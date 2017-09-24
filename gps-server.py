import os
import time
import json
from gpstools import *
from flask import Flask, request, redirect, url_for, render_template, abort, make_response, send_from_directory
from werkzeug.wrappers import Request

app = Flask(__name__)
app.url_map.strict_slashes = False

@app.route('/')
def route_index():
    return render_template("default.html")

@app.route('/data')
def route_data():
    with open("static-data.json", "r") as f:
        contents = f.read()

    response = make_response(contents)
    response.headers["Content-Type"] = "application/json"

    return response

@app.route('/ping')
def route_ping():
    return "PONG\n"

print("[+] listening")
app.run(host="0.0.0.0", port=5555, debug=True, threaded=True)
