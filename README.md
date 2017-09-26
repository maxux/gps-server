# GPS Server

This is the central GPS database, web interface and gateway made to provide an
interface based on [`gps-client`](https://github.com/maxux/gps-client).

# Features

- Lightweight
- Websocket live data pushing
- Realtime Map tracking
- Charts of speed, altitide, satellites in view, ...
- Keep all the data-points in database
- Keep raw input (to replay data if needed)
- Public API for pushing and getting data
- Small/basic protection level
- Really easy to use

# Workflow

When running `gps-server.py`, you provides two main things:
- API to push data-points
- API/Pages to get and shows data-points

## Pushing data

### Sessions
Basicly all of this is done by `gps-client`.

A **Session** is kind of data-time-slice representing a start and end date-time set.
All points within this time-slice reprensent a « trip ».

In database, we only save **begenin** of a session, the client is made **unreliable** and **stateless**,
because imagine, you stop your car, you power-off the module, you can't notify the server you're stopped.

This is how a **Session** works, a session is all points between **Session-Start** and next session in database
(if there is no next-session (when it's the last session), you get all data since begenin of the session).

As soon as you make a request to `/api/push/session`, a new session is created and all data-points inserted
after are « in this session ».

### Data Point

The client will send plain-raw **NMEA 0183** frames, bundled (batch) in a single request.
The bundle is made to push the buffer as soon as a **GPRMC** frame is received.

The server aims to decode frame and take decision (keeping it, forward it, ...)

To send data to the server, make a POST request to `/api/push/datapoint`, the body must contains
frames, separated by new-line character.

The client is made to push data over GPRS/HSDPA network, which can be slow and unreliable, this is
why some bundle are made, sending each frame one-by-one is really too slow and produce lot of delay.

### Security

Security is not the best point on this infrastructure, to provide simple security, all `/api/push/`
endpoints are « protected » with `X-GPS-Auth` HTTP header, which contains a password. This password
will be checked server-side to authorize the request or not. This is configurable on the config-file.

## Reading data

Via the API (which is used by the front-end interface), you can list **Sessions** and get all **Data-Points** from
a specific session.
- `/api/sessions`: list all sessions
- `/api/session/<session-id>`: get all data-points related to `<session-id>`

## Live Tracking

As soon as the client send something, if data are valid, data are forwarded to web-clients, with
web-sockets. This is done by fillin a redis-queue with data. The `gps-live.py` takes care to handle web-sockets clients
and forward data from redis-queue to web-clients.

## Database

Even if the current engine is SQLite3, the database itself is not relational, data are stored like in a key-value store.

You can't query the database on position/speed/etc. data are stored in JSON in a TEXT field. The database is here more
for peristance, not for data management. This can maybe change in the future.
