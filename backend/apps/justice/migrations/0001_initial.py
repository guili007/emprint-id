"""Migration initiale Module 08 — Eyeshield Justice."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── CriminalRecord ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='CriminalRecord',
            fields=[
                ('id',                       models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('national_id',              models.CharField(max_length=20, db_index=True)),
                ('record_type',              models.CharField(
                    max_length=12, db_index=True,
                    choices=[
                        ('FELONY',      'Crime'),
                        ('MISDEMEANOR', 'Délit'),
                        ('INFRACTION',  'Contravention'),
                        ('ACQUITTAL',   'Acquittement'),
                        ('PARDON',      'Grâce présidentielle'),
                    ],
                )),
                ('offense_code',             models.CharField(max_length=20, blank=True)),
                ('offense_description',      models.TextField()),
                ('judgment_date',            models.DateField()),
                ('court_name',               models.CharField(max_length=200)),
                ('sentence_type',            models.CharField(
                    max_length=20,
                    choices=[
                        ('PRISON',            'Emprisonnement'),
                        ('FINE',              'Amende'),
                        ('COMMUNITY_SERVICE', "Travaux d’intérêt général"),
                        ('PROBATION',         'Probation'),
                        ('ACQUITTED',         'Acquitté'),
                        ('SUSPENDED',         'Peine suspendue'),
                    ],
                )),
                ('sentence_duration_months', models.PositiveSmallIntegerField(null=True, blank=True)),
                ('fine_amount_cdf',          models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)),
                ('release_date',             models.DateField(null=True, blank=True)),
                ('created_at',               models.DateTimeField(auto_now_add=True, db_index=True)),
                ('created_by',               models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='criminal_records_created',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'casier judiciaire',
                'verbose_name_plural': 'casiers judiciaires',
                'ordering': ['-judgment_date'],
            },
        ),
        migrations.AddIndex(
            model_name='criminalrecord',
            index=models.Index(fields=['national_id', 'record_type'], name='justice_cr_nid_type_idx'),
        ),
        migrations.AddIndex(
            model_name='criminalrecord',
            index=models.Index(fields=['national_id', 'judgment_date'], name='justice_cr_nid_date_idx'),
        ),

        # ── ArrestWarrant ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name='ArrestWarrant',
            fields=[
                ('id',                  models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('national_id',         models.CharField(max_length=20, db_index=True)),
                ('warrant_type',        models.CharField(
                    max_length=8,
                    choices=[
                        ('ARREST',  "Mandat d’arrêt"),
                        ('SEARCH',  'Mandat de perquisition'),
                        ('SEIZURE', 'Mandat de saisie'),
                    ],
                )),
                ('issued_by',           models.CharField(max_length=200)),
                ('issued_at',           models.DateTimeField(auto_now_add=True, db_index=True)),
                ('expires_at',          models.DateTimeField(null=True, blank=True)),
                ('status',              models.CharField(
                    max_length=10, db_index=True,
                    choices=[
                        ('ACTIVE',    'Actif'),
                        ('EXECUTED',  'Exécuté'),
                        ('CANCELLED', 'Annulé'),
                        ('EXPIRED',   'Expiré'),
                    ],
                    default='ACTIVE',
                )),
                ('offense_description', models.TextField()),
                ('executed_at',         models.DateTimeField(null=True, blank=True)),
                ('created_by',          models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='warrants_issued',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'mandat judiciaire',
                'verbose_name_plural': 'mandats judiciaires',
                'ordering': ['-issued_at'],
            },
        ),
        migrations.AddIndex(
            model_name='arrestwarrant',
            index=models.Index(fields=['national_id', 'status'], name='justice_aw_nid_status_idx'),
        ),

        # ── JusticeAlert ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='JusticeAlert',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('national_id', models.CharField(max_length=20, db_index=True)),
                ('alert_type',  models.CharField(
                    max_length=22, db_index=True,
                    choices=[
                        ('WANTED',               'Recherché'),
                        ('BAIL_JUMPER',          'Fugitif sous caution'),
                        ('INTERNATIONAL_WANTED', 'Recherché international'),
                        ('COURT_ORDER',          'Injonction judiciaire'),
                    ],
                )),
                ('severity',    models.CharField(
                    max_length=8,
                    choices=[
                        ('LOW',      'Faible'),
                        ('MEDIUM',   'Moyen'),
                        ('HIGH',     'Élevé'),
                        ('CRITICAL', 'Critique'),
                    ],
                    default='MEDIUM',
                )),
                ('title',       models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('status',      models.CharField(
                    max_length=10, db_index=True,
                    choices=[
                        ('ACTIVE',   'Active'),
                        ('RESOLVED', 'Résolue'),
                        ('EXPIRED',  'Expirée'),
                    ],
                    default='ACTIVE',
                )),
                ('evidence',    models.JSONField(default=dict)),
                ('created_at',  models.DateTimeField(auto_now_add=True, db_index=True)),
                ('issued_by',   models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='justice_alerts_issued',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'alerte judiciaire',
                'verbose_name_plural': 'alertes judiciaires',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='justicealert',
            index=models.Index(fields=['national_id', 'status'], name='justice_ja_nid_status_idx'),
        ),
        migrations.AddIndex(
            model_name='justicealert',
            index=models.Index(fields=['alert_type', 'severity'], name='justice_ja_type_sev_idx'),
        ),
    ]
