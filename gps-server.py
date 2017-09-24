import os
import time
import json
import sqlite3
from gpstools import *
from flask import Flask, request, redirect, url_for, render_template, abort, make_response, send_from_directory
from werkzeug.wrappers import Request

app = Flask(__name__)
app.url_map.strict_slashes = False

#
# helpers
#
def jsonreply(contents):
    response = make_response(contents)
    response.headers["Content-Type"] = "application/json"

    return response

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
    db = sqlite3.connect('db/gps.sqlite3')

    cursor = db.cursor()
    cursor.execute("SELECT payload FROM datapoints ORDER BY timepoint DESC LIMIT 2")

    datapoints = []
    dbpoints = cursor.fetchall()
    for datapoint in dbpoints:
        datapoints.append(json.loads(datapoint[0]))

    return jsonreply(json.dumps(datapoints))

@app.route('/api/sessions')
def route_api_sessions():
    db = sqlite3.connect('db/gps.sqlite3')

    cursor = db.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY start DESC")

    sessions = []
    dbsessions = cursor.fetchall()
    for session in dbsessions:
        sessions.append({"id": session[0], "datetime": session[1]})

    return jsonreply(json.dumps(sessions))

@app.route('/api/session/<sessid>')
def route_api_session(sessid):
    db = sqlite3.connect('db/gps.sqlite3')
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

#
# serving
#
print("[+] listening")
app.run(host="0.0.0.0", port=5555, debug=True, threaded=True)
