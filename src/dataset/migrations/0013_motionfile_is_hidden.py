# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-06-09 09:10
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataset', '0012_auto_20160609_1001'),
    ]

    operations = [
        migrations.AddField(
            model_name='motionfile',
            name='is_hidden',
            field=models.BooleanField(default=False),
        ),
    ]