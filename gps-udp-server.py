import socket
import requests
from config.gpsconf import config

host = "0.0.0.0"
port = 60942
buflen = 1024

UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
UDPServerSocket.bind((host, port))

print("[+] waiting udp packets")

while(True):
    bytesAddressPair = UDPServerSocket.recvfrom(buflen)

    message = bytesAddressPair[0].decode('utf-8').split("\r\n")
    address = bytesAddressPair[1]

    payload = "\n".join(message[0:-1])
    headers = {"X-GPS-Auth": config['password']}

    print("%s: %s" % (address, message))

    if message[0] == "NEW SESSION":
        requests.get("http://gps.maxux.net/api/push/session", headers=headers)
        continue

    headers = {"X-GPS-Auth": "mx42"}
    requests.post("http://gps.maxux.net/api/push/datapoint", headers=headers, data=payload)

