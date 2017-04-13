#!/usr/bin/env python

import tornado.httpserver
import tornado.ioloop
import tornado.web
from tornado.options import options
import redis
import urlparse

from settings import settings
from urls import url_patterns
import logging
from linebot import LineBotApi,WebhookHandler

logger = logging.getLogger('boilerplate.' + __name__)

class TornadoBoilerplate(tornado.web.Application):
    def __init__(self):
        self.redisdb = self.create_client()
        
        self.line_bot_api = LineBotApi(options.line_channel_access_token)
        self.line_handler = WebhookHandler(options.line_channel_secret)
        self.line_qrcode_raw_text = options.line_qrcode_raw_text
            
        # Initialize application
        tornado.web.Application.__init__(self, url_patterns, **settings)

    def create_client(self):
        o = urlparse.urlparse(options.redis_url)
        return redis.StrictRedis(
            host=o.hostname,
            port=o.port,
            password=o.password,
            db=3
        )

def main():
    app = TornadoBoilerplate()

    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(options.port)
    # Start I/O loop
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()
