# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_remove_frase_modelo_laudo_frase_modelos_laudo'),
    ]

    operations = [
        migrations.AddField(
            model_name='frase',
            name='metodos',
            field=models.ManyToManyField(blank=True, to='api.metodo'),
        ),
    ]
