# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-02-18 10:12
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataset', '0004_annotation_duration'),
    ]

    operations = [
        migrations.AlterField(
            model_name='motionfile',
            name='filename',
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
