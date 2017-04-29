# -*- coding:utf-8 -*-

import tornado.web
import tornado.auth
import tornado.escape
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextSendMessage
import qrcode
import qrcode.image.svg
from StringIO import StringIO
import json
import logging
import random
import requests

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
        self.write('''<h2>Line</h2><img src="/line/qrcode"></img>
<ul>
<li><a href="/line/qrcode">/line/qrcode</a></li>
</ul>''')
        self.finish()


class ShopSelectableHandler(BaseHandler):
    def select_near_shop_from_redis(self,user_id,latitude,longitude,timestamp,callback=None):
        try:
            keyanddists = self.application.redisdb.execute_command('GEORADIUS','pos',longitude,latitude,3000,'km','WITHDIST')
        except Exception as e:
            logger.error(e.message)
            
        if len(keyanddists) > 0:
            keyanddist = random.choice(keyanddists)

            key = keyanddist[0]
            dist = float(keyanddist[1])
            h = self.application.redisdb.hgetall(key)
            h['key'] = key
            h['dist'] = dist
            return h
        else:
            return None

    def register_user_location(self,user_id,latitude,longitude):
        self.application.redisdb.hmset('LOC_'+user_id,{
            'lon':longitude,
            'lat':latitude
        })

    def select_user_location(self,user_id):
        h = self.application.redisdb.hmget('LOC_'+user_id)
        if h == None: return (None,None)
        lat = float(h['lat'])
        lon = float(h['lon'])
        return (lat,lon)

class ForcePostHandler(ShopSelectableHandler):
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def post(self):
        user_id = int(self.request.arguments['user_id'][0])
        latitude = float(self.request.arguments['latitude'][0])
        longitude = float(self.request.arguments['longitude'][0])
        h = self.select_near_shop_from_redis(user_id,latitude,longitude,0)

        self.write(json.dumps(h))
        self.finish()

class DBRefreshHandler(BaseHandler):
    def get(self):
        self.write('''<body>
<form enctype="multipart/form-data" action="/dbrefresh" method="POST">
<input type="file" name="filearg"/>
<input type="submit" value="Submit"/>
</form>
</body>''')

    @tornado.web.asynchronous
    def post(self):
        f = self.request.files['filearg'][0]
        j = json.loads(f['body'])

        self.application.redisdb.flushall()
        
        for i in j:
            o = j[i]
            name = o[0]
            latitude = o[1]
            longitude = o[2]
            h = {
                'name':name,
                'longitude':longitude,
                'latitude':latitude
            }
            self.application.redisdb.hmset(i,h)
            self.application.redisdb.execute_command('GEOADD','pos',longitude,latitude,i)

        self.write('Imported '+str(len(j))+' spot(s)')
        self.finish()

        
class LineWebhookHandler(ShopSelectableHandler):
    def initialize(self):
        logger.info('Set default LINE handler')
        
        @self.application.line_handler.default()
        def default(event):
            self.on_message(event)
            
    def on_message(self,event):
        logger.info('Requested '+str(event))
        reply = None
        try:
            if event.source.type != 'user':
                reply = 'user sources are only available, given '+event.source.type
                self.application.line_bot_api.reply_message(event.reply_token,TextSendMessage(text=reply))
                return

            timestamp = event.timestamp
            user_id = event.source.sender_id
            latitude = None
            longitude = None
            if event.message.type == 'location':
                reply = 'location messages are only available, given '+event.message.type
                latitude = event.message.latitude
                longitude = event.message.longitude
                self.register_user_location(user_id,latitude,longitude)
                
            elif event.message.type == 'text' and event.message.text == 'one touch search':
                (latitude,longitude) = self.select_user_location(user_id)
                if latitude == None and longitude == None:
                    reply = 'Please set your location first.'
                    self.application.line_bot_api.reply_message(event.reply_token,TextSendMessage(text=reply))
                    return
                
            h = self.select_near_shop_from_redis(user_id,latitude,longitude,timestamp)

            logger.info('Found'+str(h))
            if h != None:
                reply = 'How about '+h['name']+' which is '+str(h['dist'])+'km far from here? http://maps.google.com/maps?z=15&t=m&q=loc:'+str(h['latitude'])+'+'+str(h['longitude'])
            else:
                reply = 'No shops found'

            self.application.line_bot_api.reply_message(event.reply_token,TextSendMessage(text=reply))

        except Exception as e:
            logger.error(e.message)

    @tornado.web.asynchronous
    @tornado.gen.coroutine
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

        
class LineQrCodeHandler(BaseHandler):
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

        
class MessengerWebhookHandler(ShopSelectableHandler):
    @tornado.web.asynchronous
    def get(self):
        if self.get_argument('hub.verify_token','') == self.application.messenger_verify_token:
            self.write(self.get_argument('hub.challenge',''))
        else:
            self.write('Wrong')
        self.finish()

    @tornado.web.asynchronous
    def post(self):
        logger.info('Received data '+self.request.body)
        data = json.loads(self.request.body)

        try:
            entry0 = data['entry'][0]
            m0 = entry0['messaging'][0]
            user_id = m0['sender']['id']
            message = m0['message']
            mid = message['mid']
            attachments = message['attachments']
            attachment0 = attachments[0]

            if attachment0['type'] != 'location':
                reply = 'Type '+attachment0['type']+' is not allowed'
            else:
                coord = attachment0['payload']['coordinates']
                lat = coord['lat']
                lon = coord['long']
                h = self.select_near_shop_from_redis(user_id,lat,lon,0)
                if h != None:
                    reply = 'How about '+h['name']+' which is '+str(h['dist'])+'km far from here? http://maps.google.com/maps?z=15&t=m&q=loc:'+str(h['latitude'])+'+'+str(h['longitude'])
                else:
                    reply = 'No shops found'

            url = 'https://graph.facebook.com/v2.6/me/messages'
            headers = {'content-type':'application/json'}
            data = {'recipient':{'id':user_id},'message':{'text':reply}}
            datastr = json.dumps(data)
            params = {'access_token':self.application.messenger_page_access_token}
            logger.info('Request '+url+' '+datastr+' '+json.dumps(params))
            
            r = requests.post(url,params=params,data=datastr,headers=headers)
            logger.info('Reply '+r.text)
        except Exception as e:
            logger.error(e.message)
        finally:
            self.finish()
