from typing import Optional

import motor  # doing this locally instead of in database.py for greater modularity
import datetime

import discord
from discord import option, slash_command
from discord.ext import commands, tasks

from . import database as db
from . import config
from . import utils
from .logging import *

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
    "anonymization": {
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

tree_types = open("wordlists/trees.txt", "r").read().splitlines()
gem_types = open("wordlists/gems.txt", "r").read().splitlines()

async def get_case(case_id: str):
    db = await create_connection("cases")
    case = await db.find_one({"case_id": case_id})
    return case

async def get_case_lite(case_id: str):
    db = await create_connection("cases")
    case = await db.find_one({"case_id": case_id}, {"event_log": False, "juror_chat_log": False})
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

async def add_jurist_to_case(case_id: str, jurist_id: int, jurist_name: str):
    # set jury_pool[juri_id] = jurist_name
    db = await create_connection("cases")
    await db.update_one({"case_id": case_id}, {"$set": {f"jury_pool.{jurist_id}": jurist_name}}, upsert=True)

async def resolve_party_name(case_id: str, user_id: int):
    case_ = await get_case_lite(case_id)
    if case_ is None:
        return None
    if str(user_id) in case_["anonymization"]:
        return case_["anonymization"][str(user_id)]
    # TODO: guild.get user and await client.fetch_user, try to see if caching system for fetch_user can be used
    return f"Unknown to the Case (#{user_id})"

async def add_anonymous_user(case_id: str, user_id: int, user_nickname: str):
    case_ = await get_case_lite(case_id)
    if not case_:   return None
    db = await create_connection("cases")
    await db.update_one({"case_id": case_id}, {"$set", {f"anonymization.{user_id}": user_nickname}})


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
        "eligible_jury": [],  # people who have been invited to the jury but are yet to accept
        "anonymization": [],
        "judgement_day": None,
        "votes": {},
        "event_log": [],
        "juror_chat_log": []
    }
    await db.insert_one(case)
    return case
    

class Justice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CaseManager.start()

    async def is_potential_juror(self, member, guild=None):
        if not guild:
            guild = self.bot.get_guild(config.C["guild_id"])

        join_requried_days = 21
        message_requried_count = 100
        last_message_max_age = 7
        right_wing_role = guild.get_role(config.C["rightwing_role"])


        if member.bot:
            return False
        # disqualify if admin
        if member.guild_permissions.ban or member.guild_permissions.kick or member.guild_permissions.manage_roles or member.guild_permissions.manage_messages or member.guild_permissions.manage_guild:
            return False
        # disqualify if hasn't been a member for more than x days
        if (datetime.datetime.utcnow() - member.joined_at).days < join_requried_days:
            return False
        # disqualify if has right wing role
        if right_wing_role in member.roles:
            return False
        profile = await db.get_user(member.id)
        # disqualify if jury_banned
        if "jury_banned" in profile:
            return False
        # disqualify if less than x messages
        if profile["messages"] < message_requried_count:
            return False
        # disqualify if more than x days since last message
        if "last_seen" not in profile:
            return False    
        if (datetime.datetime.utcnow() - profile["last_seen"]).days > last_message_max_age:
            return False
        return True

    async def list_potential_jurors(self):
        guild = self.bot.get_guild(config.C["guild_id"])
        eligible = []
        right_wing_role = guild.get_role(config.C["rightwing_role"])

        for member in guild.members:
            if await self.is_potential_juror(member, guild):  # supply guild to save more time
                eligible.append(member)

        return eligible

    jury_group = discord.SlashCommandGroup("jury", "Commands related to the jury system.")

    jury_invites = {}

    @jury_group.command(name="join", description="Accept an invite to join a jury.")
    @option("case_id", str, "The case id to join.")
    @option("anonymize", bool, "Whether to anonymize your name in the jury pool.", default=False, required=False)
    async def jury_join(self, ctx, case_id: str, anonymize: bool = False):
        case = get_case_lite(case_id)
        if not case:
            return await ctx.respond("Case not found!", ephemeral=True)
        if ctx.author.id not in self.jury_invites[case_id]:
            return await ctx.respond("You have not been invited to this case or the case is not accepting new jurors.", ephemeral=True)
        if not await self.is_potential_juror(ctx.author):  # this should never happen, as a check is done before the invite is sent
            return await ctx.respond("You are no longer eligible to be a juror.", ephemeral=True)
        name = ctx.author.name
        if anonyimize:
            pass # TODO: have this guide the user through choosing a pseudonym
        await add_jurist_to_case(case_id, ctx.author.id, name)

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

    @tasks.loop(minutes=15)
    async def CaseManager(self):
        log("Justice", "CaseManager", "Doing Periodic Case Manager Loop")
        cases = await list_active_cases_lite()
        for case in cases:
            if case["jury_pool"] < 5:  # not enough jurors
                difference = 5 - case["jury_pool"]
                offer_number = difference * 2  # send out double the invites

        return

def setup(bot):
    bot.add_cog(Justice(bot))
