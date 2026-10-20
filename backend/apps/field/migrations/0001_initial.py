"""Migration initiale Module 07 — Eyeshield Field."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── FieldAgent ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='FieldAgent',
            fields=[
                ('id',               models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('device_id',        models.CharField(max_length=64, blank=True, db_index=True)),
                ('zone_province',    models.CharField(max_length=100, blank=True)),
                ('zone_territoire',  models.CharField(max_length=100, blank=True)),
                ('status',           models.CharField(
                    max_length=10,
                    choices=[
                        ('ACTIVE', 'Actif'),
                        ('INACTIVE', 'Inactif'),
                        ('SUSPENDED', 'Suspendu'),
                    ],
                    default='ACTIVE',
                )),
                ('last_sync_at',     models.DateTimeField(null=True, blank=True)),
                ('created_at',       models.DateTimeField(auto_now_add=True)),
                ('agent',            models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='field_profile',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'agent terrain',
                'verbose_name_plural': 'agents terrain',
            },
        ),

        # ── FieldMission ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='FieldMission',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('title',        models.CharField(max_length=200)),
                ('description',  models.TextField(blank=True)),
                ('mission_type', models.CharField(
                    max_length=15,
                    choices=[
                        ('VERIFICATION',  'Vérification identité'),
                        ('CENSUS',        'Recensement'),
                        ('PATROL',        'Patrouille'),
                        ('INVESTIGATION', 'Enquête terrain'),
                        ('CONTROL',       'Contrôle frontière'),
                    ],
                )),
                ('province',     models.CharField(max_length=100, blank=True)),
                ('territoire',   models.CharField(max_length=100, blank=True)),
                ('status',       models.CharField(
                    max_length=12,
                    choices=[
                        ('PENDING',     'En attente'),
                        ('IN_PROGRESS', 'En cours'),
                        ('COMPLETED',   'Terminée'),
                        ('CANCELLED',   'Annulée'),
                    ],
                    default='PENDING',
                )),
                ('assigned_at',  models.DateTimeField(auto_now_add=True)),
                ('started_at',   models.DateTimeField(null=True, blank=True)),
                ('completed_at', models.DateTimeField(null=True, blank=True)),
                ('due_date',     models.DateField(null=True, blank=True)),
                ('agent',        models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='missions',
                    to='field.fieldagent',
                )),
                ('assigned_by',  models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='assigned_field_missions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'mission terrain',
                'verbose_name_plural': 'missions terrain',
                'ordering': ['-assigned_at'],
            },
        ),
        migrations.AddIndex(
            model_name='fieldmission',
            index=models.Index(fields=['agent', 'status'], name='field_missi_agent_i_idx'),
        ),
        migrations.AddIndex(
            model_name='fieldmission',
            index=models.Index(fields=['status', 'due_date'], name='field_missi_status_d_idx'),
        ),

        # ── FieldRecord ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name='FieldRecord',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('record_type', models.CharField(
                    max_length=15,
                    db_index=True,
                    choices=[
                        ('VERIFICATION', 'Vérification identité'),
                        ('OBSERVATION',  'Observation terrain'),
                        ('ARREST',       'Interpellation'),
                        ('SEIZURE',      'Saisie'),
                        ('INCIDENT',     'Incident sécuritaire'),
                        ('CHECKPOINT',   'Passage checkpoint'),
                    ],
                )),
                ('national_id',  models.CharField(max_length=20, blank=True, db_index=True)),
                ('description',  models.TextField(blank=True)),
                ('coordinates',  models.JSONField(default=dict)),
                ('province',     models.CharField(max_length=100, blank=True)),
                ('territoire',   models.CharField(max_length=100, blank=True)),
                ('offline_at',   models.DateTimeField(db_index=True)),
                ('synced_at',    models.DateTimeField(auto_now_add=True, db_index=True)),
                ('evidence',     models.JSONField(default=dict)),
                ('field_agent',  models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='records',
                    to='field.fieldagent',
                )),
                ('mission',      models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='records',
                    to='field.fieldmission',
                )),
            ],
            options={
                'verbose_name': 'enregistrement terrain',
                'verbose_name_plural': 'enregistrements terrain',
                'ordering': ['-offline_at'],
            },
        ),
        migrations.AddIndex(
            model_name='fieldrecord',
            index=models.Index(fields=['field_agent', 'offline_at'], name='field_recor_agent_o_idx'),
        ),
        migrations.AddIndex(
            model_name='fieldrecord',
            index=models.Index(fields=['record_type', 'synced_at'], name='field_recor_type_s_idx'),
        ),

        # ── SyncBatch ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='SyncBatch',
            fields=[
                ('id',              models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('device_id',       models.CharField(max_length=64, blank=True)),
                ('records_count',   models.PositiveIntegerField(default=0)),
                ('accepted_count',  models.PositiveIntegerField(default=0)),
                ('duplicate_count', models.PositiveIntegerField(default=0)),
                ('synced_at',       models.DateTimeField(auto_now_add=True, db_index=True)),
                ('status',          models.CharField(
                    max_length=10,
                    choices=[
                        ('PENDING',  'En cours de traitement'),
                        ('COMPLETE', 'Complet'),
                        ('PARTIAL',  'Partiel (certains records rejetés)'),
                        ('FAILED',   'Échec'),
                    ],
                    default='PENDING',
                )),
                ('error_log',       models.JSONField(default=list)),
                ('field_agent',     models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sync_batches',
                    to='field.fieldagent',
                )),
            ],
            options={
                'verbose_name': 'batch sync',
                'verbose_name_plural': 'batchs sync',
                'ordering': ['-synced_at'],
            },
        ),
    ]
