import socket
import requests
from config.gpsconf import config

host = "0.0.0.0"
port = 60942
buflen = 1024
newsess = False

UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
UDPServerSocket.bind((host, port))

print("[+] waiting udp packets")

while(True):
    bytesAddressPair = UDPServerSocket.recvfrom(buflen)

    try:
        message = bytesAddressPair[0].decode('utf-8').split("\r\n")
        address = bytesAddressPair[1]

        payload = "\n".join(message[0:-1])
        headers = {"X-GPS-Auth": config['password']}

        print("%s: %s" % (address, message))

        if message[0] == "NEW SESSION":
            newsess = True
            continue

        # create the session only on datapoint
        # avoid empty sessions
        if newsess == True:
            print("[+] commit new session")
            requests.get("http://gps.maxux.net/api/push/session", headers=headers)
            newsess = False

        requests.post("http://gps.maxux.net/api/push/datapoint", headers=headers, data=payload)

    except Exception as e:
        print(e)
