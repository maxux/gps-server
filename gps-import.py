from gpstools import *
import sqlite3

if __name__ == '__main__':
    with open("trips/trip-4.json", "r") as f:
        raw = f.read()

    db = sqlite3.connect('db/gps.sqlite3')

    data = json.loads(raw)
    cursor = db.cursor()

    index = 0
    for datapoint in data:
        index += 1

        if index == 1:
            continue

        rows = (datapoint['datetime'], json.dumps(datapoint))
        cursor.execute("INSERT INTO datapoints (timepoint, payload) VALUES (?, ?)", rows)

    db.commit()



    """
    with open("/tmp/gps-data-new", "r") as f:
        raw = f.read()

    lines = raw.replace('[+] >> ', '').strip().split("\n")

    gps = GPSData()
    logs = []

    last_gga = None
    last_vtg = None
    last_rmc = None

    index = 0

    for line in lines:
        data = gps.parse(line)
        if data['type'] == 'gga':
            if not data['sats']:
                continue

            last_gga = data

        if data['type'] == 'vtg':
            if not data['track']:
                continue

            last_vtg = data

        if data['type'] == 'rmc':
            if not data['coord']['lng']:
                continue

            last_rmc = data

        if index < 25200:
            index += 1
            continue

        if last_gga and last_vtg and last_rmc:
            logs.append({
                'datetime': '%s %s' % (last_rmc['date'], last_rmc['time']),
                'coord': {
                    'lat': last_rmc['coord']['lat'],
                    'lng': last_rmc['coord']['lng'],
                },
                'speed': last_vtg['speed'],
                'quality': last_gga['quality'],
                'sats': last_gga['sats'],
                'hdop': last_gga['hdop'],
                'altitude': last_gga['altitude'],
                'timestamp': last_rmc['timestamp'],
            })

            last_gga = None
            last_vtg = None
            last_rmc = None

        index += 1

        if index > 31000:
            break

    print(json.dumps(logs))
    """
