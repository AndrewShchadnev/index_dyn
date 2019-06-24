from pathlib import Path
from configparser import ConfigParser
import requests
import json
from requests.auth import HTTPBasicAuth
import logging
from logging.handlers import RotatingFileHandler
from argparse import ArgumentParser
from lxml import html
import re
import time
from slackclient import SlackClient
import os
import test
from threading import Thread


# Define workdir
workdir = Path(__file__).resolve().parent

# Define our config file
config = ConfigParser()
config.read(workdir / "main.conf")

PROXIES = dict(http=config['PROXIES']['HTTP'],
               https=config['PROXIES']['HTTPS'])

SLACK_BOT_TOKEN = config['DEFAULT']['SLACK_BOT_TOKEN']
BOT_NAME = config['DEFAULT']['BOT_NAME']
BOT_ID = config['DEFAULT']['BOT_ID']
BOT_COMMAND = "<@" + BOT_ID + ">"         

help_message = 'Бот используется для получения статуса и запуска индекс на среде prod  и stage.'
help_message = 'Введите prod или stage для указания среды'
help_message = 'Пример @indexbot prod'

slack_client = SlackClient(SLACK_BOT_TOKEN, proxies=PROXIES)

pidfile = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), 'indexbot.pid')
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



# Preparing arguments
argparser = ArgumentParser(description="BaseLineIndexClient")
argparser.add_argument(
    '-d', '--debug', help='debug output', action="store_true")
args = argparser.parse_args()

# Определяем тип логгирования
if args.debug:
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        level='DEBUG'
    )
else:
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        level='INFO',
        handlers=[
            RotatingFileHandler(
                filename=(workdir / 'log.log').as_posix(),
                maxBytes=config['LOG_ROTATE'].getint('MaxBytes', fallback=1024),
                backupCount=config['LOG_ROTATE'].getint('BackupCount', fallback=2)
            )]
    )

pattern_c = re.compile(r't2ru-ds(-2)?-prod-[0-11]*\+production')

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


class d_job(Thread):
    def __init__(self, command, channel):
        Thread.__init__(self)
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


        def BaseLineStatus(isStage=False):
            answer = dict()
            if isStage:
                r = requests.get(
                    config['URLS_STAGE']['INDEX_URL_STAGE'],
                    auth=HTTPBasicAuth(
                        config['AUTH']['LOGIN'],
                        config['AUTH']['PASS']))
            else:
                r = requests.get(
                    config['URLS']['INDEX_URL'],
                    auth=HTTPBasicAuth(
                        config['AUTH']['LOGIN'],
                        config['AUTH']['PASS']))
                logging.info('GET {}: {}'.format(r.status_code, r.url))
                tree = html.fromstring(r.text)
                for tbl in tree.xpath('//table'):
                    elements = tbl.xpath('.//tr/td//text()')
                    if pattern_c.search(str(elements)):
                        if elements.count('PENDING') > 0:
                            pos = elements.index('PENDING')
                            answer['inode'] = elements[pos - 4]
                            answer['time'] = elements[pos - 3]
                            answer = 'Индекс запущен'
                        else:
                            answer = 'Индекс не запущен'
                return answer
        
        if goal == 'help':
            response = help_message
            logging.info("help_message output")
        elif goal == 'index':
            if target == 'stage':
                new_search = test.BaseLineStatus(True)
            else:
                new_search = test.BaseLineStatus()
            if new_search:
                response = 'index already started on {} in {}'.format(
                    new_search['inode'], new_search['time'])
            else:
                response = 'Index not running now'
        else:
            response = help_message

        slack_client.api_call("chat.postMessage", channel=self.channel,
                              text=response, as_user=False, username=BOT_NAME, icon_emoji=":robot_face:") 


class slack_poller(Thread):
    def __init__(self, command, channel):
        Thread.__init__(self)
        self.daemon = False
        self.name = "job"
        self.command = command
        self.channel = channel


        def BaseLineStatusByElement(dictin):
            if dictin is False:
                answer = False
            else:
                answer = dictin
                r = requests.get(
                    config['URLS']['INDEX_URL'],
                    auth=HTTPBasicAuth(
                        config['AUTH']['LOGIN'],
                        config['AUTH']['PASS']))
                logging.info('GET {}: {}'.format(r.status_code, r.url))
                tree = html.fromstring(r.text)
                for tbl in tree.xpath('//table'):
                    elements = tbl.xpath('.//tr/td//text()')
                    if pattern_c.search(str(elements)):
                        flag = True
                        start = 0
                        while flag is True:
                            try:
                                pos = elements.index(dictin['inode'], start)
                            except ValueError:
                                flag = False
                                answer = False
                            if elements[pos + 1] == dictin['time']:
                                answer['Success'] = elements[pos + 5]
                                answer['Status'] = elements[pos + 4]
                                answer['Duration'] = elements[pos + 3]
                                answer['End Time'] = elements[pos + 2]
                                flag = False
                            else:
                                start = pos + 1
            return answer


new_search = test.BaseLineStatus()

print(new_search)

webhook_url = 'https://hooks.slack.com/services/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'

headers = {'Content-type': 'application/json'}

slack_data = {'text': "Hello, World!"}

response = requests.post(
    webhook_url, data=json.dumps(slack_data),
    headers={'Content-Type': 'application/json'}
)    



#if new_search:
#    print('index already started on',
#          new_search['inode'], 'in', new_search['time'])
#    while BaseLineStatusByElement(new_search)['Status'] == 'PENDING':
#        print(BaseLineStatusByElement(new_search))
#        time.sleep(10)
#    print(BaseLineStatusByElement(new_search))
#else:
#    print('Index not running now')
##