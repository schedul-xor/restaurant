#!/usr/bin/env python

import tornado.httpserver
import tornado.ioloop
import tornado.web
from tornado.options import options
import redis
import urlparse
import psycopg2

from settings import settings
from urls import url_patterns
import logging
from linebot import LineBotApi,WebhookHandler

logger = logging.getLogger('boilerplate.' + __name__)

class TornadoBoilerplate(tornado.web.Application):
    def __init__(self):
        self.redisdb = self.create_redis_client()
        
        self.pgcon = self.create_pg_client()
        
        self.line_bot_api = LineBotApi(options.line_channel_access_token)
        self.line_handler = WebhookHandler(options.line_channel_secret)
        self.line_qrcode_raw_text = options.line_qrcode_raw_text

        self.self_url = options.self_url

        self.messenger_verify_token = options.messenger_verify_token
        self.messenger_page_access_token = options.messenger_page_access_token
            
        # Initialize application
        tornado.web.Application.__init__(self, url_patterns, **settings)

    def create_redis_client(self):
        o = urlparse.urlparse(options.redis_url)
        return redis.StrictRedis(
            host=o.hostname,
            port=o.port,
            password=o.password,
            db=0
        )

    def create_pg_client(self):
        o = urlparse.urlparse(options.database_url)
        username = o.username
        password = o.password
        database = o.path[1:]
        hostname = o.hostname
        return psycopg2.connect(
            database = database,
            user = username,
            password = password,
            host = hostname
        )

def main():
    app = TornadoBoilerplate()

    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(options.port)
    # Start I/O loop
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()
