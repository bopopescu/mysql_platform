# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.http.response import HttpResponse

import json
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase

import MySQLdb
from MySQLdb.constants.CLIENT import MULTI_STATEMENTS, MULTI_RESULTS


# Create your views here.


def index(request):
    return HttpResponse('hello django', status=200)


class ResultCallback(CallbackBase):
    def v2_runner_on_ok(self, result, **kwargs):
        host = result._host
        print(json.dumps({host.name: result._result}, indent=4))


def ansible_run(host_list, task_list):
    Options = namedtuple('Options',
                         ['connection', 'module_path', 'forks', 'remote_user', 'private_key_file',
                          'ssh_common_args', 'ssh_extra_args', 'sftp_extra_args', 'scp_extra_args',
                          'become', 'become_method', 'become_user', 'verbosity', 'check'])

    # initialize needed objects
    variable_manager = VariableManager()
    loader = DataLoader()
    options = Options(connection='smart', module_path=None,
                      forks=100, remote_user='root', private_key_file=None, ssh_common_args=None, ssh_extra_args=None,
                      sftp_extra_args=None, scp_extra_args=None, become=None, become_method=None,
                      become_user=None, verbosity=None, check=False
                      )

    passwords = dict(conn_pass='123456')

    # Instantiate our ResultCallback for handling results as they come in
    results_callback = ResultCallback()

    # create inventory and pass to var manager
    inventory = Inventory(loader=loader, variable_manager=variable_manager, host_list=host_list)
    variable_manager.set_inventory(inventory)

    # create play with tasks
    play_source = dict(
        name="Ansible Play",
        hosts='all',
        gather_facts='no',
        tasks=task_list
    )
    play = Play().load(play_source, variable_manager=variable_manager, loader=loader)

    # actually run it
    tqm = None
    try:
        tqm = TaskQueueManager(
            inventory=inventory, variable_manager=variable_manager,
            loader=loader, options=options, passwords=passwords,
            stdout_callback=results_callback,
            # Use our custom callback instead of the ``default`` callback plugin
        )
        result = tqm.run(play)
    finally:
        if tqm is not None:
            tqm.cleanup()


def get_info(request):
    host_list = ['192.168.0.249', '192.168.0.205']
    tasks_list = [
        dict(action=dict(module='shell', args="df -h")),
    ]
    ansible_run(host_list, tasks_list)
    return HttpResponse('hello django', status=200)


def test(request):
    # TODO: 使用原生语句来获取数据库meta信息
    try:
        conn = MySQLdb.connect(host='192.168.0.249', user='root', passwd='mysql*()', db='mysql', port=3306,
                               client_flag=MULTI_STATEMENTS | MULTI_RESULTS)
        cur = conn.cursor()
        ret = cur.execute("SELECT user,host FROM user")
        result = cur.fetchall()
        cur.close()
        conn.close()
        print(result)
    except MySQLdb.Error as e:
        print('Mysql Error %d: %s' % (e.args[0], e.args[1]))
    return HttpResponse('hello django', status=200)
