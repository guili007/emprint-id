"""Migration initiale Module 10 — Eyeshield Education."""
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
            name='StudentRecord',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('national_id',  models.CharField(db_index=True, max_length=20)),
                ('school_year',  models.CharField(db_index=True, max_length=9)),
                ('niveau',       models.CharField(max_length=15, choices=[
                    ('PRESCOLAIRE', 'Préscolaire'), ('PRIMAIRE', 'Primaire'),
                    ('SECONDAIRE', 'Secondaire'), ('SUPERIEUR', 'Supérieur'),
                    ('FORMATION_PRO', 'Formation professionnelle'),
                ])),
                ('classe',       models.CharField(max_length=50)),
                ('etablissement',models.CharField(max_length=200)),
                ('province',     models.CharField(db_index=True, max_length=100)),
                ('statut',       models.CharField(max_length=10, db_index=True, default='ACTIF', choices=[
                    ('ACTIF', 'Actif'), ('DIPLOME', 'Diplômé'),
                    ('ABANDONNE', 'Abandonné'), ('TRANSFERE', 'Transféré'),
                ])),
                ('created_at',   models.DateTimeField(auto_now_add=True)),
                ('updated_at',   models.DateTimeField(auto_now=True)),
                ('created_by',   models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='student_records_created',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'dossier scolaire',
                'verbose_name_plural': 'dossiers scolaires',
                'ordering': ['-school_year'],
            },
        ),
        migrations.AddConstraint(
            model_name='studentrecord',
            constraint=models.UniqueConstraint(
                fields=['national_id', 'school_year'],
                name='uniq_student_year',
            ),
        ),
        migrations.CreateModel(
            name='AcademicResult',
            fields=[
                ('id',        models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('matiere',   models.CharField(max_length=100)),
                ('note',      models.DecimalField(max_digits=5, decimal_places=2)),
                ('note_max',  models.DecimalField(max_digits=5, decimal_places=2, default=100)),
                ('mention',   models.CharField(max_length=20, choices=[
                    ('ECHEC', '\xc9chec'), ('PASSABLE', 'Passable'),
                    ('SATISFACTION', 'Satisfaction'), ('DISTINCTION', 'Distinction'),
                    ('GRANDE_DISTINCTION', 'Grande Distinction'),
                    ('MAX_DES_POINTS', 'Maximum des points'),
                ])),
                ('created_at',models.DateTimeField(auto_now_add=True)),
                ('student',   models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='results',
                    to='education.studentrecord',
                )),
                ('agent',     models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='academic_results_recorded',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'r\xe9sultat scolaire',
                'verbose_name_plural': 'r\xe9sultats scolaires',
                'ordering': ['matiere'],
            },
        ),
        migrations.CreateModel(
            name='Diploma',
            fields=[
                ('id',                models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('national_id',       models.CharField(db_index=True, max_length=20)),
                ('type_diplome',      models.CharField(db_index=True, max_length=10, choices=[
                    ('CERT_PRIM', "Certificat d'\xe9tudes primaires"),
                    ('DIPL_ETAT', "Dipl\xf4me d'\xc9tat (secondaire)"),
                    ('LICENCE', 'Licence'), ('MASTER', 'Master'),
                    ('DOCTORAT', 'Doctorat'), ('BREVET_PRO', 'Brevet professionnel'),
                ])),
                ('etablissement',     models.CharField(max_length=200)),
                ('province',          models.CharField(max_length=100)),
                ('annee_obtention',   models.PositiveSmallIntegerField(db_index=True)),
                ('numero_certificat', models.CharField(db_index=True, max_length=50, unique=True)),
                ('mention',           models.CharField(blank=True, max_length=20)),
                ('created_at',        models.DateTimeField(auto_now_add=True)),
                ('created_by',        models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='diplomas_recorded',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'dipl\xf4me',
                'verbose_name_plural': 'dipl\xf4mes',
                'ordering': ['-annee_obtention'],
                'indexes': [
                    models.Index(fields=['national_id', 'type_diplome'], name='edu_diploma_nat_type_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='SchoolAlert',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('national_id', models.CharField(db_index=True, max_length=20)),
                ('alert_type',  models.CharField(db_index=True, max_length=15, choices=[
                    ('ABANDON', "Risque d'abandon"), ('COMPORTEMENT', 'Probl\xe8me comportemental'),
                    ('VULNERABLE', '\xc9l\xe8ve vuln\xe9rable'),
                    ('DIPLOME_FAUX', 'Suspicion dipl\xf4me frauduleux'),
                    ('AUTRE', 'Autre'),
                ])),
                ('severity',    models.CharField(max_length=8, default='MODERE', choices=[
                    ('FAIBLE', 'Faible'), ('MODERE', 'Mod\xe9r\xe9'),
                    ('ELEVE', '\xc9lev\xe9'), ('CRITIQUE', 'Critique'),
                ])),
                ('description', models.TextField()),
                ('statut',      models.CharField(max_length=8, db_index=True, default='OUVERT', choices=[
                    ('OUVERT', 'Ouvert'), ('RESOLU', 'R\xe9solu'), ('ARCHIVE', 'Archiv\xe9'),
                ])),
                ('created_at',  models.DateTimeField(auto_now_add=True)),
                ('issued_by',   models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='school_alerts_issued',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'alerte scolaire',
                'verbose_name_plural': 'alertes scolaires',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['national_id', 'statut'], name='edu_alert_nat_statut_idx'),
                ],
            },
        ),
    ]
