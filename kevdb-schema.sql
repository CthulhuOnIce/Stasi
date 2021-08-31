CREATE TABLE auditlog(
	'action' TEXT NOT NULL,
	'actorname' TEXT NOT NULL,
	'actorid' INTEGER NOT NULL,
	'description' TEXT NOT NULL,
	'description_raw' TEXT NOT NULL,
	'timestamp' DATETIME NOT NULL
);

CREATE TABLE banledger(
	'user' INTEGER NOT NULL,
	'admin' INTEGER,
	'reason' TEXT,
	'timestamp' DATETIME NOT NULL
);

CREATE TABLE warns(
	'userid' INTEGER NOT NULL,
	'adminid' INTEGER NOT NULL,
	'reason' INTEGER NOT NULL,
	'timestamp' DATETIME NOT NULL,
	'id' TEXT NOT NULL UNIQUE
)