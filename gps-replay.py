from gpsdata.nmea0183 import *
import os
import time
import sys
import sqlite3

# checking if config file exists
if not os.path.isfile("config/gpsconf.py"):
    raise Exception("Configuration file not found")

# loading config file
from config.gpsconf import config

def status(data):
    sys.stdout.write(data)
    sys.stdout.flush()

livedata = {
    'datetime': '',
    'coord': {'lat': 0, 'lng': 0},
    'speed': 0,
    'quality': 'searching',
    'sats': 0,
    'hdop': 0,
    'altitude': 0,
    'timestamp': time.time()
}

gpsdata = {
    'gga': None,
    'vtg': None,
    'rmc': None
}

def live_update():
    global livedata
    global gpsdata

    livedata = {
        'datetime': '%s %s' % (gpsdata['rmc']['date'], gpsdata['rmc']['time']),
        'coord': {
            'lat': gpsdata['rmc']['coord']['lat'],
            'lng': gpsdata['rmc']['coord']['lng'],
        },
        'speed': gpsdata['vtg']['speed'],
        'quality': gpsdata['gga']['quality'],
        'sats': gpsdata['gga']['sats'],
        'hdop': gpsdata['gga']['hdop'],
        'altitude': gpsdata['gga']['altitude'],
        'timestamp': gpsdata['rmc']['timestamp'],
    }

    gpsdata['gga'] = None
    gpsdata['vtg'] = None
    gpsdata['rmc'] = None

def live_commit(db):
    try:
        # saving live data
        cursor = db.cursor()

        cursor.execute("SELECT * FROM datapoints WHERE timepoint = ?", (livedata['datetime'],))
        exists = cursor.fetchall()
        if len(exists) > 0:
            # print("[-] database up-to-date")
            return 0

        status('+')

        now = (livedata['datetime'], json.dumps(livedata),)
        cursor.execute("INSERT INTO datapoints (timepoint, payload) VALUES (?, ?)", now)
        db.commit()

    except Exception as e:
        print("[-] %s" % e)

    return 1

def gps_push(data, db):
    global gpsdata

    if data['type'] == 'unknown' or data['type'] == 'bad checksum':
        return 0

    # validating data
    if data['type'] == 'gga':
        gpsdata['gga'] = data

    if data['type'] == 'vtg':
        gpsdata['vtg'] = data

    if data['type'] == 'rmc':
        gpsdata['rmc'] = data

    # commit new values
    if gpsdata['gga'] and gpsdata['gga']['sats'] and \
       gpsdata['vtg'] and gpsdata['vtg']['track'] and \
       gpsdata['rmc'] and gpsdata['rmc']['coord']['lng'] and \
       gpsdata['rmc']['coord']['lat']:
        live_update()
        return live_commit(db)

    return 0

def gps_session(db, data):
    dtfound = "%s %s" % (data['date'], data['time'])

    cursor = db.cursor()
    cursor.execute("SELECT * FROM sessions WHERE start > datetime(?, '-10 minutes') AND start < datetime(?, '+10 minutes')", (dtfound, dtfound,))
    exists = cursor.fetchall()

    if len(exists) > 0:
        print("[+] session found")
        return

    print("[-] session not found, creating new session")
    cursor.execute("INSERT INTO sessions (start) VALUES (datetime(?))", (dtfound,))
    db.commit()

def gps_lookup(gps, lines):
    print("[+] looking for first valid frame")
    validity = False

    for line in lines:
        try:
            data = gps.parse(line)
            if data['type'] == "rmc":
                if data['validity']:
                    validity = True
                    break

        except Exception as e:
            print("[-] %s" % e)

    if not validity:
        print("[-] could not find any valid interresting frame")
        return None

    dtfound = "%s %s" % (data['date'], data['time'])
    print("[+] first valid frame found, datetime: %s" % dtfound)
    print("[+] looking for existing session")

    return data


def initialize(filename):
    print("[+] replaying: %s" % filename)

    db = sqlite3.connect(config['db-file'])
    gps = GPSData()

    commit = 0
    parsed = 0

    with open(filename, 'rb') as f:
        contents = f.read()

    lines = contents.decode('utf-8', 'ignore').strip().split("\n")

    data = gps_lookup(gps, lines)
    if data == None:
        # no valid frame found, skipping
        return

    # ensure session exists
    gps_session(db, data)

    status("[+] replaying: ")

    for line in lines:
        try:
            data = gps.parse(line)
            parsed += 1

            if parsed % 100 == 0:
                status('.')

            commit += gps_push(data, db)

        except Exception as e:
            print("[-] %s" % e)

    print(".")

    print("[+] replayed frames: %d" % parsed)
    print("[+] missing frames: %d" % commit)

    db.close()

if len(sys.argv) < 2:
    print("[-] missing root datapoint directory")
    sys.exit(1)

rootpath = sys.argv[1]

print("[+] root datapoint: %s" % rootpath)

for file in os.listdir(rootpath):
    initialize("%s/%s" % (rootpath, file))
