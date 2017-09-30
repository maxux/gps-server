import json
import sys
from datetime import datetime
from datetime import timezone

class GPSRawData:
    def _time(self, tf):
        return "%s:%s:%s" % (tf[0:2], tf[2:4], tf[4:6])

    def _date(self, df):
        return '20%s-%s-%s' % (df[4:6], df[2:4], df[0:2])

    def _dmsdd(self, lat, latcard, lon, loncard):
        if not lat:
            return {'lat': None, 'lng': None}

        xlat = {'d': int(lat[0:2]), 'ms': float(lat[2:])}
        xlon = {'d': int(lon[0:3]), 'ms': float(lon[3:])}

        ddlat = xlat['d'] + (xlat['ms'] / 60)
        ddlon = xlon['d'] + (xlon['ms'] / 60)

        if latcard == 'S':
            ddlat = -ddlat

        if loncard == 'W':
            ddlon = -ddlon

        return {'lat': ddlat, 'lng': ddlon, 'rlat': lat, 'rlng': lon}

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

        dt = datetime.strptime('%s %s' % (date, time), '%Y-%m-%d %H:%M:%S')
        timestamp = dt.replace(tzinfo=timezone.utc).timestamp()

        coord = self._dmsdd(fields[3], fields[4], fields[5], fields[6])

        return {
            'type': 'rmc',
            'timestamp': int(timestamp),
            'time': time,
            'date': date,
            'coord': coord
        }

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
        # malformed line (no checksum at the end)
        if line[-3:-2] != "*":
            return {'type': 'unknown'}

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
