import os
import configparser
import requests
from requests.auth import HTTPBasicAuth
import logging
from logging.handlers import RotatingFileHandler
from argparse import ArgumentParser
from lxml import html
import re

# Define workdir
workdir = os.path.dirname(os.path.realpath(__file__))

# Define our config file
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(
    os.path.realpath(__file__)), "main.conf"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


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


def BaseLineStatus():
    answer = dict()
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
            else:
                answer = False
    return answer


new_search = BaseLineStatus()

if new_search:
    print('index already started on',
          new_search['inode'], 'in', new_search['time'])
else:
    print('Index not running now')
