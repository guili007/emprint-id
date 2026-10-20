"""Migration initiale Module 05 — Eyeshield Audit."""
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
            name='AuditEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(
                    choices=[
                        ('LOGIN', 'Connexion agent'),
                        ('LOGOUT', 'Déconnexion agent'),
                        ('DATA_ACCESS', 'Accès à un dossier citoyen'),
                        ('WATCHLIST_ADD', 'Ajout watchlist'),
                        ('WATCHLIST_REMOVE', 'Retrait watchlist'),
                        ('ROLE_CHANGE', 'Changement de rôle'),
                        ('CONFIG_CHANGE', 'Modification configuration'),
                        ('EXPORT', 'Export de données'),
                        ('ALERT_STATUS', 'Changement statut alerte'),
                        ('MANUAL_OVERRIDE', 'Intervention manuelle'),
                    ],
                    db_index=True,
                    max_length=20,
                )),
                ('actor_role', models.CharField(blank=True, max_length=30)),
                ('target_national_id', models.CharField(blank=True, db_index=True, max_length=20)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('details', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('actor', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='audit_events',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'événement audit',
                'verbose_name_plural': 'événements audit',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ComplianceFlag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('flag_type', models.CharField(
                    choices=[
                        ('UNUSUAL_HOUR', 'Vérification hors-horaires (22h-5h)'),
                        ('HIGH_FREQUENCY', 'Fréquence anormale (>30/heure)'),
                        ('BULK_ACCESS', 'Accès massif (>50 citoyens/jour)'),
                        ('CROSS_SECTOR', 'Accès multi-secteurs non justifié'),
                        ('UNAUTHORIZED_ATTEMPT', "Tentative d'accès non autorisé"),
                    ],
                    db_index=True,
                    max_length=25,
                )),
                ('severity', models.CharField(
                    choices=[('LOW', 'Faible'), ('MEDIUM', 'Modéré'), ('HIGH', 'Élevé')],
                    max_length=10,
                )),
                ('actor_role', models.CharField(blank=True, max_length=30)),
                ('target_national_id', models.CharField(blank=True, db_index=True, max_length=20)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[('OPEN', 'Ouvert'), ('REVIEWED', 'Examiné'), ('DISMISSED', 'Classé sans suite')],
                    db_index=True,
                    default='OPEN',
                    max_length=12,
                )),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('actor', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='compliance_flags_as_actor',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='compliance_flags_reviewed',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'flag conformité',
                'verbose_name_plural': 'flags conformité',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AuditReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_type', models.CharField(
                    choices=[
                        ('DAILY', 'Quotidien'),
                        ('WEEKLY', 'Hebdomadaire'),
                        ('MONTHLY', 'Mensuel'),
                        ('CUSTOM', 'Personnalisé'),
                    ],
                    max_length=10,
                )),
                ('period_start', models.DateField()),
                ('period_end', models.DateField()),
                ('generated_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('status', models.CharField(
                    choices=[
                        ('PENDING', 'En cours de génération'),
                        ('COMPLETE', 'Terminé'),
                        ('FAILED', 'Échec'),
                    ],
                    default='PENDING',
                    max_length=10,
                )),
                ('summary', models.JSONField(default=dict)),
                ('generated_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='generated_audit_reports',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'rapport audit',
                'verbose_name_plural': 'rapports audit',
                'ordering': ['-generated_at'],
            },
        ),
        migrations.AddIndex(
            model_name='auditevent',
            index=models.Index(fields=['event_type', 'created_at'], name='audit_event_type_created_idx'),
        ),
        migrations.AddIndex(
            model_name='auditevent',
            index=models.Index(fields=['actor', 'created_at'], name='audit_event_actor_created_idx'),
        ),
        migrations.AddIndex(
            model_name='complianceflag',
            index=models.Index(fields=['flag_type', 'status'], name='audit_flag_type_status_idx'),
        ),
        migrations.AddIndex(
            model_name='complianceflag',
            index=models.Index(fields=['actor', 'created_at'], name='audit_flag_actor_created_idx'),
        ),
        migrations.AddIndex(
            model_name='auditreport',
            index=models.Index(fields=['report_type', 'period_start'], name='audit_report_type_period_idx'),
        ),
    ]
