#!/usr/bin/env python
# -*- coding: utf-8 -*-
import model
from sqlalchemy import *
import configparser
import os

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(
    os.path.realpath(__file__)), "main.conf"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, config['MAIN']['DDB_LINK'])

engine = create_engine('sqlite:///' + db_path, echo=False)
model.metadata.create_all(engine)
