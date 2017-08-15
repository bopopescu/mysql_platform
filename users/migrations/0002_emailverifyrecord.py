# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-08-14 15:09
from __future__ import unicode_literals

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailVerifyRecord',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, verbose_name='code')),
                ('email', models.EmailField(max_length=50, verbose_name='email')),
                ('send_type', models.CharField(choices=[('register', 'register'), ('forget', 'forget')], default='forget', max_length=10)),
                ('send_time', models.DateTimeField(default=datetime.datetime.now)),
            ],
            options={
                'verbose_name': 'Email\u9a8c\u8bc1\u7801',
                'verbose_name_plural': 'Email\u9a8c\u8bc1\u7801',
            },
        ),
    ]