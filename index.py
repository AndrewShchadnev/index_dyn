import os
import configparser
import requests
from requests.auth import HTTPBasicAuth
import logging
from logging.handlers import RotatingFileHandler
from argparse import ArgumentParser
from lxml import html
from bs4 import BeautifulSoup
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey

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

# logging
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
    logging.info('GET [wq]: qwe')
    r = requests.get(config['URLS']['INDEX_URL'], auth=HTTPBasicAuth(config['AUTH']['LOGIN'], config['AUTH']['PASS']))
    logging.info('GET {}: {}'.format(r.status_code, r.url))
    tree = html.fromstring(r.text)
    # print(tree.xpath('//title/text()')[0])
    # print(tree.xpath('//tr/td//text()'))
    element_list = list()
    for tbl in tree.xpath('//table'):
        elements = tbl.xpath('.//tr/td//text()')
        element_list.append(elements)

    print(element_list[1])

    #th = ('Server Id', 'Start Time', 'End Time', 'Duration', 'Status', 'Success')
    #super = dict((key,value) for key in th )
    
    engine = create_engine('sqlite:///:memory:', echo=True)



BaseLineStatus()

print("Version SQLAlchemy:", sqlalchemy.__version__)