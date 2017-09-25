import asyncio
import redis
import websockets
import json
import os

# checking if config file exists
if not os.path.isfile("config/gpsconf.py"):
    raise Exception("Configuration file not found")

# loading config file
from config.gpsconf import config

class GPSLive():
    def __init__(self):
        self.wsclients = set()
        self.redis = redis.Redis()
        self.pubsub = self.redis.pubsub()

        self.payload = {}

    #
    # Websocket
    #
    async def wsbroadcast(self):
        if not len(self.wsclients):
            return

        for client in self.wsclients:
            if not client.open:
                continue

            await client.send(json.dumps(self.payload))

    async def handler(self, websocket, path):
        self.wsclients.add(websocket)

        print("[+] websocket: new client connected")

        try:
            # pushing current data
            await websocket.send(json.dumps(self.payload))

            while True:
                if not websocket.open:
                    break

                await asyncio.sleep(1)

        finally:
            print("[+] websocket: client disconnected")
            self.wsclients.remove(websocket)

    async def fetcher(self):
        self.pubsub.subscribe(['gps-live'])
        loop = asyncio.get_event_loop()

        def looper():
            for item in self.pubsub.listen():
                return item

        while True:
            print("[+] waiting for redis message")
            redis_future = loop.run_in_executor(None, looper)
            response = await redis_future

            if response['type'] == 'message':
                print(response['data'])
                self.payload = json.loads(response['data'].decode('utf-8'))
                await self.wsbroadcast()

    def run(self):
        print("[+] initializing async")
        loop = asyncio.get_event_loop()
        loop.set_debug(True)

        print("[+] starting websocket server")
        addr = config['websocket-listen']
        port = config['websocket-port']
        websocketd = websockets.serve(self.handler, addr, port)
        asyncio.ensure_future(websocketd, loop=loop)

        print("[+] starting redis fetcher")
        asyncio.ensure_future(self.fetcher())

        print("[+] running")
        loop.run_forever()

gpslive = GPSLive()
gpslive.run()
