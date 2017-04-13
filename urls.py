import handlers.api

url_patterns = [
    (r'/tornado$',handlers.api.TornadoHandler),
    (r'/?$',handlers.api.IndexHandler),
    (r'/qrcode$',handlers.api.QrCodeHandler),
    (r'/webhook$',handlers.api.WebhookHandler),
    (r'/forcepost$',handlers.api.ForcePostHandler),
    (r'/dbrefresh$',handlers.api.DBRefreshHandler),
]
