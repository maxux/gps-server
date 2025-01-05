import os
import time
import json
import sqlite3
import redis
import pymysql
import traceback
from gpsdata.nmea0183 import *
from gpsdata.custom import GPSDataNew
from flask import Flask, current_app, request, redirect, render_template, abort, jsonify, g
# from werkzeug.wrappers import Request

# checking if config file exists
if not os.path.isfile("config/gpsconf.py"):
    raise Exception("Configuration file not found")

# loading config file
from config.gpsconf import config

class GPSWebServer:
    def __init__(self):
        self.app = Flask(__name__)
        # self.app.url_map.strict_slashes = False

        self.redis = redis.Redis(config['redis-host'], config['redis-port'])
        self.lastpoint = {}

    #
    # live handler
    #
    def commit(self, datapoint, device):
        live = {
            'datetime': '%s %s' % (datapoint['date'], datapoint['time']),
            'coord': {
                'lat': datapoint['lat'],
                'lng': datapoint['lng'],
            },
            'speed': datapoint['speed'],
            'quality': 0,
            'sats': 0,
            'hdop': 0,
            'altitude': datapoint['alt'],
            'timestamp': datapoint['ts'],
        }

        query = """
            INSERT INTO locations
            (timepoint, device, accuracy, latitude, longitude, speed, altitude, hdop, viewsat)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            live["datetime"],
            device,
            live["quality"],
            live["coord"]["lat"],
            live["coord"]["lng"],
            live["speed"],
            live["altitude"],
            live["hdop"],
            live["sats"]
        )

        cursor = g.db.cursor()

        try:
            cursor.execute(query, values)

        except Exception:
            traceback.print_exc()

        # forward live frame
        self.redis.publish('gps-live', json.dumps(live))


    #
    # implementation
    #
    def api_sessions(self):
        cursor = g.db.cursor()
        cursor.execute("SELECT id, start FROM sessions ORDER BY start DESC")

        sessions = []
        dbsessions = cursor.fetchall()
        for session in dbsessions:
            sessions.append({"id": session[0], "datetime": session[1]})

        return sessions

    def api_session(self, sessid):
        cursor = g.db.cursor()

        cursor.execute("SELECT start FROM sessions WHERE id = %s LIMIT 1", (sessid,))
        dbsession = cursor.fetchall()

        # session not found
        if len(dbsession) == 0:
            return []

        sessionstart = dbsession[0][0]

        # session bounds
        cursor.execute("SELECT start FROM sessions WHERE start > %s LIMIT 1", (sessionstart,))
        dbsession = cursor.fetchall()

        # yeah, this is ugly
        maxdate = '9999-01-01 00:00:00'
        if len(dbsession) > 0:
            maxdate = dbsession[0][0]

        # fetching time-slice data
        query = """
            SELECT timepoint, UNIX_TIMESTAMP(timepoint), device, latitude, longitude, speed, altitude, viewsat
            FROM locations
            WHERE timepoint > %s AND timepoint < %s
            ORDER BY timepoint
        """
        cursor.execute(query, (sessionstart, maxdate,))

        datapoints = []
        dbpoints = cursor.fetchall()
        for datapoint in dbpoints:
            entry = {
                "datetime": datapoint[0].strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": datapoint[1],
                "coord": {
                    "lat": datapoint[3],
                    "lng": datapoint[4],
                },
                "speed": datapoint[5],
                "altitude": datapoint[6],
                "sats": datapoint[7],
            }

            datapoints.append(entry)

        return datapoints

    #
    # routing
    #
    def routes(self):
        @self.app.route('/migrate')
        def migrate():
            return "DISABLED"

            dbl = sqlite3.connect(config['db-file'])
            rdb = g.db.cursor()

            print("loading list")
            cursor = dbl.cursor()
            cursor.execute("SELECT payload FROM datapoints ORDER BY timepoint ASC")

            print("inserting...")
            for x in cursor.fetchall():
                p = json.loads(x[0])

                hdop = p["hdop"] if p["hdop"] > 0 else None
                sats = p["sats"] if p["sats"] > 0 else None

                if not p["coord"]["lat"] or not p["coord"]["lng"]:
                    continue

                try:
                    rdb.execute("""
                        INSERT IGNORE INTO locations
                        (timepoint, device, accuracy, latitude, longitude, speed, altitude, hdop, viewsat, received)
                        VALUES (%s, 1, NULL, %s, %s, %s, %s, %s, %s, %s)

                    """, (p["datetime"], "%.8f" % p["coord"]["lat"], "%.8f" % p["coord"]["lng"], "%.1f" % p["speed"], "%.1f" % p["altitude"], hdop, sats, p["datetime"]))

                except Exception:
                    traceback.print_exc()
                    print(p)

                    sys.exit(1)


            g.db.commit()

            return "OK"

        @self.app.before_request
        def before_request_handler():
            g.db = pymysql.connect(
                host=config['db-host'],
                user=config['db-user'],
                password=config['db-pass'],
                database=config['db-name'],
                autocommit=True
            )

        @self.app.after_request
        def add_header(response):
            # gracefully close database connection
            g.db.close()

            return response

        @self.app.context_processor
        def inject_recurring_data():
            return {
                'now': datetime.utcnow(),
                'googlekey': config['google-map-apikey'],
            }

        # routing
        @self.app.route('/')
        def route_index():
            data = {'CATEGORY': 'live'}
            return render_template("live.html", **data)

        @self.app.route('/sessions')
        def route_sessions():
            data = {'CATEGORY': 'sessions'}
            return render_template("sessions.html", **data)

        @self.app.route('/coverage')
        def route_coverage():
            data = {'CATEGORY': 'coverage'}
            return render_template("coverage.html", **data)

        @self.app.route('/sessions-full')
        def route_sessions_full():
            data = {'CATEGORY': 'full'}
            return render_template("sessions-full.html", **data)

        @self.app.route('/sessions-light')
        def route_sessions_light():
            data = {'CATEGORY': 'light'}
            return render_template("sessions-light.html", **data)

        @self.app.route('/session/<sessid>')
        def route_session_id(sessid):
            data = {
                'SESSION_ID': sessid,
                'CATEGORY': 'sessions',
            }

            return render_template("session.html", **data)

        #
        # api routing
        #
        @self.app.route('/api/ping', methods=['GET', 'POST'])
        def route_api_ping():
            return jsonify({"pong": int(time.time())})

        @self.app.route('/api/now')
        def route_api_now():
            return jsonify(self.lastpoint)

        """
        @self.app.route('/api/scrub')
        def route_api_scrub():
            if request.headers.get('X-GPS-Auth') != config['password']:
                abort(401)

            return jsonreply(json.dumps(datapoints_scrub()))
        """

        @self.app.route('/api/push/session', methods=['GET', 'POST'])
        def route_api_push_session():
            if request.headers.get('X-GPS-Auth') != config['password']:
                abort(401)

            device = request.args.get("device", "1")
            cursor = g.db.cursor()
            sessid = 0

            try:
                query = "INSERT INTO sessions (device) VALUES (%s)"
                cursor.execute(query, (device))

            except Exception as e:
                traceback.print_exc()

            return jsonify({"status": "success", "id": cursor.lastrowid})

        @self.app.route('/api/push/datapoint', methods=['POST'])
        def route_api_push_datapoint():
            if request.headers.get('X-GPS-Auth') != config['password']:
                abort(401)

            device = request.args.get("device", "1")
            cursor = g.db.cursor()
            point = GPSDataNew()

            lines = request.data.decode('utf-8').strip().split("\n")
            for line in lines:
                query = "INSERT INTO datapoints (device, payload) VALUES (%s, %s)"
                cursor.execute(query, (device, line))

                # parsing data line
                try:
                    datapoint = point.parse(line)

                    if "Darwin/" in request.headers.get("User-Agent"):
                        # fix ios app sending m/s and not km/h
                        datapoint["speed"] = datapoint["speed"] * 3.6

                    self.commit(datapoint, device)
                    # gps_push(data, db)

                except Exception:
                    traceback.print_exc()

            return jsonify({"status": "success"})

        @self.app.route('/api/sessions')
        def route_api_sessions():
            return jsonify(self.api_sessions())

        @self.app.route('/api/session/<sessid>')
        def route_api_session(sessid):
            return jsonify(self.api_session(sessid))

        """
        @self.app.route('/api/management/delete/<sessid>')
        def route_api_mgmt_delete(sessid):
            if request.headers.get('X-GPS-Auth') != config['password']:
                abort(401)

            api_session_delete(sessid)
            return jsonreply(json.dumps({"status": "success"}))

        @self.app.route('/api/management/truncate/<sessid>')
        def route_api_mgmt_truncate(sessid):
            if request.headers.get('X-GPS-Auth') != config['password']:
                abort(401)

            db = sqlite3.connect(config['db-file'])
            cursor = db.cursor()

            datapoints = api_session(sessid)

            for datapoint in datapoints:
                print("[+] removing: %s" % datapoint['datetime'])
                now = (datapoint['datetime'],)
                cursor.execute("DELETE FROM datapoints WHERE timepoint = ?", now)

            cursor.execute("DELETE FROM sessions WHERE id = ?", (sessid,))
            db.commit()

            return jsonreply(json.dumps({"status": "success"}))
        """


"""
#
# helpers
#
    }
    return render_template(filename, **variables)

#
# gps data handling
#
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
    'custom': None,
    'gga': None,
    'vtg': None,
    'rmc': None
}

def live_update():
    global livedata
    global gpsdata

    print("live update")
    print(gpsdata)

    livedata = {
        'datetime': '%s %s' % (gpsdata['custom']['date'], gpsdata['custom']['time']),
        'coord': {
            'lat': gpsdata['custom']['lat'],
            'lng': gpsdata['custom']['lng'],
        },
        'speed': gpsdata['custom']['speed'] * 3.6, # m/s -> km/h
        'quality': gpsdata['custom']['acc'],
        'sats': 0, # gpsdata['custom']['sats'],
        'hdop': gpsdata['custom']['acc'],
        'altitude': gpsdata['custom']['alt'],
        'timestamp': gpsdata['custom']['ts'],
    }

    '''
    livedata = {
        'datetime': '%s %s' % (gpsdata['rmc']['date'], gpsdata['rmc']['time']),
        'coord': {
            'lat': gpsdata['rmc']['coord']['lat'],
            'lng': gpsdata['rmc']['coord']['lng'],
        },
        'speed': gpsdata['rmc']['speed'], # gpsdata['vtg']['speed'],
        'quality': gpsdata['gga']['quality'],
        'sats': gpsdata['gga']['sats'],
        'hdop': gpsdata['gga']['hdop'],
        'altitude': gpsdata['gga']['altitude'],
        'timestamp': gpsdata['rmc']['timestamp'],
    }
    '''

    if livedata['speed'] < 0:
        livedata['speed'] = 0

    print("data created")
    print(livedata)

    # notify live update
    rclient.publish('gps-live', json.dumps(livedata))

    gpsdata['gga'] = None
    gpsdata['vtg'] = None
    gpsdata['rmc'] = None


def live_commit(db):
    try:
        # saving live data
        cursor = db.cursor()
        now = (livedata['datetime'], json.dumps(livedata),)
        cursor.execute("INSERT INTO datapoints (timepoint, payload) VALUES (?, ?)", now)
        db.commit()

    except Exception as e:
        print(e)

def gps_push(data, db):
    global gpsdata

    print("PUSH")
    print(data)

    gpsdata["custom"] = data

    '''
    # validating data
    if data['type'] == 'gga':
        gpsdata['gga'] = data

    if data['type'] == 'vtg':
        gpsdata['vtg'] = data

    if data['type'] == 'rmc':
        gpsdata['rmc'] = data

    # commit new values
    if gpsdata['gga'] and gpsdata['gga']['sats'] and \
       gpsdata['rmc'] and gpsdata['rmc']['coord']['lng'] and \
       gpsdata['rmc']['coord']['lat']:
        print("[+] we have enough valid data, commit")
        live_update()
        live_commit(db)

    # gpsdata['vtg'] and gpsdata['vtg']['track'] and \
    '''

    live_update()
    live_commit(db)

def initialize():
    global livedata

    # loading last data from database
    db = sqlite3.connect(config['db-file'])

    cursor = db.cursor()
    cursor.execute("SELECT payload FROM datapoints ORDER BY timepoint DESC LIMIT 1")
    dbpoints = cursor.fetchall()
    if len(dbpoints) == 1:
        livedata = json.loads(dbpoints[0][0])

    rclient.publish('gps-live', json.dumps(livedata))

#
# management
#
def datapoints_scrub():
    sessions = api_sessions()
    deleted = []

    for session in sessions:
        datapoints = api_session(session['id'])
        if len(datapoints) == 0:
            deleted.append(session)
            api_session_delete(session['id'])

    return deleted

#
# api implementation
#
def api_session_delete(sessid):
    db = sqlite3.connect(config['db-file'])

    cursor = db.cursor()
    cursor.execute("DELETE FROM sessions WHERE id = ?", (sessid,))
    db.commit()

    return True

#
# page routing
#

"""

if __name__ == "gpswebsrv":
    print(f"[+] wsgi: initializing gps-web-server application")

    gps = GPSWebServer()
    gps.routes()

    app = gps.app
