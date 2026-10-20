"""
Commande de synchronisation EduFirst → cache local Eyeshield Edu.

Usage :
    python manage.py sync_edufirst
    python manage.py sync_edufirst --school-id 42   # une école seulement
    python manage.py sync_edufirst --dry-run         # aperçu sans écriture

Variables d'environnement requises :
    EDUFIRST_BASE_URL        ex. https://api.edufirst.pro
    EDUFIRST_SERVICE_EMAIL   compte de service (superadmin ou lecture seule)
    EDUFIRST_SERVICE_PASSWORD

Stratégie :
  1. Authentification JWT sur EduFirst (/auth/login/)
  2. Récupération des écoles (/api/schools/)
  3. Pour chaque école : récupération des élèves + bulletins
  4. Upsert dans EduSchool, EduStudent, EduBulletin, EduNoteBulletin
  5. Mise à jour de EduSchool.last_synced
"""
import logging
from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger('emprint.foundry.edu.sync')


class Command(BaseCommand):
    help = "Synchronise le cache Eyeshield Edu depuis api.edufirst.pro"

    def add_arguments(self, parser):
        parser.add_argument(
            '--school-id', type=int, default=None,
            help="Synchroniser une seule école (edufirst_school_id)"
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Aperçu sans écriture en base"
        )

    def handle(self, *args, **options):
        try:
            import requests
        except ImportError:
            self.stderr.write("Paquet 'requests' manquant. Installe-le avec pip install requests.")
            return

        # Imports ici pour éviter les dépendances circulaires au démarrage
        from apps.foundry.models import EduSchool, EduStudent, EduBulletin, EduNoteBulletin

        base_url = getattr(settings, 'EDUFIRST_BASE_URL', '').rstrip('/')
        email    = getattr(settings, 'EDUFIRST_SERVICE_EMAIL', '')
        password = getattr(settings, 'EDUFIRST_SERVICE_PASSWORD', '')
        dry_run  = options['dry_run']
        school_id_filter = options['school_id']

        if not all([base_url, email, password]):
            self.stderr.write(
                "EDUFIRST_BASE_URL, EDUFIRST_SERVICE_EMAIL et "
                "EDUFIRST_SERVICE_PASSWORD sont requis."
            )
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("Mode dry-run — aucune écriture."))

        # ── 1. Authentification ────────────────────────────────────────────────
        self.stdout.write("Authentification sur EduFirst…")
        try:
            resp = requests.post(
                f"{base_url}/auth/login/",
                json={"email": email, "password": password},
                timeout=15,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Échec auth EduFirst : %s", exc, exc_info=True)
            self.stderr.write(f"Erreur d'authentification : {exc}")
            return

        token = resp.json().get('access', '')
        if not token:
            self.stderr.write("Token JWT absent dans la réponse.")
            return

        headers = {"Authorization": f"Bearer {token}"}
        self.stdout.write(self.style.SUCCESS("Authentifié."))

        # ── 2. Récupération des écoles ─────────────────────────────────────────
        try:
            resp = requests.get(f"{base_url}/api/schools/", headers=headers, timeout=15)
            resp.raise_for_status()
            schools_data = resp.json()
        except Exception as exc:
            logger.error("Récupération écoles EduFirst : %s", exc, exc_info=True)
            self.stderr.write(f"Erreur récupération écoles : {exc}")
            return

        if isinstance(schools_data, dict):
            schools_data = schools_data.get('results', [])

        schools_synced = 0
        students_synced = 0
        bulletins_synced = 0

        for school_data in schools_data:
            school_ef_id = school_data.get('id')

            if school_id_filter and school_ef_id != school_id_filter:
                continue

            school_name = school_data.get('name', f"École #{school_ef_id}")
            self.stdout.write(f"  → École {school_name} (id={school_ef_id})…")

            if not dry_run:
                school, _ = EduSchool.objects.update_or_create(
                    edufirst_school_id=school_ef_id,
                    defaults={
                        'name':    school_name,
                        'country': school_data.get('country', ''),
                        'city':    school_data.get('city', ''),
                        'is_active': True,
                    },
                )
            schools_synced += 1

            # ── 3. Élèves de cette école ───────────────────────────────────────
            try:
                resp = requests.get(
                    f"{base_url}/api/students/",
                    headers=headers,
                    params={"school": school_ef_id, "page_size": 200},
                    timeout=30,
                )
                resp.raise_for_status()
                students_data = resp.json()
            except Exception as exc:
                logger.error("Élèves école %s : %s", school_ef_id, exc, exc_info=True)
                self.stderr.write(f"    Erreur élèves : {exc}")
                continue

            if isinstance(students_data, dict):
                students_data = students_data.get('results', [])

            for s in students_data:
                ef_student_id = s.get('id') or s.get('student_id')
                user = s.get('user', {})
                nom    = user.get('last_name') or s.get('nom', '')
                prenom = user.get('first_name') or s.get('prenom', '')

                if not dry_run and ef_student_id:
                    student, _ = EduStudent.objects.update_or_create(
                        edufirst_student_id=ef_student_id,
                        defaults={
                            'school':          school,
                            'matricule':       s.get('matricule', ''),
                            'nom':             nom,
                            'prenom':          prenom,
                            'date_naissance':  s.get('birth_date') or s.get('date_naissance', '1900-01-01'),
                        },
                    )
                students_synced += 1

                # ── 4. Bulletins de cet élève ──────────────────────────────────
                try:
                    resp = requests.get(
                        f"{base_url}/api/bulletins/",
                        headers=headers,
                        params={"student": ef_student_id},
                        timeout=15,
                    )
                    resp.raise_for_status()
                    bulletins_data = resp.json()
                except Exception as exc:
                    logger.warning("Bulletins élève %s : %s", ef_student_id, exc)
                    continue

                if isinstance(bulletins_data, dict):
                    bulletins_data = bulletins_data.get('results', [])

                for b in bulletins_data:
                    ef_bulletin_id = b.get('id')
                    if not dry_run and ef_bulletin_id:
                        bulletin, _ = EduBulletin.objects.update_or_create(
                            edufirst_bulletin_id=ef_bulletin_id,
                            defaults={
                                'student':        student,
                                'periode':        b.get('periode', ''),
                                'annee_scolaire': b.get('annee_scolaire', ''),
                                'moyenne':        b.get('moyenne', 0),
                                'mention':        b.get('mention', ''),
                                'appreciation':   b.get('appreciation', ''),
                                'conduite':       b.get('conduite', ''),
                            },
                        )
                        # Upsert des notes par matière
                        for note_data in b.get('notes', []):
                            EduNoteBulletin.objects.update_or_create(
                                bulletin=bulletin,
                                matiere_nom=note_data.get('matiere', ''),
                                defaults={
                                    'note':         note_data.get('note', 0),
                                    'note_max':     note_data.get('note_max', 100),
                                    'appreciation': note_data.get('appreciation_matiere', ''),
                                },
                            )
                    bulletins_synced += 1

            # Marquer la date de dernière sync
            if not dry_run:
                school.last_synced = datetime.now(tz=timezone.utc)
                school.save(update_fields=['last_synced'])

        self.stdout.write(self.style.SUCCESS(
            f"Sync terminée : {schools_synced} école(s), "
            f"{students_synced} élève(s), "
            f"{bulletins_synced} bulletin(s)."
        ))
