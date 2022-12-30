import asyncio
import base64
import datetime
from multiprocessing.sharedctypes import Value

import discord
import motor
import motor.motor_asyncio
import pymongo
import yaml

from . import utils

try:
    with open("config.yml", "r") as r:
        C = yaml.load(r.read(), Loader=yaml.FullLoader)
except FileNotFoundError:
    print("No config.yml, please copy and rename config-example.yml and fill in the appropriate values.")
    exit()

client = None
async def establish_server_connection():
    global client
    conn_str = f"mongodb+srv://{C['mongodb']['username']}:{C['mongodb']['password']}@{C['mongodb']['url']}/{C['mongodb']['name']}"
    client = motor.motor_asyncio.AsyncIOMotorClient(conn_str, serverSelectionTimeoutMS=5000)

loop = asyncio.get_event_loop()
loop.run_until_complete(establish_server_connection())
del loop  # :troll:


async def create_connection(table):
    db = client[C["mongodb"]["name"]]
    return db[table]


# global table

async def get_global(name):
    db = await create_connection("globals")
    glob = await db.find_one({"_id": name})
    if glob is None:
        return None
    return glob["value"]

async def set_global(name, value):
    db = await create_connection("globals")
    return await db.update_one({"_id": name}, {"$set": {"value": value}}, upsert=True)

async def del_global(name):
    db = await create_connection("globals")
    return await db.delete_one({"_id": name})


# user tracking

user_template = {
    "_id": int,
    "last_seen": datetime.datetime.utcnow(),
    "last_name": str, 
    "messages": int,
    "verification": []
}

async def get_user(member_id):
    db = await create_connection("users")
    user = await db.find_one({"_id": member_id})
    if user is None:
        return {}
    return user

async def add_message(member_id):  # also used to register users
    db = await create_connection("users")
    return await db.update_one({"_id": member_id}, {"$inc": {"messages": 1}}, upsert=True)

async def add_reaction(reaction, member_id):
    db = await create_connection("users")
    return await db.update_one({"_id": member_id}, {"$inc": {f"reactions.{reaction}": 1}}, upsert=True)


# verification

async def set_verification_questions(questions):
    return await set_global("verification_questions", questions)

async def add_verification_question(question):
    db = await create_connection("globals")
    return await db.update_one({"_id": "verification_questions"}, {"$push": {"value": question}}, upsert=True)

async def del_verification_question(index):
    db = await create_connection("globals")
    return await db.update_one({"_id": "verification_questions"}, {"$pull": {"value": {"$index": index}}}, upsert=True)

async def swap_verification_questions(index1, index2):
    questions = await get_verification_questions()
    if index1 >= len(questions) or index2 >= len(questions):
        return
    questions[index1], questions[index2] = questions[index2], questions[index1]
    await set_verification_questions(questions)

async def edit_verification_question(index, question):
    db = await create_connection("globals")
    return await db.update_one({"_id": "verification_questions"}, {"$set": {"value.$[index]": question}}, upsert=True, array_filters=[{"index": index}])

async def get_verification_questions():
    questions = await get_global("verification_questions")
    if questions is None:
        return []
    return questions

async def add_verification(member_id, verification):
    db = await create_connection("users")
    return await db.update_one({"_id": member_id}, {"$set": {"verification": verification}}, upsert=True)


# notes

async def add_note(member_id, author_id, note):
    note = {
        "_id": utils.generate_random_id(),
        "note": note,
        "timestamp": datetime.datetime.utcnow(),
        "author": author_id,
        "user": member_id
    }
    db = await create_connection("notes")
    await db.insert_one(note)
    return note

async def get_note(note_id):
    db = await create_connection("notes")
    return await db.find_one({"_id": note_id})

async def get_notes(member_id):
    db = await create_connection("notes")
    return await db.find({"user": member_id}).sort("timestamp", pymongo.DESCENDING).to_list(None)

async def remove_note(note_id):
    db = await create_connection("notes")
    return await db.delete_one({"_id": note_id})


# role memory

async def get_roles(member_id):
    db = await create_connection("roles")
    return await db.find_one({"_id": member_id})

async def add_roles(member_id, roles):
    db = await create_connection("roles")
    return await db.update_one({"_id": member_id}, {"$set": {"roles": roles, "timestamp": datetime.datetime.utcnow()}}, upsert=True)

async def add_roles_stealth(member_id, roles):
    db = await create_connection("roles")
    return await db.update_one({"_id": member_id}, {"$set": {"roles": roles}}, upsert=True)

async def remove_roles(member_id):
    db = await create_connection("roles")
    return await db.delete_one({"_id": member_id})


# Prison Database

async def get_prisoners():
    db = await create_connection("prison")
    return await db.find().to_list(None)

async def get_expired_prisoners():
    db = await create_connection("prison")
    return await db.find({"expires": {"$lt": datetime.datetime.utcnow()}}).to_list(None)

async def add_prisoner(member_id, admin_id, roles, release_date, reason):
    db = await create_connection("prison")
    difference_in_seconds = (release_date - datetime.datetime.utcnow()).total_seconds()
    ts = utils.seconds_to_time(difference_in_seconds)
    await add_note(member_id, admin_id, f"Prisoned for '{reason}' until {release_date} ({ts}).")
    await db.insert_one({"_id": member_id, "expires": release_date, "reason": reason, "roles": roles})

async def get_prisoner(member_id):
    db = await create_connection("prison")
    return await db.find_one({"_id": member_id})

async def adjust_sentence(member_id, release_date):
    db = await create_connection("prison")
    await db.update_one({"_id": member_id}, {"$set": {"expires": release_date}})

async def remove_prisoner(member_id):
    db = await create_connection("prison")
    await db.delete_one({"_id": member_id})