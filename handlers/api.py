# -*- coding:utf-8 -*-

import tornado.web
import tornado.auth
import tornado.escape
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextSendMessage,ImageSendMessage,TemplateSendMessage,URITemplateAction,MessageTemplateAction,PostbackTemplateAction,ButtonsTemplate
import qrcode
import qrcode.image.svg
from StringIO import StringIO
import json
import random
import requests
import base64
from PIL import Image
import validators
import logging

logger = logging.getLogger('boilerplate.' + __name__)


def insert_callback_log(pgcon,user_id,platform,category_id,shop_id):
    cur = pgcon.cursor()
    cur.execute("""
    INSERT INTO callbacks
    (timestamp,user_id,platform,searched_category_id,result_shop_id)
    VALUES
    (NOW(),%s,%s,%s,%s)
    """,(user_id,platform,category_id,shop_id))

def insert_jump_log(pgcon,user_id,shop_id):
    cur = pgcon.cursor()
    cur.execute("""
    INSERT INTO jumps
    (timestamp,user_id,result_shop_id)
    VALUES
    (NOW(),%s,%s)
    """,(user_id,shop_id))

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

        
class RedirectHandler(BaseHandler):
    @tornado.web.asynchronous
    def get(self,key,user_id):
        try:
            insert_jump_log(self.application.pgcon,user_id,key)
            
            h = self.application.redisdb.hgetall(key)
            if h == None:
                msg = 'Not found for key '+str(key)
                self.write(msg)
                raise tornado.web.HTTPError(400, msg)
            
            url = h['budget']
            if not validators.url(url):
                msg = 'URL ['+str(url)+'] is not valid for key '+str(key)
                self.write(msg)
                raise tornado.web.HTTPError(400,msg)

            self.redirect(url, status=302)
            
        finally:
            self.application.pgcon.commit()
            self.finish()


class ShopSelectableHandler(BaseHandler):
    def select_near_shop_from_redis(self,user_id,latitude,longitude,category_id,timestamp,callback=None):
        DISTANCE_OFFSET = (10.0,'km')
        if category_id == None:
            target_key = 'pos'
        else:
            target_key = 'pos'+str(category_id)
        keyanddists = []
        try:
            keyanddists = self.application.redisdb.georadius(target_key,longitude,latitude,DISTANCE_OFFSET[0],unit=DISTANCE_OFFSET[1],withdist=True)
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
        else: return None

    def select_random_shop_from_redis(self,user_id,category_id,timestamp,callback=None):
        try:
            if category_id == None:
                keys = self.application.redisdb.srandmember('ALL_KEYS',1)
            else:
                keys = self.application.redisdb.srandmember('ALL_CATEGORY'+str(category_id)+'_KEYS',1)
        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            
        if len(keys) > 0:
            key = keys[0]
            dist = None
            h = self.application.redisdb.hgetall(key)
            h['key'] = key
            h['dist'] = dist
            return h
        else: return None

    def register_user_location(self,user_id,latitude,longitude):
        self.application.redisdb.hmset('LOC_'+user_id,{
            'lon':longitude,
            'lat':latitude
        })

    def select_user_location(self,user_id):
        h = self.application.redisdb.hgetall('LOC_'+user_id)
        if h == None or not h.has_key('lat'): return (None,None)
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
            if not o.has_key('latitude'): continue
            if latitude == None: continue
            longitude = o['longitude']
            if not o.has_key('img_base64'): continue
            image_base64 = o['img_base64']
            image_mime = o['img_mime']
            budget = ''
            if o.has_key('budget'): budget = o['budget']
            building_name = ''
            if o.has_key('building_name'): building_name = o['building_name']
            floor_name = ''
            if o.has_key('floor_name'): floor_name = o['floor_name']
            explicit_category_name = ''
            if o.has_key('explicit_category_name'): explicit_category_name = o['explicit_category_name']

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
                'image_height':im_height,
                'budget':budget, 
                'building_name':building_name,
                'floor_name':floor_name,
                'explicit_category_name':explicit_category_name
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
            h = None
            if event.type == 'follow':
                img_url = self.application.self_url+'/static/img/location.png'
                self.application.line_bot_api.reply_message(event.reply_token,TextSendMessage(text='下のOne touch screenを連打してみましょう！'))
                return
            
            elif event.type == 'unfollow':
                self.application.redisdb.delete('LOC_'+str(event.source.user_id))
                return

            elif event.message.type == 'text' and len(event.message.text) >= len('one touch search') and event.message.text[:len('one touch search')] == 'one touch search':
                if len(event.message.text) > len('one touch search'):
                    category_id = event.message.text[len('one touch search'):]
                    
                h = self.select_random_shop_from_redis(user_id,category_id,timestamp)
                
            elif event.message.type == 'text' and len(event.message.text) >= len(RECOMMEND_REGISTERING_LOCATION) and event.message.text[:len(RECOMMEND_REGISTERING_LOCATION)] == RECOMMEND_REGISTERING_LOCATION:
                img_url = self.application.self_url+'/static/img/location.png'
                self.application.line_bot_api.reply_message(event.reply_token,ImageSendMessage(
                    original_content_url=img_url,
                    preview_image_url=img_url
                ))

            if category_id == None: category_id = 0
            if h != None:
                image_url = self.application.self_url+'/image/'+h['key']
                logger.info('Image URL: '+image_url)
                url = 'http://ogiqvo.com/'
                reply = h['explicit_category_name']
                    
                actions = [URITemplateAction(
                    label=u'詳細を見る',
                    uri=url
                )]
                
                insert_callback_log(self.application.pgcon,user_id,'line',category_id,h['floor_name'])
                self.application.line_bot_api.reply_message(event.reply_token,TemplateSendMessage(
                    alt_text=h['name'],
                    template=ButtonsTemplate(
                        thumbnail_image_url=image_url,
                        title=h['name'].decode('UTF-8')[:40], # Limit 40 chars
                        text=reply.decode('UTF-8')[:60], # Limit 60 chars
                        actions=actions
                    )
                ))
                    
            else:
                insert_callback_log(self.application.pgcon,user_id,'line',category_id,'')
                reply = 'Nothing found'
                self.application.line_bot_api.reply_message(event.reply_token,TextSendMessage(text=reply))
                
            self.application.pgcon.commit()

        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            logger.error(e.error.details)
            self.application.pgcon.rollback()

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def post(self):
        self.set_default_headers()
        
        signature = self.request.headers['X-Line-Signature']
        body = self.request.body.decode('UTF-8')

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

            data = {'recipient':{'id':user_id},'message':{'text':'Nothing found.'}}
            h = self.select_random_shop_from_redis(user_id,None,0)
            if h != None:
                result_title = h['name']
                result_content = h['explicit_category_name'][:2000]
                result_str = result_title+"\n"+result_content
                result_str = result_str[:2000] # 2000 is the limit of words
                
                image_url = self.application.self_url+'/image/'+h['key']
                
                data = {
                    'recipient':{'id':user_id},
                    'message':{
                        'attachment':{
                            'type':'template',
                            'payload':{
                                'template_type':'generic',
                                'elements':[
                                    {
                                        'title':result_title,
                                        'subtitle':result_content,
                                        'image_url':image_url,
                                        'default_action':{
                                            'type':'web_url',
                                            'url':'http://ogiqvo.com/',
                                            'messenger_extensions':False,
                                            'webview_height_ratio':'tall'
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
                shop_id = h['floor_name']
            else:
                shop_id = ''

            url = 'https://graph.facebook.com/v2.6/me/messages'
            headers = {'content-type':'application/json'}
            datastr = json.dumps(data)
            params = {'access_token':self.application.messenger_page_access_token}

            insert_callback_log(self.application.pgcon,user_id,'messenger',0,shop_id)
            self.application.pgcon.commit()
            
            r = requests.post(url,params=params,data=datastr,headers=headers)
        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            self.application.pgcon.rollback()
        finally:
            self.finish()

class LogDBInitHandler(BaseHandler):
    def get(self):
        self.write('''<body>
<form action="/log/dbinit" method="POST">
<input type="submit" value="Initialize"/>
</form>
</body>''')

    @tornado.web.asynchronous
    def post(self):
        try:
            cur = self.application.pgcon.cursor()
            cur.execute("""
            CREATE TABLE callbacks
            (id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            user_id TEXT NOT NULL,
            platform VARCHAR(16) NOT NULL,
            searched_category_id INTEGER NOT NULL,
            result_shop_id VARCHAR(16) NOT NULL
            )
            """)
            cur.execute("""
            CREATE TABLE jumps
            (id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            user_id TEXT NOT NULL,
            result_shop_id VARCHAR(16) NOT NULL
            )
            """)
            self.application.pgcon.commit()
            
            self.write('Initialization done.')
        except Exception as e:
            import traceback
            self.application.pgcon.rollback()
            logger.error(traceback.format_exc())
        finally:
            self.finish()

class LogHandler(BaseHandler):
    def get(self):
        self.write('''<body>
<h1>Log admin</h1>
<form action="/log/dump_callback" method="POST">
<input type="submit" value="Export callback log"/>
</form>
<form action="/log/dump_jump" method="POST">
<input type="submit" value="Export jump log"/>
</form>
<br/>
<br/>
<br/>
<br/>
<br/>
<br/>
<form action="/log/delete" method="POST" style="background-color:#f99;color:#fff;">
<p>DANGER ZONE</p>
<input type="submit" value="DELETE ALL LOGS" style="background-color:#f00;color:#fff;"/>
</form>
</body>''')

class LogDumpHandler(BaseHandler):
    @tornado.web.asynchronous
    def post(self,req_type):
        try:
            if req_type == 'callback':
                self.set_header('Content-Type','text/csv')
                self.set_header('Content-disposition','attachment;filename=callbacks.csv')
        
                self.write('utc_timestamp,user_id,platform,searched_category_id,shown_key'+"\n")
                cur = self.application.pgcon.cursor()
                cur.execute("""
                SELECT timestamp,user_id,platform,searched_category_id,result_shop_id
                FROM callbacks
                """)
                for timestamp,user_id,platform,searched_category_id,result_shop_id in cur.fetchall():
                    self.write(str(timestamp)+','+str(user_id)+','+str(platform)+','+str(searched_category_id)+','+str(result_shop_id)+"\n")
                
            elif req_type == 'jump':
                self.set_header('Content-Type','text/csv')
                self.set_header('Content-disposition','attachment;filename=jumps.csv')
        
                self.write('utc_timestamp,user_id,shown_key'+"\n")
                cur = self.application.pgcon.cursor()
                cur.execute("""
                SELECT timestamp,user_id,result_shop_id
                FROM jumps
                """)
                for timestamp,user_id,result_shop_id in cur.fetchall():
                    self.write(str(timestamp)+','+str(user_id)+','+str(result_shop_id)+"\n")

            else:
                self.write('No type '+req_type+' was found')
        finally:
            self.application.pgcon.rollback()
            self.finish()

class LogDeleteHandler(BaseHandler):
    @tornado.web.asynchronous
    def post(self):
        try:
            cur = self.application.pgcon.cursor()

            cur.execute("TRUNCATE TABLE callbacks")
            cur.execute("TRUNCATE TABLE jumps")
             
            self.application.pgcon.commit()
            self.write('Deleted')
        except Exception as e:
            import traceback
            self.application.pgcon.rollback()
            logger.error(traceback.format_exc())
        finally:
            self.finish()

