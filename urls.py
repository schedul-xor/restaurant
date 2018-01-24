import handlers.api

url_patterns = [
    (r'/tornado$',handlers.api.TornadoHandler),
    (r'/?$',handlers.api.IndexHandler),
    (r'/line/qrcode$',handlers.api.LineQrCodeHandler),
    (r'/line/webhook$',handlers.api.LineWebhookHandler),
    (r'/messenger/webhook$',handlers.api.MessengerWebhookHandler),
    (r'/forcepost$',handlers.api.ForcePostHandler),
    (r'/image/([\.\d]+)(/\d+)?$',handlers.api.ImageHandler),
    (r'/dbrefresh$',handlers.api.DBRefreshHandler),
    (r'/dbrefresh2$',handlers.api.DBRefresh2Handler),
    (r'/redirect/(.+)$',handlers.api.RedirectHandler),
    (r'/log/dbinit$',handlers.api.LogDBInitHandler),
    (r'/log$',handlers.api.LogHandler),
    (r'/log/dump_(callback|jump)$',handlers.api.LogDumpHandler),
    (r'/log/delete$',handlers.api.LogDeleteHandler),
]
