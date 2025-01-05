import asyncio
import redis
import json
import os
import uuid
import traceback
from websockets.asyncio.server import serve

# checking if config file exists
if not os.path.isfile("config/gpsconf.py"):
    raise Exception("Configuration file not found")

# loading config file
from config.gpsconf import config

class GPSLive():
    def __init__(self):
        self.clients = {}

    async def redis_message(self, message):
        print(f"[+][redis-channel] {message['data']}")
        payload = json.loads(message['data'])

        for clientid in self.clients:
            await self.clients[clientid].send(message['data'])

        return True

    async def redis_reader(self, channel):
        while True:
            message = await channel.get_message(ignore_subscribe_messages=True, timeout=0.2)
            if message is not None:
                try:
                    await self.redis_message(message)

                except Exception:
                    traceback.print_exc()

    async def websocket_handler(self, websocket):
        clientid = str(uuid.uuid4())
        print(f"[+] websocket: new client: {clientid}")

        try:
            self.clients[clientid] = websocket

            # request a quick latency checking
            await websocket.ping()

            # do not listen for client messages
            await websocket.wait_closed()

        except websockets.exceptions.ConnectionClosedError:
            print(f"[-][{clientid}] connection closed prematurely")

        finally:
            if not clientid:
                return None

            print(f"[+][{clientid}] disconnected, cleaning up")

            # remove clientid from websockets clients list
            if clientid in self.clients:
                print(f"[+][{clientid}] cleaning up clients list")
                del self.clients[clientid]

    async def process(self):
        # fetching instance settings
        redis_channel = "gps-live"
        websocket_address = config['websocket-listen']
        websocket_port = config['websocket-port']

        async with serve(self.websocket_handler, websocket_address, websocket_port):
            print(f"[+] websocket: waiting for clients on: [{websocket_address}:{websocket_port}]")
            future_ws = asyncio.get_running_loop().create_future()

            while True:
                print("[+] redis: connecting to backend with asyncio")

                try:
                    self.redis = redis.asyncio.Redis(
                        host=config['redis-host'],
                        port=config['redis-port'],
                        decode_responses=True,
                        client_name="gps-live-monitor"
                    )

                    async with self.redis.pubsub() as pubsub:
                        print(f"[+] redis: subscribing to: {redis_channel}")
                        await pubsub.subscribe(redis_channel)

                        print(f"[+] redis: waiting for events")
                        future_redis = asyncio.create_task(self.redis_reader(pubsub))
                        await future_redis

                except redis.exceptions.ConnectionError as error:
                    print(f"[-] redis: connection lost: {error} attempting to reconnect")

                    await asyncio.sleep(1)
                    continue

                except Exception:
                    print("[-] redis: unhandled exception, stopping")
                    traceback.print_exc()
                    return None

            await future_ws

    #
    # external launcher
    #
    def listen(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.process())
        loop.close()

if __name__ == "__main__":
    root = GPSLive()
    root.listen()
