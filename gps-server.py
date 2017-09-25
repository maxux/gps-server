import os
import time
import json
import sqlite3
import redis
from gpstools import *
from flask import Flask, request, redirect, url_for, render_template, abort, make_response, send_from_directory
from werkzeug.wrappers import Request

dbfile = 'db/gps.sqlite3'

app = Flask(__name__)
app.url_map.strict_slashes = False

rclient = redis.Redis()

#
# helpers
#
def jsonreply(contents):
    response = make_response(contents)
    response.headers["Content-Type"] = "application/json"

    return response

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

    rclient.publish('gps-live', json.dumps(livedata))

def live_commit(db):
    # saving live data
    cursor = db.cursor()
    now = (livedata['datetime'], json.dumps(livedata),)
    cursor.execute("INSERT INTO datapoints (timepoint, payload) VALUES (?, ?)", now)
    db.commit()

def gps_push(data, db):
    global gpsdata

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
       gpsdata['rmc'] and gpsdata['rmc']['coord']['lng']:
        print("[+] we have enough valid data, commit")

        try:
            live_commit(db)

        except Exception as e:
            print(e)

def initialize():
    rclient.publish('gps-live', json.dumps(livedata))

#
# page routing
#
@app.route('/')
def route_index():
    return render_template("default.html")

@app.route('/sessions')
def route_sessions():
    return render_template("sessions.html")

@app.route('/session/<sessid>')
def route_session_id(sessid):
    data = {'SESSION_ID': sessid}
    return render_template("session.html", **data)

#
# api routing
#
@app.route('/api/ping')
def route_api_ping():
    return jsonreply(json.dumps({"pong": int(time.time())}))

@app.route('/api/now')
def route_api_now():
    return jsonreply(json.dumps(livedata))

@app.route('/api/push/session')
def route_api_push_session():
    db = sqlite3.connect(dbfile)

    cursor = db.cursor()
    now = (int(time.time()),)
    cursor.execute("INSERT INTO sessions (start) VALUES (datetime(?, 'unixepoch'))", now)
    db.commit()

    return jsonreply(json.dumps({"status": "success"}))

@app.route('/api/push/datapoint', methods=['POST'])
def route_api_push_datapoint():
    db = sqlite3.connect(dbfile)
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
    live_update()

    return jsonreply(json.dumps({"status": "success"}))

@app.route('/api/sessions')
def route_api_sessions():
    db = sqlite3.connect(dbfile)

    cursor = db.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY start DESC")

    sessions = []
    dbsessions = cursor.fetchall()
    for session in dbsessions:
        sessions.append({"id": session[0], "datetime": session[1]})

    return jsonreply(json.dumps(sessions))

@app.route('/api/session/<sessid>')
def route_api_session(sessid):
    db = sqlite3.connect(dbfile)
    cursor = db.cursor()

    cursor.execute("SELECT start FROM sessions WHERE id = ? LIMIT 1", (sessid,))
    dbsession = cursor.fetchall()

    # session not found
    if len(dbsession) == 0:
        return jsonreply("[]")

    sessionstart = dbsession[0][0]

    # session bounds
    cursor.execute("SELECT start FROM sessions WHERE id > ? LIMIT 1", (sessid,))
    dbsession = cursor.fetchall()

    # yeah, this is ugly
    maxdate = '9999-01-01 00:00:00'
    if len(dbsession) > 0:
        maxdate = dbsession[0][0]

    print(sessionstart, maxdate)

    # fetching time-slice data
    cursor.execute("SELECT payload FROM datapoints WHERE timepoint > ? AND timepoint < ?", (sessionstart, maxdate,))

    datapoints = []
    dbpoints = cursor.fetchall()
    for datapoint in dbpoints:
        datapoints.append(json.loads(datapoint[0]))

    return jsonreply(json.dumps(datapoints))

initialize()

#
# serving
#
print("[+] listening")
app.run(host="0.0.0.0", port=5555, debug=True, threaded=True)
