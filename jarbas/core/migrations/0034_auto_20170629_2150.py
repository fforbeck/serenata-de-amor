# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-06-30 00:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_add_index_for_subquota_description'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalreimbursement',
            name='congressperson_document',
            field=models.IntegerField(blank=True, null=True, verbose_name='Número da Carteira Parlamentar'),
        ),
        migrations.AlterField(
            model_name='historicalreimbursement',
            name='receipt_fetched',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Tentamos acessar a URL do documento fiscal?'),
        ),
        migrations.AlterField(
            model_name='historicalreimbursement',
            name='term',
            field=models.IntegerField(blank=True, null=True, verbose_name='Número da Legislatura'),
        ),
        migrations.AlterField(
            model_name='reimbursement',
            name='congressperson_document',
            field=models.IntegerField(blank=True, null=True, verbose_name='Número da Carteira Parlamentar'),
        ),
        migrations.AlterField(
            model_name='reimbursement',
            name='receipt_fetched',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Tentamos acessar a URL do documento fiscal?'),
        ),
        migrations.AlterField(
            model_name='reimbursement',
            name='term',
            field=models.IntegerField(blank=True, null=True, verbose_name='Número da Legislatura'),
        ),
    ]
