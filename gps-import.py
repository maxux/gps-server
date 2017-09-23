from gpstools import *

if __name__ == '__main__':
    with open("/tmp/gps-data-new", "r") as f:
        raw = f.read()

    lines = raw.replace('[+] >> ', '').strip().split("\n")

    gps = GPSData()
    logs = []

    last_gga = None
    last_vtg = None
    last_rmc = None

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
            if not data['coord']['lon']:
                continue

            last_rmc = data

        if last_gga and last_vtg and last_rmc:
            logs.append({
                'datetime': '%s %s' % (last_rmc['date'], last_rmc['time']),
                'coord': last_rmc['coord'],
                'speed': last_vtg['speed'],
                'quality': last_gga['quality'],
                'sats': last_gga['sats'],
                'hdop': last_gga['hdop'],
                'altitude': last_gga['altitude'],
            })

    print(json.dumps(logs))
