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
	res = cur.execute(f'SELECT * FROM `banledger` WHERE user = ?', (user,)).fetchall()
	if len(res):
		return res[0]
	else:
		return None

def get_all_bans():
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	return cur.execute(f'SELECT * FROM `banledger`').fetchall()

def sql_raw(statement):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	return cur.execute(statement).fetchall()

def sql_write(statement):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	result = cur.execute(statement)
	CON.commit()
	return result