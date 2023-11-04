from typing import Optional

import motor  # doing this locally instead of in database.py for greater modularity
import datetime
import random

import discord
from discord import option, slash_command
from discord.ext import commands, tasks

from . import database as db
from . import config
from . import utils
from .logging import *

"""
case = {
    "_id": "Red-Rebel-98",
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

# motion types

# stage types

# punishment codes
# BAN, KICK, PRISON, TIMEOUT, 

client = db.client
create_connection = db.create_connection

tree_types = open("wordlists/trees.txt", "r").read().splitlines()
gem_types = open("wordlists/gems.txt", "r").read().splitlines()

async def get_case(case_id: str):
    db = await create_connection("cases")
    case = await db.find_one({"_id": case_id})
    return case

async def get_case_lite(case_id: str):
    db = await create_connection("cases")
    case = await db.find_one({"_id": case_id}, {"event_log": False, "juror_chat_log": False})
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
    cases = await db.find({"status": {"$gt": 0}}).to_list(None)
    return cases

async def list_active_cases_lite():
    db = await create_connection("cases")
    cases = await db.find({"status": {"$gt": 0}}, {"event_log": False, "juror_chat_log": False}).to_list(None)
    return cases

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
    await db.update_one({"_id": case_id}, {"$set", {f"anonymization.{user_id}": user_nickname}})

async def add_jurist_to_case(case_id: str, jurist_id: int, jurist_name: str = None):
    # set jury_pool[juri_id] = jurist_name
    db = await create_connection("cases")
    await db.update_one({"_id": case_id}, {"$push": {f"jury_pool": jurist_id}}, upsert=True)
    if jurist_name:
        await db.update_one({"_id": case_id}, {"$set": {f"anonyimization.{jurist_id}": jurist_name}})

async def add_case(case_id: str, title:str, description: str, plaintiff_id: int, plaintiff_is_prosecutor: bool, defense_ids: list[int], penalty: dict, jury_pool: dict):
    db = await create_connection("cases")
    case = {
        # metadata
        "_id": case_id,
        "title": title,
        "description": description,
        "filed_date": datetime.datetime.utcnow(),
        "filed_date_utc": datetime.datetime.utcnow().timestamp(),

        # plaintiff and defense
        "plaintiff_id": plaintiff_id,
        "plaintiff_is_prosecutor": plaintiff_is_prosecutor,
        "defense_ids": defense_ids,
        
        "penalty": penalty,
        
        # processing stuff
        "stage": 1,  # 0 - done (archived), 1 - jury selection, 2 - jury consideration, 3 - argumentation / body, 4 - ready to close, awaiting archive 
        "guilty": None,
        "motion_queue": [
            {
                "name": ""
            }
        ],

        # jury stuff
        "jury_pool": jury_pool,
        "eligible_jury": [],  # people who have been invited to the jury but are yet to accept
        
        "anonymization": {},  # id: name - anybody in this list will be anonymized and referred to by their dict value
        "votes": {},  # guilty vs not guilty votes
        "event_log": [
            {
                "event_id": "open_case",
                "name": "Case Opened",
                "author_id": 0,
                "desc": f"A case has been opened.",
                "timestamp": datetime.datetime.utcnow(),
                "timestamp_utc": datetime.datetime.utcnow().timestamp(),
            }
        ],
        "juror_chat_log": []
    }
    await db.insert_one(case)
    return case

ACTIVECASES = []

"""
    def new_motion(self, author, motion_code, **kwargs):
        motionid = f"{self.case_id}-{self.motion_number}"
        self.motion_number += 1
        motion = {
            "motion_id": 
            "author": author,
            "motion_code": 
        }
        for kw in kwargs:
            motion[kw] = kwargs[kw]
        return motion 
"""


class Case:

    motion_timeout_days = 1  # how long it takes for voting to close on a motion in the absence of all parties voting

    def CreateMotion(self):
        return Motion(self).New()

    def new_event(self, event_id: str, name, desc, **kwargs):
        event = {
                    "event_id": event_id,
                    "name": name,
                    "desc": desc,
                    "timestamp": datetime.datetime.utcnow(),
                    "timestamp_utc": datetime.datetime.utcnow().timestamp(),
                }
        for kw in kwargs:
            event[kw] = kwargs[kw]
        return event

    async def generate_new_id(self):
        return
    
    async def Announce(self, content = None, embed = None, jurors: bool = True, defense: bool = True, prosecution: bool = True, news_wire: bool = True):
        # content = plain text content
        # embed = an embed
        # jurors = whether or not to send this announcement to the jury
        # defense = whether or not to send this announcement to the defense
        # prosucution = whether or not to send this announcement to the prosecution
        # news_wire = whether or not to send this announcement to the public news wire channel
        return
    
    def GenerateKnownUserName(self, user):
        return f"{user}"
    
    def NameUserByID(self, userid: int):
        if userid in self.anonymization:
            return self.anonymization[userid]
        if str(userid) in self.anonymization:
            return self.anonymization[str(userid)]
        if self.guild:
            user = self.guild.get_user(userid)
            if user:
                return user
        if userid in self.known_users:
            return self.known_users[userid]
        if str(userid) in self.known_users:
            return self.known_users[str(userid)]
        return f"Unknown User #{utils.int_to_base64(userid)}"

    def RegisterUser(user, anonymousname: str = None):
        self.known_users[user.id] = self.GenerateKnownUserName(user)
        if anonymousname:
            self.anonymization[user.id] = anonymousname

    async def Tick(self):  # called by case manager or when certain events happen, like a juror leaving the case
        if len(self.jury_pool) < 5:
            if self.stage > 1:  # juror left the case
                self.stage = 1  # back in the recruitment stage
            invites_to_send = (5 - len(self.jury_pool)) * 2   # if we need 3 more jurors, the bot will send out 6 invites
            eligible_jurors = await self.FindEligibleJurors()
            for i in range(invites_to_send):
                invitee = random.choice(eligible_jurors)
                eligible_jurors.remove(invitee)
                try:
                    await invitee.send(f"You have been invited to be a juror for `{self.case_id}`.\nTo accept, use `/jury join`.")
                    self.jury_invites.append(invitee)
                except:
                    pass  # already removed from eligible jurors
            return
        # switching from stage 1 to 2 should be done by the function which assigns a juror to the case
        if self.stage == 2:  # work the motion queue
            
            if self.motion_in_consideration != self.motion_queue[0]:  # putting up a new motion to vote
                motion_queue[0].StartVoting()

            elif len(self.motion_in_consideration["votes"]) >= len(self.jury_pool) or datetime.datetime.utcnow() < self.motion_in_consideration["expiry"]:  # everybody's voted, doesn't need to expire, or has expired
                if len(self.motion_in_consideration["votes"]["yes"]) <= len(self.motion_in_consideration["votes"]["no"]):  # needs majority yes to pass, this triggers if yes is equal to or less than no
                    explainer = "The motion has failed its vote."
                    if datetime.datetime.utcnow() < self.motion_in_consideration["expiry"]:
                        explainer += " The motion expired before all votes were cast."

                    self.event_log.append(self.new_event(
                        "motion_fail",
                        "This motion has failed its vote.",
                        explainer,
                        motion = self.motion_in_consideration
                    ))
            
            return

        if self.stage == 3:  # archive self, end the case
            # unprison prisoned users
            return

            




    async def New(self, title: str, description: str, plaintiff: discord.Member, defense: discord.Member, penalty: dict, guild):
        self.guild = guild

        self.title = title
        self.description = description
        self.case_id = await self.generate_new_id()
        self.created = datetime.datetime.utcnow()
        self.plaintiff = plaintiff
        self.defense = defense
        self.penalty = penalty
        self.stage = 1
        self.motion_queue = []
        self.motion_archive = []
        self.jury_pool = []
        self.jury_invites = []
        self.anonymization = {}
        self.known_users = {}
        self.votes = {}
        self.event_log = []
        self.juror_chat_log = []
        self.motion_in_consideration = None
        self.motion_number = 100  # motion IDs start as {caseid}-100, {caseid}-101, etc. 

        self.Save()
        ACTIVECASES.append(self)
        return self

    async def LoadFromID(self, case_id, guild):
        self.guild = guild

        ACTIVECASES.append(self)

        return
    
    def __del__(self):
        ACTIVECASES.remove(self)

    async def Save(self):
        case_dict = {
                # metadata
                "_id": self.case_id,
                "title": self.title,
                "description": self.description,
                "filed_date": self.created,
                "filed_date_utc": self.created.timestamp(),

                # plaintiff and defense
                "plaintiff_id": self.plaintiff.id,
                "defense_id": self.defense.id,
                
                "penalty": self.penalty,
                
                # processing stuff
                "stage": self.stage,  # 0 - done (archived), 1 - jury selection, 2 - argumentation / body, 3 - ready to close, awaiting archive 
                "guilty": None,
                
                "motion_number": self.motion_number,
                "motion_queue": [motion.Dict() for motion in self.motions],
                "motion_archive": self.motion_archive,

                # jury stuff
                "jury_pool": [user.id for user in self.jury_pool],
                "jury_invites": [user.id for user in self.jury_invites],  # people who have been invited to the jury but are yet to accept
                
                "anonymization": self.anonymization,  # id: name - anybody in this list will be anonymized and referred to by their dict value
                "known_users": self.known_users,

                "votes": self.votes,  # guilty vs not guilty votes
                "event_log": self.event_log,
                "juror_chat_log": self.juror_chat_log
            }
        return
    
    def __init__(self):
        return

class Motion:

    expiry_days = 1
    expiry_hours = expiry_days * 24

    Case: Case = None

    async def StartVoting(self):
        self.Expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=self.expiry_hours)
        self.Votes["Yes"] = []
        self.Votes["No"] = []
        self.Case.motion_in_consideration = self
        self.Case.event_log.append(self.Case.new_event(
            "motion_up",
            f"The motion {self.MotionID} has been put up to be considered for a vote by {self.Case.NameUserByID(self.Author.id)}.",
            f"The motion {self.MotionID} has been put up to be considered for a vote by {self.Case.NameUserByID(self.Author.id)}. \
            Unless another vote is rushed, voting will end on <t:{self.Expiry.timestamp()}:F>.",
            motion = self.Dict()
        ))

    async def VoteFailed(self):
        self.Case.event_log.append(self.Case.new_event(
            "motion_failed",
            f"The motion {self.MotionID} has failed its vote.",
            f"The motion {self.MotionID} has failed its jury vote. {len(self.Votes['Yes'])}/{len(self.Votes['No'])}",
            motion = self.Dict()
        ))
        return

    async def VotePassed(self):
        self.Case.event_log.append(self.Case.new_event(
            "motion_failed",
            f"The motion {self.MotionID} has passed its vote.",
            f"The motion {self.MotionID} has passed its jury vote. {len(self.Votes['Yes'])}/{len(self.Votes['No'])}",
            motion = self.Dict()
        ))
        return
    
    async def Execute(self):
        return

    async def Close(self, delete: bool = True):
        if len(self.No) >= len(self.Yes):
            await self.VoteFailed()
        else:
            await self.VotePassed()
            await self.Execute()
        if delete:
            del(self)


    def LoadDict(self, DBDocument: dict):
        return self
    
    def New(self, author, motion_code):
        self.Created = datetime.datetime.utcnow()
        self.Author = author
        self.MotionCode = motion_code
        self.MotionID = f"{self.Case.case_id}-M{self.Case.motion_number}"  # 11042023-M001 for example
        self.Case.motion_number += 1
        return self

    def __init__(self, Case: Case):
        self.Case = Case
        self.Expiry = None  # this is set by the motion manageer based on when it appears on the floors
        self.Votes = {}
        self.Votes["Yes"] = []
        self.Votes["No"] = []
        self.MotionID = "#NO-ID-ERR"
        return 

    def __del__(self):
        self.Case.motion_queue.remove(self)
        if self.Case.motion_in_consideration != self:
            self.Case.motion_in_consideration = None
    
    def Dict():  # like Motion.Save() but doesn't save the dictionary, just returns it instead. Motions are saved when their 
        return

class StatementMotion(Motion):
    async def Execute(self):
        self.Case.event_log.append(self.Case.new_event(
            "jury_statement",
            f"The jury has made an official statement.",
            f"Pursuant to motion {self.MotionID}, the Jury makes the following statement:\n{self.statement_content}",
            motion = self.Dict()
        ))

    def LoadDict(self, DBDocument: dict):
        super().LoadDict()
        return


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

    @jury_group.command(name="join", description="Accept an invite to join a jury.")
    @option("_id", str, "The case id to join.")
    @option("anonymize", bool, "Whether to anonymize your name in the jury pool.", default=False, required=False)
    async def jury_join(self, ctx, case_id: str):
        anonymize = False
        # anonymize = ask_yes_or_no("Would you like to anonymize yourself? You will be referred to by randomly-generated pseudonym instead of your real username.")
        case = get_case_lite(case_id)
        if not case:
            return await ctx.respond("Case not found!", ephemeral=True)
        if ctx.author.id not in case["eligible_jury"]:
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
            if len(case["jury_pool"]) < 5:  # not enough jurors
                difference = 5 - case["jury_pool"]
                offer_number = difference * 2  # send out double the invites

        return

def setup(bot):
    bot.add_cog(Justice(bot))
