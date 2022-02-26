from datetime import datetime
import sqlite3
import random

dbname = 'cyberkevdb.db'
nouns = open("wordlists/nouns.txt", "r").read().split("\n")
adjectives = open("wordlists/adjectives.txt", "r").read().split("\n")

def create_id(adj=5, nou=1):  # technically not a db operation, but it was easier to put it here
	lst = []
	for i in range(adj):			lst.append(random.choice(adjectives))
	for i in range(nou):			lst.append(random.choice(nouns))
	return "-".join(lst).lower()

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

def sql_wraw(statement):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	ret = cur.execute(statement).fetchall()
	CON.commit()
	return ret

def verify_user(userid, ideology, questionbank):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()

	arguments = [userid, ideology]
	for i in range(5):
		arguments.append(questionbank[i][0])
		arguments.append(questionbank[i][1])

	ret = cur.execute("INSERT INTO `verification` ('userid', 'ideology', 'Q1', 'A1', 'Q2', 'A2', 'Q3', 'A3', 'Q4', 'A4', 'Q5', 'A5') VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
	arguments)
	CON.commit()

def fetch_verification(userid):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	res = cur.execute("SELECT * FROM `verification` WHERE userid = ?", (userid,)).fetchall()
	if not len(res):
		return None
	else:
		return res[0]

def create_warn(userid, adminid, reason):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	warnid = create_id()
	while len(cur.execute(f'SELECT * FROM `warns` WHERE id = ?', (warnid,)).fetchall()):  # find a random id, this is just security though and should never actually run more than once
		warnid = create_id()
	cur.execute(f"INSERT INTO `warns` VALUES (?, ?, ?, ?, ?)", (userid, adminid, reason, datetime.now(), warnid))
	CON.commit()

def delete_warn(warnid):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	cur.execute(f"DELETE FROM `warns` WHERE id = ?", (warnid,))
	CON.commit()

def delete_user_warns(userid):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	cur.execute(f"DELETE FROM `warns` WHERE userid = ?", (userid,))
	CON.commit()

def get_warns(userid):
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	return cur.execute(f"SELECT * FROM `warns` WHERE userid = ?", (userid,)).fetchall()

def get_warn(warnid): # returns a warn with an id, used for checking if it exists
	CON = sqlite3.connect(dbname)
	cur = CON.cursor()
	warn = cur.execute(f"SELECT * FROM `warns` WHERE id = ?", (warnid,)).fetchall()
	if len(warn):	return warn[0]
	else:			return None