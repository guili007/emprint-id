"""
Commande management : sync_siga
================================
Synchronise les agents SIGA-RDC dans le cache local Foundry Gov.

Usage :
    python manage.py sync_siga              # mise à jour incrémentale
    python manage.py sync_siga --full       # force la mise à jour de tous les agents
    python manage.py sync_siga --dry-run    # affiche ce qui serait fait, sans écrire

Stratégie :
  - `update_or_create` par `siga_uuid` → jamais de doublons
  - Ne supprime JAMAIS un fonctionnaire (même s'il disparaît de SIGA).
    Si le statut devient RADIE ou DECEDE, on le met à jour en local.
  - Pagine sur /api/v1/agents/ jusqu'à épuisement (next == null)
  - Pour chaque agent, récupère aussi ses événements de carrière

Variables d'environnement nécessaires :
    SIGA_BASE_URL, SIGA_SERVICE_USER, SIGA_SERVICE_PASSWORD
"""
import logging
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.foundry.gov.connector import SIGAConnector, SIGAConnectionError
from apps.foundry.models import GovEmployee, GovCareerEvent

logger = logging.getLogger('emprint.foundry.gov')


class Command(BaseCommand):
    help = "Synchronise les agents SIGA-RDC dans le cache Foundry Gov."

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help="Met à jour tous les agents, pas seulement les modifiés.",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Affiche ce qui serait fait sans rien écrire en base.",
        )

    def handle(self, *args, **options):
        full = options['full']
        dry_run = options['dry_run']

        self.stdout.write(
            self.style.NOTICE(
                f"Synchro SIGA {'(dry-run) ' if dry_run else ''}{'[FULL] ' if full else ''}…"
            )
        )

        try:
            connector = SIGAConnector()
            connector.authenticate()
        except SIGAConnectionError as exc:
            # Erreur critique — on loggue et on arrête proprement
            self.stderr.write(self.style.ERROR(f"Impossible de se connecter à SIGA : {exc}"))
            return

        created_count = 0
        updated_count = 0
        page = 1

        while True:
            try:
                data = connector.list_agents(page=page)
            except SIGAConnectionError as exc:
                self.stderr.write(self.style.ERROR(f"Erreur page {page} : {exc}"))
                break

            # DRF retourne {'count': N, 'next': '...', 'results': [...]}
            results = data.get('results', [])

            for agent_data in results:
                created, updated = _sync_one_agent(
                    agent_data, connector, dry_run=dry_run, full=full
                )
                created_count += created
                updated_count += updated

            # Si `next` est null, on a tout parcouru
            if not data.get('next'):
                break
            page += 1

        action = "(dry-run) aurait " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Terminé. {action}Créé : {created_count}, mis à jour : {updated_count}."
            )
        )


def _sync_one_agent(agent_data, connector, dry_run=False, full=False):
    """
    Crée ou met à jour un GovEmployee à partir d'une ligne de l'API SIGA.
    Retourne (created: int, updated: int).
    """
    siga_uuid = agent_data.get('public_id') or agent_data.get('id')

    # Extraction des données imbriquées (grade_actuel, unite_actuelle)
    grade = agent_data.get('grade_actuel') or {}
    unite = agent_data.get('unite_actuelle') or {}

    # L'administration est la racine de l'arbre (ministère).
    # SIGA ne la retourne pas directement dans la liste — on l'approche
    # via unite.type_unite == ADMINISTRATION, ou on utilise une heuristique.
    administration_nom = _extract_administration(unite)

    defaults = {
        'matricule':         agent_data.get('matricule', ''),
        'nom':               agent_data.get('nom', ''),
        'postnom':           agent_data.get('postnom', ''),
        'prenom':            agent_data.get('prenom', ''),
        'sexe':              agent_data.get('sexe', ''),
        'statut':            agent_data.get('statut', GovEmployee.Statut.ACTIF),
        'grade_code':        grade.get('code', ''),
        'grade_libelle':     grade.get('libelle', ''),
        'unite_nom':         unite.get('nom', ''),
        'unite_type':        unite.get('type_unite', ''),
        'administration_nom': administration_nom,
        'synced_at':         timezone.now(),
    }

    if dry_run:
        logger.debug("[dry-run] agent %s (%s)", siga_uuid, defaults['matricule'])
        return 0, 0

    employee, created = GovEmployee.objects.update_or_create(
        siga_uuid=siga_uuid,
        defaults=defaults,
    )

    # Synchroniser les événements de carrière (seulement si demandé ou créé)
    if created or full:
        _sync_career_events(employee, connector)

    return (1, 0) if created else (0, 1)


def _sync_career_events(employee, connector):
    """
    Récupère les événements de carrière de cet agent depuis SIGA
    et les ajoute en local (append-only — on ne supprime jamais un événement).
    """
    try:
        events_data = connector.get_agent_events(employee.siga_uuid)
    except SIGAConnectionError:
        logger.warning(
            "Impossible de récupérer les événements de %s.", employee.matricule
        )
        return

    results = events_data if isinstance(events_data, list) else events_data.get('results', [])

    for ev in results:
        # `get_or_create` par (employee, type, date_effet, reference_acte)
        # évite les doublons si la synchro est rejouée
        GovCareerEvent.objects.get_or_create(
            employee=employee,
            type_evenement=ev.get('type_evenement', ''),
            date_effet=_parse_date(ev.get('date_effet')),
            reference_acte=ev.get('reference_acte', ''),
            defaults={
                'grade_code': (ev.get('grade') or {}).get('code', ''),
                'unite_nom':  (ev.get('unite') or {}).get('nom', ''),
            },
        )


def _extract_administration(unite_data):
    """
    Heuristique : si l'unité est de type ADMINISTRATION, c'est la racine.
    Sinon on utilise le nom comme fallback (l'arbre complet nécessiterait
    un appel récursif à l'API, ce qu'on évite pour la performance).
    """
    if not unite_data:
        return ''
    if unite_data.get('type_unite') == 'ADMINISTRATION':
        return unite_data.get('nom', '')
    # Si l'unité a un parent, il faudrait remonter — pour v1, on utilise le nom
    return unite_data.get('nom', '')


def _parse_date(value):
    """Parse une date ISO (YYYY-MM-DD) ou retourne aujourd'hui en fallback."""
    if not value:
        return date.today()
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return date.today()
