import os
import time
import json
import sqlite3
import redis
from gpsdata.nmea0183 import *
from gpsdata.custom import GPSDataNew
from flask import Flask, request, redirect, url_for, render_template, abort, make_response, send_from_directory
from werkzeug.wrappers import Request

# checking if config file exists
if not os.path.isfile("config/gpsconf.py"):
    raise Exception("Configuration file not found")

# loading config file
from config.gpsconf import config

app = Flask(__name__)
app.url_map.strict_slashes = False

rclient = redis.Redis()

#
# helpers
#
def jsonreply(contents):
    response = make_response(contents + "\n")
    response.headers["Content-Type"] = "application/json"

    return response

def template(filename, data={}):
    # building default common variable
    # and merge custom variable
    variables = {
        'GOOGLE_API_KEY': config['google-map-apikey'],
        **data
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

    """
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
    """

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

    """
    gpsdata["custom"] = data
    """

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

    # live_update()
    # live_commit(db)

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
def api_sessions():
    db = sqlite3.connect(config['db-file'])

    cursor = db.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY start DESC")

    sessions = []
    dbsessions = cursor.fetchall()
    for session in dbsessions:
        sessions.append({"id": session[0], "datetime": session[1]})

    return sessions

def api_session(sessid):
    db = sqlite3.connect(config['db-file'])
    cursor = db.cursor()

    cursor.execute("SELECT start FROM sessions WHERE id = ? LIMIT 1", (sessid,))
    dbsession = cursor.fetchall()

    # session not found
    if len(dbsession) == 0:
        return []

    sessionstart = dbsession[0][0]

    # session bounds
    cursor.execute("SELECT start FROM sessions WHERE start > ? LIMIT 1", (sessionstart,))
    dbsession = cursor.fetchall()

    # yeah, this is ugly
    maxdate = '9999-01-01 00:00:00'
    if len(dbsession) > 0:
        maxdate = dbsession[0][0]

    # fetching time-slice data
    cursor.execute("SELECT payload FROM datapoints WHERE timepoint > ? AND timepoint < ?", (sessionstart, maxdate,))

    datapoints = []
    dbpoints = cursor.fetchall()
    for datapoint in dbpoints:
        datapoints.append(json.loads(datapoint[0]))

    return datapoints

def api_session_delete(sessid):
    db = sqlite3.connect(config['db-file'])

    cursor = db.cursor()
    cursor.execute("DELETE FROM sessions WHERE id = ?", (sessid,))
    db.commit()

    return True

#
# page routing
#
@app.route('/')
def route_index():
    data = {'CATEGORY': 'live'}
    return template("live.html", data)

@app.route('/sessions')
def route_sessions():
    data = {'CATEGORY': 'sessions'}
    return template("sessions.html", data)

@app.route('/coverage')
def route_coverage():
    data = {'CATEGORY': 'coverage'}
    return template("coverage.html", data)


@app.route('/sessions-full')
def route_sessions_full():
    data = {'CATEGORY': 'full'}
    return template("sessions-full.html", data)

@app.route('/sessions-light')
def route_sessions_light():
    data = {'CATEGORY': 'light'}
    return template("sessions-light.html", data)

@app.route('/session/<sessid>')
def route_session_id(sessid):
    data = {
        'SESSION_ID': sessid,
        'CATEGORY': 'sessions',
    }
    return template("session.html", data)

#
# api routing
#
@app.route('/api/ping', methods=['GET', 'POST'])
def route_api_ping():
    return jsonreply(json.dumps({"pong": int(time.time())}))

@app.route('/api/now')
def route_api_now():
    return jsonreply(json.dumps(livedata))

@app.route('/api/scrub')
def route_api_scrub():
    if request.headers.get('X-GPS-Auth') != config['password']:
        abort(401)

    return jsonreply(json.dumps(datapoints_scrub()))

@app.route('/api/push/session', methods=['GET', 'POST'])
def route_api_push_session():
    if request.headers.get('X-GPS-Auth') != config['password']:
        abort(401)

    db = sqlite3.connect(config['db-file'])

    try:
        cursor = db.cursor()
        now = (int(time.time()),)
        cursor.execute("INSERT INTO sessions (start) VALUES (datetime(?, 'unixepoch', 'localtime'))", now)
        db.commit()

    except Exception as e:
        print(e)

    return jsonreply(json.dumps({"status": "success"}))

@app.route('/api/push/datapoint', methods=['POST'])
def route_api_push_datapoint():
    global gpsdata

    if request.headers.get('X-GPS-Auth') != config['password']:
        abort(401)

    db = sqlite3.connect(config['db-file'])
    # gps = GPSDataNew()
    gps = GPSData()

    lines = request.data.decode('utf-8').strip().split("\n")
    for line in lines:
        # saving raw data
        cursor = db.cursor()
        cursor.execute("INSERT INTO raw (raw) VALUES (?)", (line,))

        # parsing data line
        try:
            data = gps.parse(line)
            gps_push(data, db)

        except Exception as e:
            print(e)

    db.commit()

    return jsonreply(json.dumps({"status": "success"}))

@app.route('/api/sessions')
def route_api_sessions():
    return jsonreply(json.dumps(api_sessions()))

@app.route('/api/session/<sessid>')
def route_api_session(sessid):
    return jsonreply(json.dumps(api_session(sessid)))

@app.route('/api/management/delete/<sessid>')
def route_api_mgmt_delete(sessid):
    if request.headers.get('X-GPS-Auth') != config['password']:
        abort(401)

    api_session_delete(sessid)
    return jsonreply(json.dumps({"status": "success"}))

@app.route('/api/management/truncate/<sessid>')
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


initialize()

#
# serving
#
print("[+] listening")
app.run(host=config['http-listen'], port=config['http-port'], debug=config['debug'], threaded=True)
