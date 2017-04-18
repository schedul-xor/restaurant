import handlers.api

url_patterns = [
    (r'/tornado$',handlers.api.TornadoHandler),
    (r'/?$',handlers.api.IndexHandler),
    (r'/line/qrcode$',handlers.api.LineQrCodeHandler),
    (r'/line/webhook$',handlers.api.LineWebhookHandler),
    (r'/forcepost$',handlers.api.ForcePostHandler),
    (r'/dbrefresh$',handlers.api.DBRefreshHandler),
]
