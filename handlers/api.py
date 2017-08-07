# -*- coding:utf-8 -*-

import tornado.web
import tornado.auth
import tornado.escape
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextSendMessage,TemplateSendMessage,URITemplateAction,MessageTemplateAction,PostbackTemplateAction,ButtonsTemplate
import qrcode
import qrcode.image.svg
from StringIO import StringIO
import json
import random
import requests
import base64
from PIL import Image
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
        self.write('''<h2>Line</h2><img src="/line/qrcode"></img>
<ul>
<li><a href="/line/qrcode">/line/qrcode</a></li>
</ul>''')
        self.finish()


class ShopSelectableHandler(BaseHandler):
    def select_near_shop_from_redis(self,user_id,latitude,longitude,category_id,timestamp,callback=None):
        DISTANCE_OFFSET = (3000.0,'km')
        if category_id == None:
            target_key = 'pos'
        else:
            target_key = 'pos'+str(category_id)
        try:
            keyanddists = self.application.redisdb.execute_command('GEORADIUS',target_key,longitude,latitude,DISTANCE_OFFSET[0],DISTANCE_OFFSET[1],'WITHDIST')
        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            
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
        h = self.application.redisdb.hgetall('LOC_'+user_id)
        if h == None: return (None,None)
        if not h.has_key('lat'): return (None,None)
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
        h = self.select_near_shop_from_redis(user_id,latitude,longitude,None,0)

        self.write(json.dumps(h))
        self.finish()

class ImageHandler(BaseHandler):
    @tornado.web.asynchronous
    def get(self,shop_id,random_suffix):
        j = self.application.redisdb.hgetall(shop_id)
        self.set_header('Content-Type',j['image_mime'])
        b = base64.b64decode(j['image_base64'])
        self.write(b)
        self.finish()

class DBRefreshHandler(BaseHandler):
    def get(self):
        self.write('''<body>
<p>Use <a href="/dbrefresh2">/dbrefresh2</a> for version 2</p>
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

        

class DBRefresh2Handler(BaseHandler):
    def get(self):
        self.write('''<body>
<form enctype="multipart/form-data" action="/dbrefresh2" method="POST">
<input type="file" name="filearg"/>
<input type="submit" value="Submit"/>
</form>
</body>''')

    @tornado.web.asynchronous
    def post(self):
        f = self.request.files['filearg'][0]
        j = json.loads(f['body'])

        # self.application.redisdb.flushall()
        if self.application.redisdb.exists('ALL_KEYS'):
            prev_keys = self.application.redisdb.smembers('ALL_KEYS')
            for key in prev_keys:
                self.application.redisdb.delete(key)
            self.write('Deleted previous '+str(len(prev_keys))+' spot(s)')
            self.application.redisdb.delete('ALL_KEYS')

        
        if self.application.redisdb.exists('ALL_CATEGORIES'):
            prev_categories = self.application.redisdb.smembers('ALL_CATEGORIES')
            for category_id in prev_categories:
                self.application.redisdb.delete('ALL_CATEGORY'+category_id+'_KEYS')
        self.application.redisdb.delete('ALL_CATEGORIES')
        
        self.application.redisdb.delete('pos')

        imported_keys = []
        for i in j:
            o = j[i]

            i = i.replace('/','.')
            
            if o.has_key('name'):
                name = o['name']
            else:
                name = ''
            latitude = o['latitude']
            longitude = o['longitude']
            if not o.has_key('img_base64'):
                continue
            image_base64 = o['img_base64']
            image_mime = o['img_mime']

            category_ids = []
            if o.has_key('category_ids'):
                for category_id in o['category_ids']:
                    category_ids.append(category_id)
                    self.application.redisdb.sadd('ALL_CATEGORIES',category_id)
                    self.application.redisdb.sadd('ALL_CATEGORY'+str(category_id)+'_KEYS',i)
                    self.application.redisdb.execute_command('GEOADD','pos'+str(category_id),longitude,latitude,i)

            img_binary = base64.b64decode(image_base64)
            im = Image.open(StringIO(img_binary))
            im_width,im_height = im.size
                
            h = {
                'name':name,
                'longitude':longitude,
                'latitude':latitude,
                'image_base64':image_base64,
                'image_mime':image_mime,
                'image_width':im_width,
                'image_height':im_height
            }
            self.application.redisdb.hmset(i,h)
            self.application.redisdb.execute_command('GEOADD','pos',longitude,latitude,i)
            self.application.redisdb.sadd('ALL_KEYS',i)
            logger.info('Inserted key '+i)

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
            category_id = None
            latitude = None
            longitude = None
            if event.message.type == 'location':
                reply = 'location messages are only available, given '+event.message.type
                latitude = event.message.latitude
                longitude = event.message.longitude
                self.register_user_location(user_id,latitude,longitude)

            elif event.message.type == 'text' and if len(event.message.text) >= len('one touch search') and event.message.text[:len('one touch search')] == 'one touch search':
                if len(event.message.text) > len('one touch search'):
                    category_id = event.message.text[len('one touch search'):]
                    
                (latitude,longitude) = self.select_user_location(user_id)
                if latitude == None and longitude == None:
                    reply = u'最初に、自分の現在位置を設定してください。'
                    self.application.line_bot_api.reply_message(event.reply_token,TextSendMessage(text=reply))
                    return
                
            h = self.select_near_shop_from_redis(user_id,latitude,longitude,category_id,timestamp)

            if h != None:
                image_url = self.application.self_url+'/image/'+h['key']
                logger.info('Use image '+image_url+' for '+str(h['key']))
                image_width = int(h['image_width'])
                image_height = int(h['image_height'])
                map_url = 'http://maps.google.com/maps?z=15&t=m&q=loc:'+str(h['latitude'])+'+'+str(h['longitude'])
                logger.info('Map url: '+map_url)
                reply = str(int(float(h['dist'])*10.0)/float(10.0))+'km far from here.'
                self.application.line_bot_api.reply_message(event.reply_token,TemplateSendMessage(
                    alt_text=h['name'],
                    template=ButtonsTemplate(
                        thumbnail_image_url=image_url,
                        title=h['name'].decode('UTF-8')[:40], # Limit 40 chars
                        text=reply,
                        actions=[
                            URITemplateAction(
                                label='Map',
                                uri=map_url
                            )
                        ]
                    )
                ))
            else:
                reply = 'No shops found'
                self.application.line_bot_api.reply_message(event.reply_token,TextSendMessage(text=reply))

        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            logger.error(e.error.details)

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
            import traceback
            logger.error(traceback.format_exc())

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

            lat = None
            lon = None
            if attachment0['type'] == 'location':
                coord = attachment0['payload']['coordinates']
                lat = coord['lat']
                lon = coord['long']
                self.register_user_location(user_id,lat,lon)
            else:
                (lat,lon) = self.select_user_location(user_id)
                if lat == None and lon == None:
                    reply = 'Please set your location first.'

            if lat != None and lon != None:
                h = self.select_near_shop_from_redis(user_id,lat,lon,None,0)
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
            import traceback
            logger.error(traceback.format_exc())
        finally:
            self.finish()
