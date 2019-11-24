# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-07-16 19:18
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('productdb', '0029_auto_20181125_2250'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productcheckentry',
            name='part_of_product_list',
            field=models.TextField(blank=True, default='', help_text='hash values of product lists that contain the Product (at time of the check)', max_length=8192, verbose_name='product list hash values'),
        ),
    ]