# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-02-16 16:11
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataset', '0003_auto_20160215_1659'),
    ]

    operations = [
        migrations.AddField(
            model_name='annotation',
            name='duration',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
