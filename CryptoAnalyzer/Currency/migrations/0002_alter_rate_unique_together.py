# Generated by Django 3.2.9 on 2021-11-14 00:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Currency', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='rate',
            unique_together={('from_currency', 'to_currency', 'timestamp', 'source')},
        ),
    ]