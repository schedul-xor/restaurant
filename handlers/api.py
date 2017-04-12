# -*- coding:utf-8 -*-

import tornado.web
import tornado.auth
import tornado.escape
from linebot.exceptions import InvalidSignatureError
import qrcode
import qrcode.image.svg
from StringIO import StringIO
from linebot.models import TextSendMessage
import json
import logging

logger = logging.getLogger('boilerplate.' + __name__)


class BaseHandler(tornado.web.RequestHandler):
    """A class to collect common handler methods - all other handlers should
    subclass this one.
    """

    def set_default_headers(self):
        self.set_header('Access-Control-Allow-Origin','*')
        self.set_header("Last-Modified", 'Fri, 05 Sep 2014 22:16:24 GMT')
        self.set_header('Expires','Sun, 17 Jan 2038 19:14:07 GMT')
        self.set_header('Cache-Control','public,max-age=31536000')

        
class TornadoHandler(BaseHandler):
    @tornado.web.asynchronous
    def get(self):
        self.set_default_headers()
        self.write('echo')
        self.finish()

        
class IndexHandler(BaseHandler):
    @tornado.web.asynchronous
    def get(self):
        self.set_default_headers()
        self.write('''<img src="/qrcode"></img>
<ul>
<li><a href="/qrcode">/qrcode</a></li>
</ul>''')
        self.finish()


class PointPostableHandler(BaseHandler):
    @tornado.gen.engine
    def put_in_redis(self,user_id,latitude,longitude,timestamp,callback=None):
        try:
            expires_sec = 3600
            j = {
                'latitude':latitude,
                'longitude':longitude,
                'timestamp':timestamp,
                'user_id':user_id
            }
            r = yield tornado.gen.Task(self.application.redisdb.hmset,user_id,j)
            r = yield tornado.gen.Task(self.application.redisdb.execute_command,'GEOADD','pos',longitude,latitude,user_id)
            r = yield tornado.gen.Task(self.application.redisdb.expire,user_id,expires_sec)
        except Exception as e:
            logger.error(e.message)
            
        if callback:
            callback(False)


class WebhookHandler(PointPostableHandler):
    def initialize(self):
        logger.info('Set default LINE handler')
        
        @self.application.line_handler.default()
        def default(event):
            self.on_message(event)
            
    def on_message(self,event):
        logger.info('Requested '+str(event))
        reply = None
        try:
            if event.message.type != 'location':
                reply = 'location messages are only available, given '+event.message.type

            if event.source.type != 'user':
                reply = 'user sources are only available, given '+event.source.type

            if reply == None:
                user_id = event.source.sender_id
                latitude = event.message.latitude
                longitude = event.message.longitude
                timestamp = event.timestamp
                reply = 'Message from user '+str(user_id)+' at ('+str(latitude)+','+str(longitude)+') '+str(timestamp)
                self.put_in_redis(user_id,latitude,longitude,timestamp)

            self.application.line_bot_api.reply_message(event.reply_token,TextSendMessage(text=reply))

        except Exception as e:
            logger.error(e.message)

    @tornado.web.asynchronous
    @tornado.gen.engine
    def post(self):
        self.set_default_headers()
        
        signature = self.request.headers['X-Line-Signature']
        body = self.request.body.decode('UTF-8')
        logger.info('body='+body+', '+signature)

        try:
            self.application.line_handler.handle(body, signature)

            self.write('OK')
            self.finish()
            
        except InvalidSignatureError as e:
            self.set_status(400)
            self.write(e.message)
            self.finish()

            
class QrCodeHandler(BaseHandler):
    @tornado.web.asynchronous
    def get(self):
        self.set_header('Content-Type','image/svg+xml')
        img = qrcode.make(self.application.line_qrcode_raw_text.decode('UTF-8'),image_factory=qrcode.image.svg.SvgImage)
        output = StringIO()
        img.save(output)
        d = output.getvalue()
        output.close()
        self.write(d)
        self.finish()

        
class PlacesJsonHandler(BaseHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self):
        keys = yield tornado.gen.Task(self.application.redisdb.execute_command,'GEORADIUS','pos',135,35,3000,'km')
        j = {}
        for key in keys:
            logger.info('Found key '+key)
            r = yield tornado.gen.Task(self.application.redisdb.exists,key)
            if r == 0:
                r = yield tornado.gen.Task(self.application.redisdb.zrem,'pos',key)
            else:
                o = yield tornado.gen.Task(self.application.redisdb.hgetall,key)
                if o.has_key('timestamp'):
                    for k in ['timestamp']:
                        o[k] = int(o[k])
                    for k in ['latitude','longitude']:
                        o[k] = float(o[k])
                    j[key] = o
        
        self.set_header('Content-Type','text/json')
        self.write(json.dumps(j,separators=(',', ':')))
        self.finish()

class ForcePostHandler(PointPostableHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def post(self):
        user_id = int(self.request.arguments['user_id'][0])
        latitude = float(self.request.arguments['latitude'][0])
        longitude = float(self.request.arguments['longitude'][0])
        self.put_in_redis(user_id,latitude,longitude,0)

        self.write('OK')
        self.finish()
