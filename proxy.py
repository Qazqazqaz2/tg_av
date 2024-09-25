import ssl
import time

import requests
import sqlite3

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager
from requests.packages.urllib3.util import ssl_
from requests import Session
from bs4 import BeautifulSoup as BS
import random

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('auto.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS proxy (id INTEGER PRIMARY KEY, ip varchar not null)')
    conn.commit()
    conn.close()


init_db()

CIPHERS = """ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:AES256-SHA"""


class TlsAdapter(HTTPAdapter):

    def __init__(self, ssl_options=0, **kwargs):
        self.ssl_options = ssl_options
        super(TlsAdapter, self).__init__(**kwargs)

    def init_poolmanager(self, *pool_args, **pool_kwargs):
        ctx = ssl_.create_urllib3_context(ciphers=CIPHERS, cert_reqs=ssl.CERT_REQUIRED, options=self.ssl_options)
        self.poolmanager = PoolManager(*pool_args, ssl_context=ctx, **pool_kwargs)

url = "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
resp = requests.get(url)
http = str(resp.text).split('\n')

while True:
    conn = sqlite3.connect('auto.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM proxy")
    print([(ip) for ip in http])
    cursor.executemany('INSERT INTO proxy (ip) VALUES (?)', [[ip] for ip in http])
    conn.commit()
    time.sleep(40*60)