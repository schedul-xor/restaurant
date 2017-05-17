import handlers.api

url_patterns = [
    (r'/tornado$',handlers.api.TornadoHandler),
    (r'/?$',handlers.api.IndexHandler),
    (r'/line/qrcode$',handlers.api.LineQrCodeHandler),
    (r'/line/webhook$',handlers.api.LineWebhookHandler),
    (r'/messenger/webhook$',handlers.api.MessengerWebhookHandler),
    (r'/forcepost$',handlers.api.ForcePostHandler),
    (r'/image/(.+)(/\d+)?$',handlers.api.ImageHandler),
    (r'/dbrefresh$',handlers.api.DBRefreshHandler),
    (r'/dbrefresh2$',handlers.api.DBRefresh2Handler),
]
