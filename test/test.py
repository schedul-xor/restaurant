#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os
import requests
from logging import getLogger, StreamHandler, DEBUG
logger = getLogger(__name__)
handler = StreamHandler()
handler.setLevel(DEBUG)
logger.setLevel(DEBUG)
logger.addHandler(handler)

logger.debug('Init git db')

URL_PREFIX = 'http://localhost:8888/'
SQLITE3_PATH = '/home/xor/local/m/p/w/shonanmonorail-commit/tmp/commit.sqlite'
BRANCH_NAME = 'test-branch'

logger.debug('Initialize environment')
r = requests.post(URL_PREFIX+'init_env')

logger.debug('Create branch')
r = requests.post(URL_PREFIX+'branch',data={'branch':BRANCH_NAME})

logger.debug('Post SQLite3 file')
r = requests.post(URL_PREFIX+'commit',data={'branch':BRANCH_NAME,},files={
    'filearg':('commit.sqlite',open(SQLITE3_PATH))
})
print r.text
