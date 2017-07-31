# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from datetime import datetime
import MySQLdb
import json
from MySQLdb.constants.CLIENT import MULTI_STATEMENTS, MULTI_RESULTS
from django.http.response import HttpResponse, HttpResponseRedirect

from django.shortcuts import render
from django.views import View
from django.core import serializers

from mysql_platform.settings import INCEPTION_IP, INCEPTION_PORT, BACKUP_HOST_IP, BACKUP_HOST_PORT, BACKUP_PASSWORD
from mysql_platform.settings import BACKUP_USER
from statistics.models import MysqlInstance, MysqlInstanceGroup
from sql_review.models import SqlReviewRecord, SqlBackupRecord
from sql_review.forms import SqlReviewRecordForm

# Create your views here.


def review(request, record_id):
    record = SqlReviewRecord.objects.get(id=record_id)
    sql = record.sql
    instance = record.instance
    instance_ip = instance.ip
    instance_port = instance.port
    all_the_text = message_to_review_sql(option='--enable-check;--disable-remote-backup;', host=instance_ip,
                                         port=instance_port, sql=sql)
    try:
        conn = MySQLdb.connect(host=INCEPTION_IP, user='', passwd='', db='', port=INCEPTION_PORT,
                               client_flag=MULTI_STATEMENTS | MULTI_RESULTS)
        cur = conn.cursor()
        ret = cur.execute(all_the_text)
        num_fields = len(cur.description)
        field_names = [i[0] for i in cur.description]
        result = cur.fetchall()
        # 判断结果中是否有error level 为 2 的，如果有，则不做操作，如果没有则将sql_review_record 记录的 is_checked 设为1
        flag = 'success'
        for res in result:
            if res[2] == 2:
                flag = 'failed'
        if flag == 'success':
            record.is_checked = 1
            record.save()
        cur.close()
        conn.close()
        data = {
            'field_names': field_names,
            'result': result,
            'sub_module': '2_1',
            'flag': flag,
            'record_id': record.id,
            'sql': sql
        }
        return render(request, 'sql_review/result.html', data)
    except MySQLdb.Error as e:
        return HttpResponse('Mysql Error {}: {}'.format(e.args[0], e.args[1]), status=500)


def message_to_review_sql(host, port, sql, option):
    review_sql = """
    /*--user=inception;--password=inception;--host=""" + host + """;--port=""" + str(port) + """;""" + option + """*/
inception_magic_start;
""" + sql + """
inception_magic_commit;    
    """
    return review_sql


class StepView(View):
    def get(self, request):
        instance_groups = MysqlInstanceGroup.objects.all()
        data = {
            'sub_module': '2_1',
            'instance_groups': instance_groups,
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M')
        }
        return render(request, 'sql_review/step.html', data)

    def post(self, request):
        sql_review_form = SqlReviewRecordForm(request.POST)
        if sql_review_form.is_valid():
            result = SqlReviewRecord()
            result.sql = sql_review_form.cleaned_data.get('sql')
            result.for_what = sql_review_form.cleaned_data.get('for_what')
            result.instance = sql_review_form.cleaned_data.get('instance')
            result.instance_group = sql_review_form.cleaned_data.get('instance_group')
            result.execute_time = sql_review_form.cleaned_data.get('execute_time')
            result.save()
            data = {
                'result': 'success',
                'result_id': result.id
            }
            return HttpResponse(json.dumps(data), content_type='application/json')
        else:
            data = {
                'result': 'error'
            }
            return HttpResponse(json.dumps(data), content_type='application/json')


def instance_by_ajax_and_id(request):
    group_id = request.POST.get('group_id', '1')
    instance = MysqlInstance.objects.filter(group=group_id)
    return HttpResponse(serializers.serialize("json", instance), content_type='application/json')


def submitted_list(request):
    # 取出账号权限下所有的审核请求
    record_list = SqlReviewRecord.objects.filter(is_checked=1).order_by('-id')
    data = {
        'record_list': record_list,
        'sub_module': '2_2'
    }
    return render(request, 'sql_review/record_list.html', data)


def modify_submitted_sql(request):
    record = SqlReviewRecord.objects.get(id=request.POST.get('record_id'))
    new_sql = request.POST.get('sql', 'select 1')
    new_record = SqlReviewRecord()
    new_record.sql = new_sql
    new_record.for_what = record.for_what
    new_record.instance = record.instance
    new_record.instance_group = record.instance_group
    new_record.execute_time = record.execute_time
    new_record.save()
    data = {
        'new_id': new_record.id,
        'status': 'success'
    }
    return HttpResponse(json.dumps(data), content_type='application/json')


def sql_execute(request, record_id):
    record = SqlReviewRecord.objects.get(id=record_id)
    sql = record.sql
    instance = record.instance
    instance_ip = instance.ip
    instance_port = instance.port
    # 组成一个inception 可以执行的 sql
    all_the_text = message_to_review_sql(option='--enable-execute;--enable-remote-backup;',
                                         host=instance_ip, port=instance_port, sql=sql)
    try:
        conn = MySQLdb.connect(host=INCEPTION_IP, user='', passwd='', db='', port=INCEPTION_PORT,
                               client_flag=MULTI_STATEMENTS | MULTI_RESULTS)
        cur = conn.cursor()
        ret = cur.execute(all_the_text)
        field_names = [i[0] for i in cur.description]
        result = cur.fetchall()
        # 判断结果中是否有执行成功的状态，如果有则将备份信息存入表中，等待给以后做回滚
        for res in result:
            if res[1] == 'EXECUTED' and res[2] == 0:
                sql_backup_instance = SqlBackupRecord()
                sql_backup_instance.review_record_id = record_id
                sql_backup_instance.backup_db_name = res[8]
                sql_backup_instance.sequence = res[7]
                sql_backup_instance.sql_sha1 = res[10]
                sql_backup_instance.save()
        # 判断结果中是否有error level 为 2 的，如果有，则不做操作，如果没有则将 sql_review_record 记录的 is_executed 设为1
        flag = 'success'
        for res in result:
            if res[2] == 2:
                flag = 'failed'
        if flag == 'success':
            record.is_executed = 1
            record.save()
        cur.close()
        conn.close()
        data = {
            'field_names': field_names,
            'result': result,
            'sub_module': '2_1',
            'record_id': record.id,
            'sql': sql
        }
        return render(request, 'sql_review/execute_result.html', data)
    except MySQLdb.Error as e:
        return HttpResponse('Mysql Error {}: {}'.format(e.args[0], e.args[1]), status=500)


def reviewed_list(request):
    # 取出账号权限下所有的项目经理审核完成列表
    record_list = SqlReviewRecord.objects.filter(is_checked=1, is_reviewed=1).order_by('-id')
    data = {
        'record_list': record_list,
        'sub_module': '2_3',
    }
    return render(request, 'sql_review/reviewed_list.html', data)


def finished_list(request):
    # 取出账号权限下所有的执行完成列表
    record_list = SqlReviewRecord.objects.filter(is_checked=1,is_executed=1).order_by('-id')
    data = {
        'record_list': record_list,
        'sub_module': '2_4',
    }
    return render(request, 'sql_review/finished_list.html', data)


def rollback(request, record_id):
    rollback_list = SqlBackupRecord.objects.filter(review_record_id=record_id)
    for idx, obj in enumerate(rollback_list):
        backup_db = obj.backup_db_name
        sequence = obj.sequence
        sql = 'select * from $_$Inception_backup_information$_$ where `opid_time` = {}'.format(sequence)
        result = get_sql_result(BACKUP_HOST_IP, BACKUP_HOST_PORT, BACKUP_USER, BACKUP_PASSWORD,
                                backup_db,
                                sql)
        rollback_list[idx].sql = result[0][5]
        rollback_list[idx].db_host = result[0][6]
        rollback_list[idx].db_name = result[0][7]
        rollback_list[idx].db_table_name = result[0][8]
    data = {
        'rollback_list': rollback_list
    }
    return render(request, 'sql_review/rollback.html', data)


def get_sql_result(host_ip, host_port, user, password, database, sql):
    try:
        conn = MySQLdb.connect(host=host_ip, user=user, passwd=password, db=database, port=host_port,
                               client_flag=MULTI_STATEMENTS | MULTI_RESULTS)
        cur = conn.cursor()
        ret = cur.execute(sql)
        result = cur.fetchall()
        cur.close()
        conn.close()
        return result
    except MySQLdb.Error as e:
        return 'error'
