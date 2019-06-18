from pathlib import Path
from configparser import ConfigParser
import requests
from requests.auth import HTTPBasicAuth
import logging
from logging.handlers import RotatingFileHandler
from argparse import ArgumentParser
from lxml import html
import re
import time

# Define workdir
workdir = Path(__file__).resolve().parent

# Define our config file
config = ConfigParser()
config.read(workdir / "main.conf")


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
                else:
                    answer = False
        return answer


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


new_search = BaseLineStatus()

if new_search:
    print('index already started on',
          new_search['inode'], 'in', new_search['time'])
    while BaseLineStatusByElement(new_search)['Status'] == 'PENDING':
        print(BaseLineStatusByElement(new_search))
        time.sleep(10)
    print(BaseLineStatusByElement(new_search))
else:
    print('Index not running now')
