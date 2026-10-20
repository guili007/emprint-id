"""
Commande de détection automatique de structuration financière (smurfing).

Usage :
    python manage.py detect_structuring
    python manage.py detect_structuring --dry-run
    python manage.py detect_structuring --threshold 9999 --min-count 5

Principe : cherche dans les CitizenDataLink (source BANKING) des external_ids
qui reviennent souvent avec un montant proche du seuil de déclaration légal.
Pour l'instant, détecte les citoyens avec ≥ N liens BANKING (proxy du volume).
En production, brancher sur les données de transaction réelles via un connecteur Rawbank.
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger('emprint.intel.detect')


class Command(BaseCommand):
    help = "Détecte des patterns de structuration financière → crée des IntelAlert"

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold', type=int, default=9999,
            help="Montant seuil en USD (défaut : 9999)"
        )
        parser.add_argument(
            '--min-count', type=int, default=3,
            help="Nombre minimum de liens BANKING pour déclencher l'alerte (défaut : 3)"
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Afficher les suspects sans créer d'alertes"
        )

    def handle(self, *args, **options):
        from apps.data.models import CitizenDataLink
        from apps.intel.models import IntelAlert

        threshold = options['threshold']
        min_count = options['min_count']
        dry_run   = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING("Mode dry-run — aucune alerte créée."))

        # Citoyens avec ≥ min_count liens BANKING actifs
        from django.db.models import Count
        suspects = (
            CitizenDataLink.objects
            .filter(source__sector='BANKING')
            .values('national_id')
            .annotate(nb_liens=Count('id'))
            .filter(nb_liens__gte=min_count)
            .order_by('-nb_liens')
        )

        alerts_created = 0
        for row in suspects:
            nid     = row['national_id']
            nb      = row['nb_liens']
            title   = f"Structuration potentielle — {nb} liens bancaires (seuil {threshold}$)"
            evidence = {
                'national_id':   nid,
                'nb_liens_bank': nb,
                'threshold_usd': threshold,
                'detection':     'detect_structuring v1 (proxy liens BANKING)',
            }

            # Ne pas créer de doublon si une alerte OPEN existe déjà pour ce citoyen
            existing = IntelAlert.objects.filter(
                national_id=nid,
                alert_type=IntelAlert.AlertType.STRUCTURING,
                status=IntelAlert.Status.OPEN,
            ).exists()

            if existing:
                self.stdout.write(f"  Déjà alerté : {nid}")
                continue

            if not dry_run:
                IntelAlert.objects.create(
                    national_id=nid,
                    alert_type=IntelAlert.AlertType.STRUCTURING,
                    severity=IntelAlert.Severity.HIGH if nb >= 10 else IntelAlert.Severity.MEDIUM,
                    title=title,
                    evidence=evidence,
                    source_module='DATA',
                )
                alerts_created += 1
            else:
                self.stdout.write(f"  [dry] {nid} → {nb} liens BANKING")

        self.stdout.write(self.style.SUCCESS(
            f"Détection terminée : {alerts_created} alerte(s) créée(s)."
        ))
