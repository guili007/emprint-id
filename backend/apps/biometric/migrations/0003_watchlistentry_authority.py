from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('biometric', '0002_agentprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='watchlistentry',
            name='authority',
            field=models.CharField(
                choices=[
                    ('CIVIL', 'Autorité civile (Gouvernement / Police)'),
                    ('MILITAIRE', 'Forces armées (FARDC / Défense)'),
                    ('ETAT', 'État — diffusion générale (civil + militaire)'),
                ],
                default='CIVIL',
                help_text="Détermine quel dashboard reçoit l'alerte silencieuse.",
                max_length=15,
            ),
        ),
    ]
