from typing import Optional

import motor  # doing this locally instead of in database.py for greater modularity
import datetime

import discord
from discord import option, slash_command
from discord.ext import commands, tasks

from . import database as db
from . import config
from . import utils

"""
case = {
    "case_id": "Red-Rebel-98",
    "plaintiff_id": int,
    "plaintiff_is_prosecutor": 0,
    "defense_ids": [int, int, int],
    "pentalty": {
        "penalty_code": "ban",
        "expiry": timestamp
    },
    "guilty": None, # true, false, None
    "filed_date": datetime,
    "filed_date_utc": utc_int,
    "jury_pool": [int, int, int],
    "jury_pool_anonymization": {
        user_id_int: "Nickname"
    },
    "judgement_day": None,  # or datetime
    "votes": {
        juror_id: None, True, False
    },
    "event_log": [
        {
            event_id: "something_happened"
            name: "Something happened"
            author_id: 000  #
            desc: "Someone did something!"
            timestamp: datetime
            datetime_utc: int

        }
    ],
    "juror_chat_log": [
        {"id": int, "name": str, "content": int, "datetime": int}
    ],
}
"""

client = db.client
create_connection = db.create_connection

async def get_case(case_id: str):
    db = await create_connection("cases")
    case = await db.find_one({"case_id": case_id})
    return case

async def list_cases():  
    db = await create_connection("cases")
    cases = await db.find().to_list(None)
    return cases

# list_cases but doesn't return the event log or juror chat log, for efficiency
async def list_cases_lite():
    db = await create_connection("cases")
    cases = await db.find({}, {"event_log": False, "juror_chat_log": False}).to_list(None)
    return cases


# only returns cases that have judgement day set
async def list_active_cases():
    db = await create_connection("cases")
    cases = await db.find({"judgement_day": {"$ne": None}}).to_list(None)
    return cases

async def list_active_cases_lite():
    db = await create_connection("cases")
    cases = await db.find({"judgement_day": {"$ne": None}}, {"event_log": False, "juror_chat_log": False}).to_list(None)
    return cases


async def add_case(case_id: str, title:str, description: str, plaintiff_id: int, plaintiff_is_prosecutor: bool, defense_ids: list[int], penalty: dict, jury_pool: dict):
    db = await create_connection("cases")
    case = {
        "case_id": case_id,
        "title": title,
        "description": description,
        "plaintiff_id": plaintiff_id,
        "plaintiff_is_prosecutor": plaintiff_is_prosecutor,
        "defense_ids": defense_ids,
        "penalty": penalty,
        "guilty": None,
        "filed_date": datetime.datetime.utcnow(),
        "filed_date_utc": datetime.datetime.utcnow().timestamp(),
        "jury_pool": jury_pool,
        "judgement_day": None,
        "votes": {},
        "event_log": [],
        "juror_chat_log": []
    }
    await db.insert_one(case)
    return case

class NewCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_potential_juror(self, member):
        return True

    async def list_potential_jurors(self):
        guild = self.bot.get_guild(config.C["guild_id"])
        eligible = []
        right_wing_role = guild.get_role(config.C["rightwing_role"])

        for member in guild.members:
            if member.bot:
                continue
            # disqualify if admin
            if member.guild_permissions.ban or member.guild_permissions.kick or member.guild_permissions.manage_roles or member.guild_permissions.manage_messages or member.guild_permissions.manage_guild:
                continue
            # disqualify if hasn't been a member for more than x days
            join_requried_days = 21
            if (datetime.datetime.utcnow() - member.joined_at).days < join_requried_days:
                continue
            # disqualify if has right wing role
            if right_wing_role in member.roles:
                continue
            profile = await db.get_user(member.id)
            # disqualify if jury_banned
            if "jury_banned" in profile:
                continue
            # disqualify if less than x messages
            message_requried_count = 100
            if profile["messages"] < message_requried_count:
                continue
            # disqualify if more than x days since last message
            if "last_seen" not in profile:
                continue    
            message_requried_days = 7
            if (datetime.datetime.utcnow() - profile["last_seen"]).days > message_requried_days:
                continue
        
            eligible.append(member)

        return eligible



    @slash_command(name='')

    @slash_command(name='simonsays', description='Repeat what Simon says.')
    @option('text', str, description='The text to repeat')
    async def player_info(self, ctx, text:str):
        await ctx.respond("Simon says " + text, ephemeral=True)

    # add option to report a user by right clicking a message
    @commands.message_command(name="Report Message to Server Staff")
    async def report_message(self, ctx, message: discord.Message):
        embed=discord.Embed(title="Message Report", description="Message reported to server staff.", color=0xff0000)
        embed.set_author(name=f"{message.author.display_name} ({message.author.id})", url=message.jump_url, icon_url=message.author.display_avatar)
        embed.set_footer(text=f"Reported by {ctx.author.display_name} ({message.author.id})")

        embed.add_field(name="Message Content", value=message.content, inline=False)
        for attachment in message.attachments:
            embed.add_field(name="Attachment", value=f"[{attachment.filename}]({attachment.url})", inline=False)

        await ctx.send(embed=embed)


    @commands.Cog.listener()
    async def on_message(self, message):
        return

def setup(bot):
    bot.add_cog(NewCog(bot))
