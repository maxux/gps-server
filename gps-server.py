import json

class GPSRawData:
    def _time(self, tf):
        return "%s:%s:%s" % (tf[0:2], tf[2:4], tf[4:6])

    def _date(self, df):
        return '20%s-%s-%s' % (df[4:6], df[2:4], df[0:2])

    def _dmsdd(self, lat, latcard, lon, loncard):
        if not lat:
            return {'lat': 0, 'lon': 0}

        xlat = {'d': int(lat[0:2]), 'm': int(lat[2:4]), 's': int(lat[5:]) / 100}
        xlon = {'d': int(lon[0:3]), 'm': int(lon[3:5]), 's': int(lon[6:]) / 100}

        ddlat = xlat['d'] + (xlat['m'] / 60) + (xlat['s'] / 3600)
        ddlon = xlon['d'] + (xlon['m'] / 60) + (xlon['s'] / 3600)

        if latcard == 'S':
            ddlat = -ddlat

        if loncard == 'W':
            ddlon = -ddlon

        return {'lat': ddlat, 'lon': ddlon}

    def _quality(self, quality):
        if quality == '0':
            return 'invalid'

        if quality == '1':
            return 'GPS'

        if quality == '2':
            return 'DGPS'

        return 'unknown'

    # Recommended minimum specific GPS/Transit data
    def gprmc(self, fields):
        time = self._time(fields[1])
        date = self._date(fields[9])
        coord = self._dmsdd(fields[3], fields[4], fields[5], fields[6])

        return {'type': 'rmc', 'time': time, 'date': date, 'coord': coord}

    # GPS Satellites in view
    def gpgsv(self, fields):
        return {'type': 'gsv'}

    # Track made good and ground speed
    def gpvtg(self, fields):
        data = {
            'type': 'vtg',
            'track': float(fields[1]),
            'speed': float(fields[7])
        }

        if data['speed'] > 200:
            data['speed'] = 0

        return data

    # GPS DOP and active satellites
    def gpgsa(self, fields):
        mode = 'automatic' if fields[1] == 'A' else 'manual'
        fix = fields[2] + 'd' if fields[2] != '1' else 'not available'

        return {'type': 'gsa', 'mode': mode, 'fix': fix}

    # Global Positioning System Fix Data
    def gpgga(self, fields):
        time = self._time(fields[1])
        coord = self._dmsdd(fields[2], fields[3], fields[4], fields[5])
        quality = self._quality(fields[6])
        hdop = float(fields[8]) if fields[8] else 0
        altitude = float(fields[9]) if fields[9] else 0

        return {
            'type': 'gga',
            'time': time,
            'coord': coord,
            'quality': quality,
            'sats': int(fields[7]),
            'hdop': hdop,       # Horizontal Dilution of Precision
            'altitude': altitude
        }

class GPSData:
    def __init__(self):
        self.raw = GPSRawData()

    def parse(self, line):
        fields = line.split(',')
        action = fields[0]
        # print(fields)

        if action == "$GPRMC":
            return self.raw.gprmc(fields)

        if action == "$GPGSV":
            return self.raw.gpgsv(fields)

        if action == "$GPVTG":
            return self.raw.gpvtg(fields)

        if action == "$GPGSA":
            return self.raw.gpgsa(fields)

        if action == "$GPGGA":
            return self.raw.gpgga(fields)

        return {'type': 'unknown'}

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
