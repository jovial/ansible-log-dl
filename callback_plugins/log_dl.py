# (C) 2012, Michael DeHaan, <michael.dehaan@gmail.com>
# (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)

from ansible.playbook.task_include import TaskInclude
from collections import Iterable

__metaclass__ = type

DOCUMENTATION = '''
    callback: log_dl
    type: notification
    short_description: write list of downloaded files to log file
    version_added: historical
    description:
      - This callback tries to determine all downloaded files and writes them, on a per host basis, to `/tmp/log/ansible/host/<host>/dl`
    requirements:
     - A writeable /tmp/log/ansible/hosts directory by the user executing Ansible on the controller
'''

import os
import time
import json
from collections import MutableMapping

from ansible.module_utils._text import to_bytes
from ansible.plugins.callback import CallbackBase


# NOTE: in Ansible 1.2 or later general logging is available without
# this plugin, just set ANSIBLE_LOG_PATH as an environment variable
# or log_path in the DEFAULTS section of your ansible configuration
# file.  This callback is an example of per hosts logging for those
# that want it.


class CallbackModule(CallbackBase):
    """
    logs playbook results, per host, in /var/log/ansible/hosts
    """
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'log_dl'
    CALLBACK_NEEDS_WHITELIST = False

    TIME_FORMAT = "%b %d %Y %H:%M:%S"
    MSG_FORMAT = "%(now)s - %(category)s - %(data)s\n\n"

    def __init__(self):

        super(CallbackModule, self).__init__()

        self.not_handled = set()

        if not os.path.exists("/tmp/log/ansible/hosts"):
            os.makedirs("/tmp/log/ansible/hosts")

    def log(self, host, category, data):
        if isinstance(data, MutableMapping):
            if '_ansible_verbose_override' in data:
                # avoid logging extraneous data
                data = 'omitted'
            else:
                data = data.copy()
                invocation = data.pop('invocation', None)
                data = json.dumps(data)
                if invocation is not None:
                    data = json.dumps(invocation) + " => %s " % data

        path = os.path.join("/tmp/log/ansible/hosts", host)
        now = time.strftime(self.TIME_FORMAT, time.localtime())

        msg = to_bytes(self.MSG_FORMAT % dict(now=now, category=category, data=data))
        with open(path, "ab") as fd:
            fd.write(msg)

    def playbook_on_play_start(self, name):
        #self.current_playbook = name
        #self._log_dl_play("#playbook: {}".format(name))
        pass

    @staticmethod
    def _create_host_dir(host):
        path = os.path.join("/tmp/log/ansible/hosts", host.name)
        if not os.path.exists(path):
            os.makedirs(path)


    @staticmethod
    def _log_dl(host, proto, src):
        CallbackModule._create_host_dir(host)
        if isinstance(src, Iterable):
            src = " ".join(src)
        path = os.path.join("/tmp/log/ansible/hosts", host.name, "dl")
        with open(path, "a+") as f:
            print("{proto}: {src}".format(proto=proto,src=src), file=f)

    @staticmethod
    def _log_dl_play(host, line):
        CallbackModule._create_host_dir(host)
        path = os.path.join("/tmp/log/ansible/hosts", host.name, "dl")
        with open(path, "a+") as f:
            print(line, file=f)

    def _handle_action_get_url(self, host, args):
        self._log_dl(host, "http", args["url"])

    def _handle_action_pip(self, host, args):
        requirements = args["requirements"]
        if requirements:
            with open(requirements, "r") as f:
                self._log_dl(host, "pip", f.readlines())
        else:
            self._log_dl(host, "pip", args["name"])

    def _handle_action_yum(self, host, args):
        self._log_dl(host, "yum", args["name"])

    def _handle_action_package(self, host, args):
        # TODO: is "dest" not None, like requirments in
        # pip
        if "dest" in args:
            with open(args["dest"], "r") as f:
                self._log_dl(host, "yum", f.readlines())
        else:
            self._log_dl(host, "yum", args["name"])

    def _handle_action_git(self, host, args):
        self._log_dl(host, "git", args["repo"])

    def _handle_action_fetch(self, host, args):
        self._log_dl(host, "http", args["src"])

    def _handle_action_command(self, host, args):
        self._default_cmd_handler(host, args)

    def _default_action_handler(self, host, action, args):
        #print("not handled: " + task.action)
        #self.not_handled.add(task.action)
        with open("/tmp/log/ansible/not_handled", "a+") as f:
            print(action, file=f)

    def _default_cmd_handler(self, host, cmd):
        with open("/tmp/log/ansible/cmd_not_handled", "a+") as f:
            print(cmd, file=f)

    def v2_playbook_on_task_start(self, task, is_conditional):
        #print("running task:" + task.name)
        #print(task.get_ds())
        #print(task.action)
        self.task = task
        #handler_method = getattr(self, "_handle_action_" + task.action, None)
        #handler_method(task, is_conditional)

    def v2_playbook_on_stats(self, stats):
        #print("playbook: " + self.current_playbook)
        #print("not handled: " + repr(self.not_handled))
        pass

    def runner_on_failed(self, host, res, ignore_errors=False):
        #self.log(host, 'FAILED', res)
        pass

    def runner_on_ok(self, host, res):
        #print(res)
        #self.log(host, 'OK', res)
        #print(self.task)
        #self.task.get_name()
        #print(res)
        pass

    def _dispatch_action(self, host, action, result):
        if "invocation" not in result:
            return
        invocation = result["invocation"]
        args = invocation["module_args"]
        handler_method = self.get_action_handler(action)
        if handler_method:
            handler_method(host, args)
        else:
            self._default_action_handler(host, action, args)

    def get_action_handler(self, action):
        return getattr(self, "_handle_action_" + action, None)

    def v2_runner_on_ok(self, result):
        task = result._task
        task_result = result._result
        host = result._host
        #print(task.)
        action = task.action
        if self.get_action_handler(action):
            self._log_dl_play(host, "# task: {}".format(task.name))
        #print("the action was: " + result._task.action)
        if task.loop and "results" in task_result:
            # handle with_items separately
            for x in task_result["results"]:
                self._dispatch_action(host, action, x)
        else:
            self._dispatch_action(host, action, task_result)

    def v2_runner_item_on_ok(self, result):
        if isinstance(result._task, TaskInclude):
            print("skipping include task")
            return
        task = result._task
        task_result = result._result
        host = result._host
        action = task.action
        self._dispatch_action(host, action, task_result)

    def runner_on_skipped(self, host, item=None):
        #self.log(host, 'SKIPPED', '...')
        pass

    def runner_on_unreachable(self, host, res):
        #self.log(host, 'UNREACHABLE', res)
        pass

    def runner_on_async_failed(self, host, res, jid):
        #self.log(host, 'ASYNC_FAILED', res)
        pass

    def playbook_on_import_for_host(self, host, imported_file):
        #self.log(host, 'IMPORTED', imported_file)
        pass

    def playbook_on_not_import_for_host(self, host, missing_file):
        #self.log(host, 'NOTIMPORTED', missing_file)
        pass
