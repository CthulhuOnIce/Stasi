from datetime import datetime
import sqlite3

dbname = 'cyberkevdb.db'

def audit_log(action, actorname, actorid, description, description_raw):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	cur.execute(f"INSERT INTO `auditlog` VALUES (?, ?, ?, ?, ?, ?)", (action, actorname, actorid, description, description_raw, datetime.now()))
	CON.commit()

def record_ban(admin, target, reason):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	cur.execute(f"INSERT INTO `banledger` VALUES (?, ?, ?, ?)", (target, admin, reason, datetime.now()))
	CON.commit()

def expunge_ban(user):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	cur.execute(f"DELETE FROM `banledger` WHERE user = ?", (user,))
	CON.commit()

def get_ban(user):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	return cur.execute(f'SELECT * FROM `banledger` WHERE user = ?', (user,)).fetchall()[0]

def sql_raw(statement):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	return cur.execute(statement).fetchall()