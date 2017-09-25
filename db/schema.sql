CREATE TABLE raw (id integer primary key autoincrement, raw varchar(512));
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE datapoints (timepoint datetime primary key, payload text);
CREATE TABLE sessions (id integer primary key autoincrement, start datetime unique);

