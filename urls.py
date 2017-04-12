import handlers.api

url_patterns = [
    (r'/tornado$',handlers.api.TornadoHandler),
    (r'/?$',handlers.api.IndexHandler),
    (r'/qrcode$',handlers.api.QrCodeHandler),
    (r'/places/json$',handlers.api.PlacesJsonHandler),
    (r'/webhook$',handlers.api.WebhookHandler),
    (r'/forcepost$',handlers.api.ForcePostHandler),
]
