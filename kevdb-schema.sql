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

CREATE TABLE verification(
	'userid' INT NOT NULL UNIQUE,
	'timestamp' DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	'ideology' TEXT NOT NULL,
	'Q1' TEXT,
	'A1' TEXT,
	'Q2' TEXT,
	'A2' TEXT,
	'Q3' TEXT,
	'A3' TEXT,
	'Q4' TEXT,
	'A4' TEXT,
	'Q5' TEXT,
	'A5' TEXT 
)