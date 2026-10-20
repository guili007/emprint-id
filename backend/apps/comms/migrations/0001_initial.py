"""Migration initiale Module 06 — Eyeshield Comms."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SimCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('msisdn',      models.CharField(max_length=20, unique=True, db_index=True)),
                ('imei',        models.CharField(max_length=20, blank=True, db_index=True)),
                ('national_id', models.CharField(max_length=20, blank=True, db_index=True)),
                ('operator',    models.CharField(
                    max_length=10,
                    choices=[
                        ('MTN', 'MTN Congo'), ('VODACOM', 'Vodacom Congo'),
                        ('AIRTEL', 'Airtel Congo'), ('ORANGE', 'Orange Congo'),
                        ('AFRICELL', 'Africell Congo'), ('UNKNOWN', 'Opérateur inconnu'),
                    ],
                    default='UNKNOWN',
                )),
                ('status', models.CharField(
                    max_length=12,
                    choices=[
                        ('ACTIVE', 'Active'), ('SUSPENDED', 'Suspendue'),
                        ('BLACKLISTED', 'Liste noire'), ('EXPIRED', 'Expirée'),
                    ],
                    default='ACTIVE',
                )),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('last_seen_at',  models.DateTimeField(null=True, blank=True)),
                ('registered_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='registered_sims',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'carte SIM',
                'verbose_name_plural': 'cartes SIM',
                'ordering': ['-registered_at'],
            },
        ),
        migrations.CreateModel(
            name='CallRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('caller_msisdn', models.CharField(max_length=20, db_index=True)),
                ('callee_msisdn', models.CharField(max_length=20, db_index=True)),
                ('call_type',    models.CharField(
                    max_length=5,
                    choices=[('VOICE', 'Appel vocal'), ('SMS', 'SMS'), ('DATA', 'Session data')],
                )),
                ('duration_sec',  models.PositiveIntegerField(default=0)),
                ('started_at',    models.DateTimeField(db_index=True)),
                ('cell_tower_id', models.CharField(max_length=20, blank=True)),
                ('province',      models.CharField(max_length=100, blank=True)),
                ('caller_imei',   models.CharField(max_length=20, blank=True)),
            ],
            options={
                'verbose_name': 'enregistrement CDR',
                'verbose_name_plural': 'enregistrements CDR',
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='CommsAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_type', models.CharField(
                    max_length=20, db_index=True,
                    choices=[
                        ('IMEI_SWAP', 'Swap IMEI (SIM utilisée sur plusieurs appareils)'),
                        ('MULTI_SIM', 'Multi-SIM (même personne, plusieurs numéros)'),
                        ('FREQUENT_CONTACT', 'Contact fréquent suspect (>X appels/jour)'),
                        ('SIM_CLONE', 'Clone SIM suspecté (MSISDN simultané)'),
                        ('CROSS_BORDER', 'Trafic transfrontalier suspect'),
                        ('BLACKLIST_CONTACT', 'Contact avec MSISDN liste noire'),
                    ],
                )),
                ('severity', models.CharField(
                    max_length=10,
                    choices=[('LOW', 'Faible'), ('MEDIUM', 'Modéré'), ('HIGH', 'Élevé'), ('CRITICAL', 'Critique')],
                )),
                ('national_id', models.CharField(max_length=20, blank=True, db_index=True)),
                ('msisdn_a',    models.CharField(max_length=20, blank=True, db_index=True)),
                ('msisdn_b',    models.CharField(max_length=20, blank=True)),
                ('title',       models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(
                    max_length=20, default='OPEN',
                    choices=[
                        ('OPEN', 'Ouverte'), ('INVESTIGATING', "En cours d'investigation"),
                        ('CLOSED', 'Fermée'), ('FALSE_POSITIVE', 'Faux positif'),
                    ],
                )),
                ('evidence',    models.JSONField(default=dict)),
                ('created_at',  models.DateTimeField(auto_now_add=True, db_index=True)),
                ('resolved_at', models.DateTimeField(null=True, blank=True)),
                ('created_by',  models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_comms_alerts',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'alerte comms',
                'verbose_name_plural': 'alertes comms',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='simcard',
            index=models.Index(fields=['national_id', 'status'], name='comms_sim_natid_status_idx'),
        ),
        migrations.AddIndex(
            model_name='simcard',
            index=models.Index(fields=['imei'], name='comms_sim_imei_idx'),
        ),
        migrations.AddIndex(
            model_name='callrecord',
            index=models.Index(fields=['caller_msisdn', 'started_at'], name='comms_cdr_caller_idx'),
        ),
        migrations.AddIndex(
            model_name='callrecord',
            index=models.Index(fields=['callee_msisdn', 'started_at'], name='comms_cdr_callee_idx'),
        ),
        migrations.AddIndex(
            model_name='callrecord',
            index=models.Index(fields=['started_at'], name='comms_cdr_started_idx'),
        ),
        migrations.AddIndex(
            model_name='commsalert',
            index=models.Index(fields=['alert_type', 'severity'], name='comms_alert_type_sev_idx'),
        ),
        migrations.AddIndex(
            model_name='commsalert',
            index=models.Index(fields=['national_id', 'created_at'], name='comms_alert_natid_idx'),
        ),
        migrations.AddIndex(
            model_name='commsalert',
            index=models.Index(fields=['status', 'created_at'], name='comms_alert_status_idx'),
        ),
    ]
