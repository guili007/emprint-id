"""
Commande de seed pour EmPrint-iD (développement uniquement).

Usage :
    python manage.py seed_db
    python manage.py seed_db --flush   # efface et recrée tout

Crée :
  - 6 provinces DRC + leurs communes principales
  - 20 citoyens avec national_id, embeddings ArcFace aléatoires
  - 5 entrées watchlist (ROUGE/ORANGE/JAUNE × CIVIL/MILITAIRE/ETAT)
  - 10 logs de vérification
"""
import math
import random
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.citizens.models import Citizen, Province, Commune
from apps.biometric.models import CitizenFaceEmbedding, VerificationLog, WatchlistEntry

User = get_user_model()

# ── Données géographiques DRC ─────────────────────────────────────────────────

PROVINCES = [
    ('KN', 'Kinshasa'),
    ('KG', 'Kongo Central'),
    ('KS', 'Kasaï'),
    ('MN', 'Maniema'),
    ('NK', 'Nord-Kivu'),
    ('SK', 'Sud-Kivu'),
]

COMMUNES = {
    'KN': [('GBE', 'Gombe'), ('LWA', 'Lingwala'), ('KIN', 'Kinshasa'), ('KLM', 'Kalamu'), ('BNT', 'Bandalungwa')],
    'KG': [('MAT', 'Matadi'), ('BON', 'Boma')],
    'KS': [('KAN', 'Kananga'), ('MBJ', 'Mbuji-Mayi')],
    'MN': [('KNY', 'Kindu')],
    'NK': [('GOM', 'Goma'), ('BNI', 'Beni')],
    'SK': [('BKV', 'Bukavu'), ('UVR', 'Uvira')],
}

NOMS = ['Mutombo', 'Kabila', 'Tshisekedi', 'Lumumba', 'Kasongo', 'Mwamba',
        'Kalala', 'Nkurunziza', 'Kambere', 'Bisimwa', 'Masiala', 'Lukoki',
        'Bondombe', 'Nsimba', 'Mbemba', 'Ngalula', 'Kitenge', 'Banza',
        'Tshibangu', 'Muamba']

PRENOMS_M = ['Jean-Pierre', 'Joseph', 'Patrick', 'Emmanuel', 'Christian',
             'David', 'Michel', 'Robert', 'Pierre', 'François']
PRENOMS_F = ['Marie', 'Christine', 'Josephine', 'Yvonne', 'Claudine',
             'Angélique', 'Solange', 'Thérèse', 'Bernadette', 'Pauline']

WATCHLIST_SEED = [
    dict(alert_level='ROUGE',  authority='CIVIL',     issued_by='PNC / DEMIAP',
         reason='Trafic d\'armes — réseau Kinshasa Est'),
    dict(alert_level='ROUGE',  authority='MILITAIRE', issued_by='FARDC / G2 Renseignement',
         reason='Combattant M23 actif — zone Goma'),
    dict(alert_level='ORANGE', authority='ETAT',      issued_by='INTERPOL / Notice Rouge',
         reason='Fraude financière internationale — mandat d\'arrêt'),
    dict(alert_level='ORANGE', authority='CIVIL',     issued_by='BCC / Cellule Anti-Blanchiment',
         reason='Blanchiment de capitaux — réseau bancaire suspect'),
    dict(alert_level='JAUNE',  authority='MILITAIRE', issued_by='FARDC / Frontière NK',
         reason='Surveillance active — mouvement transfrontalier suspect'),
]


def _random_embedding() -> list:
    """Vecteur ArcFace 512D normalisé (simulé — remplacé par DeepFace en prod)."""
    v = [random.gauss(0, 1) for _ in range(512)]
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v]


def _national_id(prov_code: str, comm_code: str, seq: int) -> str:
    checksum = chr(65 + (seq % 26)) + str(seq % 10)
    return f"CG-{prov_code}-{comm_code}-{seq:06d}-{checksum}"


class Command(BaseCommand):
    help = 'Peuple la base de données EmPrint-iD avec des données de test'

    def add_arguments(self, parser):
        parser.add_argument('--flush', action='store_true',
                            help='Efface les données existantes avant de seeder')

    def handle(self, *args, **options):
        if options['flush']:
            self.stdout.write('Flush des données...')
            VerificationLog.objects.all().delete()
            WatchlistEntry.objects.all().delete()
            CitizenFaceEmbedding.objects.all().delete()
            Citizen.objects.all().delete()
            Commune.objects.all().delete()
            Province.objects.all().delete()

        # ── Provinces & Communes ──────────────────────────────────────────────
        self.stdout.write('Création des provinces et communes...')
        provinces = {}
        for code, nom in PROVINCES:
            p, _ = Province.objects.get_or_create(code=code, defaults={'nom': nom})
            provinces[code] = p

        communes = {}
        for prov_code, comm_list in COMMUNES.items():
            for comm_code, comm_nom in comm_list:
                c, _ = Commune.objects.get_or_create(
                    code=comm_code,
                    defaults={'nom': comm_nom, 'province': provinces[prov_code]}
                )
                communes[comm_code] = c

        # ── Citoyens + Embeddings ─────────────────────────────────────────────
        self.stdout.write('Création des 20 citoyens...')
        all_communes = list(communes.values())
        citizens = []
        for i, nom in enumerate(NOMS):
            sexe = random.choice(['M', 'F'])
            prenom = random.choice(PRENOMS_M if sexe == 'M' else PRENOMS_F)
            commune = all_communes[i % len(all_communes)]
            province = commune.province
            national_id = _national_id(province.code, commune.code, 1000 + i)

            citizen, created = Citizen.objects.get_or_create(
                national_id=national_id,
                defaults=dict(
                    nom=nom,
                    postnom=random.choice(NOMS),
                    prenom=prenom,
                    sexe=sexe,
                    date_naissance=date(1970 + i, (i % 12) + 1, (i % 28) + 1),
                    lieu_naissance=commune.nom,
                    province=province,
                    commune=commune,
                )
            )
            citizens.append(citizen)

            CitizenFaceEmbedding.objects.get_or_create(
                citizen=citizen,
                defaults=dict(
                    embedding=_random_embedding(),
                    liveness_score=round(random.uniform(0.75, 0.99), 4),
                    quality_score=round(random.uniform(0.80, 0.99), 4),
                )
            )

        self.stdout.write(f'  {len(citizens)} citoyens prêts.')

        # ── Watchlist ─────────────────────────────────────────────────────────
        self.stdout.write('Création de la watchlist...')
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write('Aucun superuser trouvé — crée-en un avec createsuperuser.')
            return

        for i, entry_data in enumerate(WATCHLIST_SEED):
            citizen = citizens[i]
            WatchlistEntry.objects.get_or_create(
                citizen=citizen,
                is_active=True,
                defaults=dict(
                    **entry_data,
                    created_by=admin,
                    expires_at=timezone.now() + timedelta(days=365),
                )
            )

        self.stdout.write(f'  {len(WATCHLIST_SEED)} entrées watchlist créées.')

        # ── Logs de vérification ──────────────────────────────────────────────
        self.stdout.write('Création de 10 logs de vérification...')
        agent = User.objects.filter(username='agent_police').first() or admin
        statuses = list(VerificationLog.VerifStatus.values)
        for i in range(10):
            citizen = citizens[i + 5]
            VerificationLog.objects.create(
                citizen=citizen,
                agent_user=agent,
                status=random.choice(statuses[:3]),  # VERIFIED / REJECTED_FACE / REJECTED_LIVENESS
                confidence_score=round(random.uniform(0.85, 0.99), 4),
                liveness_score=round(random.uniform(0.75, 0.99), 4),
                agent_role='ROLE_POLICE',
            )

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Seed terminé — 6 provinces, 20 citoyens, 5 watchlist, 10 logs.'
        ))
