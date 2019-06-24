#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import time
import threading
import logging
from logging.handlers import RotatingFileHandler
import requests
from slackclient import SlackClient
from sqlalchemy import *
import test
import configparser

# Define workdir
workdir = os.path.dirname(os.path.realpath(__file__))

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(
    os.path.realpath(__file__)), "main.conf"))

PROXIES = dict(http=config['PROXIES']['HTTP'],
               https=config['PROXIES']['HTTPS'])

SLACK_BOT_TOKEN = config['DEFAULT']['SLACK_BOT_TOKEN']
BOT_NAME = config['DEFAULT']['BOT_NAME']
BOT_ID = config['DEFAULT']['BOT_ID']
BOT_COMMAND = "<@" + BOT_ID + ">"

help_message = '\n'.join(['*Help:*\n'])
help_message = help_message + '\n '
help_message = help_message + config['HELP']['HELP_INDEX_PROD'] + '\n'
help_message = help_message + config['HELP']['HELP_INDEX_STAGE'] + '\n'
help_message = help_message + config['HELP']['HELP_INDEX_PROD_RUN'] + '\n'
help_message = help_message + config['HELP']['HELP_INDEX_STAGE_RUN'] + '\n'

slack_client = SlackClient(SLACK_BOT_TOKEN, proxies=PROXIES)

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level='INFO',
    handlers=[
        RotatingFileHandler(
            filename=os.path.join(workdir, 'log.log'),
            maxBytes=int(config['LOG_ROTATE']['MaxBytes']),
            backupCount=int(config['LOG_ROTATE']['BackupCount'])
        )]
)

for user in slack_client.api_call("users.list")['members']:
    if user['name'] == BOT_NAME:
        BOT_ID = user['id']
        break


def check_pid(pid):
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    else:
        return True


pidfile = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), 'T2bot.pid')
if os.path.isfile(pidfile):
    with open(pidfile, 'r') as pidfile_obj:
        last_pid = pidfile_obj.read()
    if check_pid(last_pid):
        print("Already running: " + last_pid)
        exit(1)
    else:
        with open(pidfile, 'w') as pidfile_obj:
            pidfile_obj.write(str(os.getpid()))
else:
    with open(pidfile, 'w') as pidfile_obj:
        pidfile_obj.write(str(os.getpid()))


class d_job(threading.Thread):
    def __init__(self, command, channel):
        threading.Thread.__init__(self)
        self.daemon = False
        self.name = "job"
        self.command = command
        self.channel = channel

    def run(self):
        command = self.command.split()
        # get number elements in command: [botname] <goal> [target]
        command_length = len(command)

        goal = ''
        target = ''

        # Check bot_name in command and define variables
        if command[0].strip().lower().startswith("<@"):
            goal = command[1].strip().lower()
            if command_length > 2:
                target = command[2].strip().lower()
        else:
            goal = command[0].strip().lower()
            if command_length > 1:
                target = command[1].strip().lower()

        def BaseLineStatus(IsStage=False):
            answer = dict()
            if IsStage is True:
                r = requests.get(config['URLS']['INDEX_URL_STAGE'], auth=HTTPBasicAuth(
                    config['AUTH']['LOGIN'], config['AUTH']['PASS']))
            else:
                r = requests.get(config['URLS']['INDEX_URL'], auth=HTTPBasicAuth(
                    config['AUTH']['LOGIN'], config['AUTH']['PASS']))
                logging.info('GET {}: {}'.format(r.status_code, r.url))
                tree = html.fromstring(r.text)
                for tbl in tree.xpath('//table'):
                    elements = tbl.xpath('.//tr/td//text()')
                    pattern = r"t2ru-ds(-2)?-prod-[0-11]*\+production"
                    if re.search(pattern, str(elements)):
                        if elements.count('PENDING') > 0:
                            pos = elements.index('PENDING')
                            answer['inode'] = elements[pos - 4]
                            answer['time'] = elements[pos - 3]
                            answer = 'yew index now'
                        else:
                            answer = 'no index now'
                return answer

        if goal == 'help':
            response = help_message
            logging.info("help_message output")
        elif goal == 'tariffs':
            response = tariffs()
        elif goal == 'index':
            response = ''
            if target == 'stage':
                new_search = test.BaseLineStatus(True)
            elif target == '':
                new_search = test.BaseLineStatus()

            elif target == 'run':
                new_search = test.BaseLineStatus()
                if new_search is False:
                    test.StartBaseLine()
                    response = '`Index starting on PROD`' + '\n '
                    new_search = test.BaseLineStatus()
                    if new_search is False:
                        response = '`Unknown error`'
                else:
                    response = '`Index not starting on PROD`' + '\n '

            elif target == 'run.stage':
                new_search = test.BaseLineStatus(True)
                if new_search is False:
                    test.StartBaseLine(True)
                    response = '`Index starting on STAGE`' + '\n '
                    new_search = test.BaseLineStatus(True)
                    if new_search is False:
                        response = '`Unknown error`'
                else:
                    response = '`Index not starting on STAGE`' + '\n '
            logging.info(new_search)
            if new_search:
                response = response + 'Index already started on {} in {}'.format(
                    new_search['inode'], new_search['time'])
            else:
                response = 'Index not running now'
        else:
            response = help_message

        slack_client.api_call("chat.postMessage", channel=self.channel,
                              text=response, as_user=False, username=BOT_NAME, icon_emoji=":robot_face:")


class slack_poller(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = False
        self.name = "poller"

    def run(self):
        def parse_slack_output(slack_rtm_output):
            output_list = slack_rtm_output
            if output_list and len(output_list) > 0:
                for output in output_list:
                    if (
                        output and
                        'text' in output and
                        (
                            BOT_COMMAND in output['text'] or
                            output['channel'].startswith('D')) and
                        output['type'] == 'message' and
                        ('subtype' not in output or output['subtype']
                         != 'bot_message')
                    ):
                        if output['channel'].startswith('D'):
                            command = output['text']
                        else:
                            command = output['text'].split(BOT_COMMAND)[
                                1].strip()
                        return command, output['channel']
            return None, None
        if slack_client.rtm_connect():
            logging.info("Bot connected and running!")
            while True:
                try:
                    command, channel = parse_slack_output(
                        slack_client.rtm_read())
                except:
                    logging.exception("communicating with Slack")
                    exit(7)
                if command and channel:
                    logging.info("found command: %s" % command)
                    run_job = d_job(command, channel)
                    run_job.start()
                time.sleep(1)
        else:
            logging.error("Connection failed. Invalid Slack token or bot ID?")
            exit(1)


main_poller = slack_poller()
main_poller.start()
print('Process has been started!')
