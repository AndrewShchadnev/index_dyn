import os
import configparser
import requests
from requests.auth import HTTPBasicAuth
import logging
from logging.handlers import RotatingFileHandler
from argparse import ArgumentParser
from lxml import html
import re
import time
from threading import Thread
import json

# Define workdir
workdir = os.path.dirname(os.path.realpath(__file__))

# Define our config file
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(
    os.path.realpath(__file__)), "main.conf"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROXIES = dict(http=config['PROXIES']['HTTP'],
               https=config['PROXIES']['HTTPS'])

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
                filename=os.path.join(workdir, 'log.log'),
                maxBytes=int(config['LOG_ROTATE']['MaxBytes']),
                backupCount=int(config['LOG_ROTATE']['BackupCount'])
            )]
    )


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
        pattern = r"t2ru-ds(-2)?-(prod|staging)-[0-11]*\+(production|staging)"
        if re.search(pattern, str(elements)):
            if elements.count('PENDING') > 0:
                pos = elements.index('PENDING')
                answer['inode'] = elements[pos - 4]
                answer['time'] = elements[pos - 3]
            else:
                answer = False
    return answer


def BaseLineStatusByElement(dictin, IsStage=False):
    if dictin is False:
        answer = False
    else:
        answer = dictin
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
            pattern = r"t2ru-ds(-2)?-(prod|staging)-[0-11]*\+(production|staging)"
            if re.search(pattern, str(elements)):
                flag = True
                start = 0
                while flag is True:
                    try:
                        pos = elements.index(dictin['inode'], start)
                    except ValueError:
                        flag = False
                        answer = False
                    if elements[pos + 1] == dictin['time']:
                        # answer['Success'] = elements[pos + 5]
                        answer['Status'] = elements[pos + 4]
                        answer['Success'] = elements[pos + 5]
                        # answer['Duration'] = elements[pos + 3]
                        # answer['End Time'] = elements[pos + 2]
                        flag = False
                    else:
                        start = pos + 1
    return answer


def send_slack(msg):
    if msg != '':
        body = json.dumps({"text": str(msg)})
        response = requests.post(
            config['DEFAULT']['WEBHOOK_URL'],
            proxies=PROXIES,
            data=body,
            headers={'Content-Type': 'application/json'}
        )
        logging.info('POST {}: {}, {}'.format(response.status_code, response.url, body))
        if response.status_code != 200:
            raise ValueError('Request to slack returned an error %s, the response is:\n%s' % (
                response.status_code, response.text))


def chekking(dictin, IsStage=False):
    logging.info('Запуск чеккинга')
    while BaseLineStatusByElement(dictin, IsStage)['Status'] == 'PENDING':
        logging.info('BaseLineStatusByElement : {}'.format(
            BaseLineStatusByElement(dictin, IsStage)))
        time.sleep(10)
    logging.info('BaseLineStatusByElement : {}'.format(
        BaseLineStatusByElement(dictin, IsStage)))
    send_slack(str(BaseLineStatusByElement(dictin, IsStage)))


def StartBaseLine(IsStage=False):
    answer = dict()
    body = {'baselineAction': 'Baseline Index',
            'activelyIndexing': 'false', 'submitted': 'true'}
    if IsStage is True:
        r = requests.post(config['URLS']['INDEX_START_STAGE'], auth=HTTPBasicAuth(
            config['AUTH']['LOGIN'], config['AUTH']['PASS']), data=body)
    else:
        r = requests.post(config['URLS']['INDEX_START'], auth=HTTPBasicAuth(
            config['AUTH']['LOGIN'], config['AUTH']['PASS']), data=body)
    logging.info('POST {}: {}, {}'.format(r.status_code, r.url, body))
    if r.status_code == 200:
        new_search = BaseLineStatus(IsStage)
        thread = Thread(target=chekking, args=(new_search, IsStage))
        thread.start()
