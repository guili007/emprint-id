"""Migration initiale Module 09 — Eyeshield Health."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HealthPatient',
            fields=[
                ('id',                models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('national_id',       models.CharField(db_index=True, max_length=20, unique=True)),
                ('blood_type',        models.CharField(blank=True, max_length=3, choices=[
                    ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
                    ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-'),
                ])),
                ('allergies',         models.JSONField(default=list)),
                ('chronic_conditions',models.JSONField(default=list)),
                ('created_at',        models.DateTimeField(auto_now_add=True)),
                ('updated_at',        models.DateTimeField(auto_now=True)),
                ('created_by',        models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='health_patients_created',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'dossier m\xe9dical',
                'verbose_name_plural': 'dossiers m\xe9dicaux',
            },
        ),
        migrations.CreateModel(
            name='HealthVisit',
            fields=[
                ('id',               models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('facility_name',    models.CharField(max_length=200)),
                ('visit_type',       models.CharField(max_length=15, choices=[
                    ('CONSULTATION', 'Consultation'), ('HOSPITALISATION', 'Hospitalisation'),
                    ('URGENCE', 'Urgence'), ('TELECONSULT', 'T\xe9l\xe9consultation'),
                ])),
                ('motif',            models.CharField(max_length=300)),
                ('diagnostic_code',  models.CharField(blank=True, db_index=True, max_length=10)),
                ('diagnostic_label', models.CharField(blank=True, max_length=300)),
                ('date_visite',      models.DateTimeField(auto_now_add=True, db_index=True)),
                ('patient',          models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='visits',
                    to='health.healthpatient',
                )),
                ('agent',            models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='health_visits_recorded',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'consultation',
                'verbose_name_plural': 'consultations',
                'ordering': ['-date_visite'],
                'indexes': [
                    models.Index(fields=['patient', 'date_visite'], name='health_visit_patient_date_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='HealthVaccination',
            fields=[
                ('id',                  models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('vaccin_nom',          models.CharField(max_length=100)),
                ('vaccin_code',         models.CharField(db_index=True, max_length=20)),
                ('dose_numero',         models.PositiveSmallIntegerField(default=1)),
                ('date_administration', models.DateField(db_index=True)),
                ('lot_numero',          models.CharField(blank=True, max_length=50)),
                ('facility_name',       models.CharField(max_length=200)),
                ('patient',             models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='vaccinations',
                    to='health.healthpatient',
                )),
                ('agent',               models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='vaccinations_recorded',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'vaccination',
                'verbose_name_plural': 'vaccinations',
                'ordering': ['-date_administration'],
                'indexes': [
                    models.Index(fields=['patient', 'vaccin_code'], name='health_vac_patient_code_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='HealthPrescription',
            fields=[
                ('id',                models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('medicament_nom',    models.CharField(max_length=200)),
                ('posologie',         models.CharField(max_length=200)),
                ('facility_name',     models.CharField(max_length=200)),
                ('date_prescription', models.DateField(auto_now_add=True, db_index=True)),
                ('est_delivre',       models.BooleanField(default=False)),
                ('patient',           models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='prescriptions',
                    to='health.healthpatient',
                )),
                ('visit',             models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='prescriptions',
                    to='health.healthvisit',
                )),
                ('prescrit_par',      models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='prescriptions_issued',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'prescription',
                'verbose_name_plural': 'prescriptions',
                'ordering': ['-date_prescription'],
            },
        ),
        migrations.CreateModel(
            name='EpidemioAlert',
            fields=[
                ('id',            models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('disease_code',  models.CharField(db_index=True, max_length=20)),
                ('disease_name',  models.CharField(max_length=100)),
                ('province',      models.CharField(db_index=True, max_length=100)),
                ('territoire',    models.CharField(blank=True, max_length=100)),
                ('cas_confirmes', models.PositiveIntegerField(default=0)),
                ('cas_suspects',  models.PositiveIntegerField(default=0)),
                ('deces',         models.PositiveIntegerField(default=0)),
                ('date_debut',    models.DateField(db_index=True)),
                ('date_fin',      models.DateField(blank=True, null=True)),
                ('niveau',        models.CharField(max_length=8, default='MODERE', choices=[
                    ('FAIBLE', 'Faible'), ('MODERE', 'Mod\xe9r\xe9'),
                    ('ELEVE', '\xc9lev\xe9'), ('CRITIQUE', 'Critique'),
                ])),
                ('statut',        models.CharField(max_length=10, db_index=True, default='EN_COURS', choices=[
                    ('EN_COURS', 'En cours'), ('RESOLU', 'R\xe9solu'),
                    ('SURVEILLE', 'Sous surveillance'),
                ])),
                ('source',        models.CharField(blank=True, max_length=100)),
                ('created_at',    models.DateTimeField(auto_now_add=True)),
                ('created_by',    models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='epidemio_alerts_created',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'alerte \xe9pid\xe9miologique',
                'verbose_name_plural': 'alertes \xe9pid\xe9miologiques',
                'ordering': ['-date_debut'],
                'indexes': [
                    models.Index(fields=['statut', 'date_debut'], name='health_epi_statut_date_idx'),
                    models.Index(fields=['province', 'statut'],   name='health_epi_province_statut_idx'),
                ],
            },
        ),
    ]
