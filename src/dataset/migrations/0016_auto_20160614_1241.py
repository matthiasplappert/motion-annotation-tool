# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-06-14 10:41
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dataset', '0015_dataset_filesize'),
    ]

    operations = [
        migrations.CreateModel(
            name='Download',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creation_date', models.DateTimeField(auto_now_add=True)),
                ('ip_address', models.CharField(blank=True, max_length=255, null=True)),
                ('accept_language', models.CharField(blank=True, max_length=50, null=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='dataset',
            name='nb_downloads',
        ),
        migrations.AddField(
            model_name='download',
            name='dataset',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='dataset.Dataset'),
        ),
    ]
