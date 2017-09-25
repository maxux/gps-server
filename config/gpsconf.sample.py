# gps-server global configuration
config = {
    # sqlite database file
    'db-file': "db/gps.sqlite3",

    # http post (session, datapoint) password
    'password': '',

    # public url for reaching pages
    'public-url': 'gps.domain.tld',

    # public url for reaching live websocket
    'public-live-url': 'live.gps.domain.tld',

    # google map api key
    'google-map-apikey': '',

    # http listen port
    'http-port': 5555,

    # live websocket port
    'websocket-port': 5556,

    # http listen address
    'http-listen': '0.0.0.0',

    # websocket listen address
    'websocket-listen': '0.0.0.0',

    # enable flask debug
    'debug': True,
}
