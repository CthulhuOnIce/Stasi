from __future__ import annotations
from typing import *

# this file is for testing Case classes, Motion classes, and implementations of such
# PORTED IMPORTS
import datetime
import random
from .stasilogging import *
import io
import zipfile
from discord import Embed
import discord
import simplejson as json
from . import utils
from . import database as db
import time
from . import config
from . import warden
from . import evidence

nouns = open("wordlists/nouns.txt", "r").read().split("\n")
adjectives = open("wordlists/adjectives.txt", "r").read().split("\n")
elements = open("wordlists/elements.txt", "r").read().split("\n")

# --- END DEBUG CLASSES AND FUNCTIONS - EVERYTHING BELOW MUST BE PORTED TO THE BOT ---

"""
This library is for managing cases, motions, and other court-related things.
Court cases are basically just a collection of metadata, a list of motions, and a list of events.
They are designed to allow for more public participation in server moderation, and to get "public" interest up.

Cases are stored in a database, and are loaded into memory when the bot starts up.
Cases are also saved to the database when they are updated, and when the bot shuts down.
Cases are not saved to the database when they are closed, as they are archived and removed from memory.
When this happens, they are saved to a zip file and sent to relevant discord channels. 

Cases are created by the plaintiff, and the defendant is notified.
The plaintiff can also offer a plea deal at any time, including before jury selection, and the defendant can accept or decline.
The bot is meant to handle most communication in case-related matters, to allow for greater archival capacity, and the 
ability to anonymize jurors.

Cases are created with a title, description, and a list of penalties.
Penalties are o_summary_bjects which are executed when a case is closed, and can be warnings, bans, or prison sentences.
Penalties are also used in plea deals, and can be modified by the plaintiff and defendant at any time.
Penalties are also used in motions, and can be modified by the plaintiff and defendant at any time.

Feature Complete:
- [ ] Penalty Drafting UI
- [ ] Implement All Motion
- [ ] Evidence Management
- [ ] Juror Chat
- [ ] Remove jurors from juries if they leave the server
- [ ] Remove jurors from juries if case is officially filed against them
- [ ] Make Case selection dict persistent

Commands:
- [ ] /case view status
- [ ] /case view motionqueue
- [ ] /case view eventlog [reverse=True]
- [ ] /case view discovery
- [ ] /case view evidence [evidenceid]


Tutorial:
- [ ] /case help


- [ ] /case move statement - To file a motion to have the court make an official statement 
- [ ] /case move adjustpenalty - Move to adjust the penalty of a guilty conviction
- [ ] /case move order - File a motion to procure a court order
- [ ] /case move censure - File a motion to prevent a specific party in the case from doing a specific thing for a limited time

- [ ] /case move expedite - File a motion to expedite another motion
- [ ] /case move batch - File a motion to batch dismiss or pass other motions

- [ ] /case evidence strike - File a motion to strike evidence from the case, or if you submitted it, strike it from the case immediately.
- [ ] /case evidence interview - Interview a user through Stasi and admit it as evidence
- [ ] /case evidence statement - Ask a user for a single statement through Stasi and admit that as evidence.
- [ ] /case evidence message - Submit a message link to have it archived as evidence
- [ ] /case evidence upload - Upload a file as evidence

- [ ] /case motion withdraw - To withdraw a motion

All in one suite for managing plea deals.
When ran by the plaintiff, allows them to offer a plea deal and check on it, or withdraw/modifiy it.
When ran by the defense, allows them to accept or decline a plea deal.
- [ ] /case plea offer
"""

ACTIVECASES: List[Case] = []

def getCaseByID(case_id: str) -> Case:
    case_id = case_id.lower()  # just in case
    for case in ACTIVECASES:
        if case.id == case_id:
            return case
    return None

async def populateActiveCases(bot, guild: discord.Guild) -> List[Case]:
    t = time.time()
    log("Case", "populateActiveCases", f"Populating active cases for guild {guild.id} ({guild.name})")
    db_ = await db.create_connection("cases")
    cases = await db_.find().to_list(None)
    for case in cases:
        new_case = Case(bot, guild)
        new_case.loadFromDict(case)
        ACTIVECASES.append(new_case)
    log("Case", "populateActiveCases", f"Populated {len(ACTIVECASES)} active cases for guild {guild.id} ({guild.name}) in {round(time.time() - t, 5)} seconds")
    return ACTIVECASES

def memberIsJuror(member: discord.Member) -> bool:
    member = member if isinstance(member, int) else member.id  # we don't actually care about the member object, just the id
    for case in ACTIVECASES:
        if member in case.jury_pool_ids:
            return True
    return False

def getCasesByJuror(member: discord.Member) -> List[Case]:
    member = member if isinstance(member, int) else member.id  # we don't actually care about the member object, just the id
    cases = []
    for case in ACTIVECASES:
        if member in case.jury_pool_ids:
            cases.append(case)
    return cases

# makes intellisense work for event dictionaries
class Event(TypedDict):
    event_id: str
    name: str
    desc: str
    timestamp: datetime.datetime
    timestamp_utc: float

class Penalty:
    def __init__(self, case):
        self.case: Case = case
        return

    def __str__(self):
        return self.describe()

    def __repr__(self):
        return self.describe()

    def describe(self):
        return "Blank Penalty"
    
    def save(self):
        s = self.__dict__
        s["type"] = self.__class__.__name__
        if "case" in s:
            del s["case"]
        return s

    def load(self):
        return
    
    async def Execute(self):
        return

class WarningPenalty(Penalty):
    def __init__(self, case):
        super().__init__(case)
        self.warning_text = None
        return
    
    def New(self, warning_text: str):
        self.warning_text = warning_text
        return self

    def describe(self):
        return f"Warning: {self.warning_text}"

    # needs to be made async for implementation
    async def Execute(self):
        # note = await db.add_note(self.case.defense.id, self.case.plaintiff.id, f"User Warned as Penalty of Case {self.case.id}: `{self.warning_text}`")
        print(f"User Warned as Penalty of Case {self.case.id}: `{self.warning_text}`")
    
class PermanentBanPenalty(Penalty):
    def __init__(self, case):
        super().__init__(case)
        self.ban_text = None
        return
    
    def New(self, ban_text: str):
        self.ban_text = ban_text
        return self
    
    def describe(self):
        return f"Permanent Ban: {self.ban_text}"
    
    async def Execute(self):
        # await self.case.guild.ban(self.case.defense, reason=f"User Banned as Penalty of Case {self.case.id}: `{self.ban_text}`")
        self.case.guild.ban(self.case.defense(), reason=f"User Banned as Penalty of Case {self.case.id}: `{self.ban_text}`")
        print(f"User Banned as Penalty of Case {self.case.id}: `{self.ban_text}`")

class PrisonPenalty(Penalty):
    def __init__(self, case):
        super().__init__(case)
        self.prison_length_seconds = None
        return

    def New(self, prison_length_seconds: int):
        self.prison_length_seconds = prison_length_seconds
        return self
    
    def describe(self):
        if self.prison_length_seconds > 0:
            return f"Prison: {utils.seconds_to_time_long(self.prison_length_seconds)}"
        else:
            return f"Prison: Permanent / Indefinite"
        
    async def Execute(self):
        await warden.newWarrant(self.case.defense(), "case", f"Case {self.case.id} Verdict", self.case.plaintiff_id, self.prison_length_seconds)

def penaltyFromDict(case, d: dict) -> Penalty:
    # dynamically locate the class and instantiate it
    for subclass in Penalty.__subclasses__():
        if subclass.__name__ == d["type"]:
            new_penalty = subclass(case)
            # assign all the values from the dictionary to the new penalty
            for key in d:
                new_penalty.__dict__[key] = d[key]
            return new_penalty

def eventToEmbed(event: Event, case_name: str) -> discord.Embed:
    embed = discord.Embed(title=event["name"], description=event["desc"], timestamp=event["timestamp"])
    embed.set_footer(text=f"Event ID: {event['event_id']}")
    icon_url = utils.twemojiPNG.normal
    
    if event["event_id"] == "case_filed":
        icon_url = utils.twemojiPNG.opencab
    elif event["event_id"] == "status_update":
        icon_url = utils.twemojiPNG.label
    elif event["event_id"] == "juror_join":
        icon_url = utils.twemojiPNG.scale
    elif event["event_id"] == "juror_leave":
        icon_url = utils.twemojiPNG.scale
    elif event["event_id"] == "motion_up":
        icon_url = utils.twemojiPNG.ballot
    elif event["event_id"] == "personal_statement":
        icon_url = utils.twemojiPNG.leftchat

    if event["event_id"] == "evidence_submit":
        icon_url = utils.twemojiPNG.folder
        if "evidence" in event:
            embed.description = f"New Evidence Submitted "
            embed.add_field(name="File Name", value=f"{event['evidence']['filename']}", inline=False)
            embed.add_field(name="Evidence ID", value=f"{event['evidence']['id']}", inline=False)

    embed.set_author(name=case_name, icon_url=icon_url)
    return embed

class Case:

    motion_timeout_days = 1  # how long it takes for voting to close on a motion in the absence of all parties voting

    def describePenalties(self, penalties: List[Penalty]) -> str:

        if not penalties:
            penalties = self.penalties
        
        if isinstance(penalties, Penalty):
            penalties = [penalties]

        penalty_desc = [penalty.describe() for penalty in penalties]
        penalty_str = "\n".join([f"- {penalty}" for penalty in penalty_desc])
        return penalty_str

    async def newEvent(self, event_id: str, name, desc, **kwargs) -> Event:
        event = {
                    "event_id": event_id,
                    "name": name,
                    "desc": desc,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc),
                    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).timestamp(),
                }
        for kw in kwargs:
            event[kw] = kwargs[kw]
        
        await self.Announce(None, embed=eventToEmbed(event, f"{self} ({self.id})"), jurors=True, defense=True, prosecution=True, news_wire=True)

        log("CaseEventLog", "newEvent", f"New event {self} ({self.id}): {event}", False)

        return event
    
    class Statement(TypedDict):
        author_id: int
        content: str

    async def personalStatement(self, author, text):

        statement: self.Statement = {
            "author_id": author.id,
            "content": text,
            "timestamp": datetime.datetime.now(datetime.timezone.utc)
        }

        self.personal_statements.append(statement)
        self.event_log.append(await self.newEvent(
            "personal_statement",
            f"{self.nameUserByID(statement['author_id'])} has submitted a personal statement",
            f"{self.nameUserByID(statement['author_id'])} has submitted a personal statement:\n{statement['content']}",
            statement = statement
        ))

        log("Case", "personalStatement", f"New personal statement from {self.nameUserByID(statement['author_id'])} ({statement['author_id']}) for case {self} ({self.id})")

        await self.Save()

        return statement

    async def offerPleaDeal(self, penalties: List[Penalty], expiration: datetime.datetime = None):
        self.plea_deal_penalties = penalties

        desc = f"{self.nameUserByID(self.defense.id)} has offered a plea deal.\nOld Penalties:\n{self.describePenalties(self.penalties)}\n\nBargain Penalties:\n{self.describePenalties(penalties)}"
        if expiration:
            desc += f"\n\nThis plea deal will expire on {discord_dynamic_timestamp(expiration, 'F')} ({discord_dynamic_timestamp(expiration, 'R')})"
            self.plea_deal_expiration = expiration
        
        self.event_log.append(await self.newEvent(
            "plea_deal",
            f"{self.nameUserByID(self.defense.id)} has offered a plea deal.",
            desc
        ))
        return
    
    class jsay(TypedDict):
        user_id: int
        content: str
        timestamp: datetime.datetime
    
    def juror_say(self, user, content):
        jsay: jsay = {
            "user_id": user.id,
            "content": content,
            "timestamp": datetime.datetime.now(datetime.timezone.utc)
        }

        self.juror_chat_log.append(jsay)

        for juror in self.jury_pool():
            juror.send(f"**JSAY: {self.nameUserByID(user.id)}:** {content}")

        log("Case", "JSAY", f"{self.nameUserByID(user.id)} ({user.id}): {self.id}: {content}")
        
        return jsay

    
    async def declinePleaDeal(self):
        self.plea_deal_penalties = []
        self.plea_deal_expiration = None
        self.event_log.append(await self.newEvent(
            "plea_deal_declined",
            f"{self.nameUserByID(self.plaintiff_id)} has declined the plea deal.",
            f"{self.nameUserByID(self.plaintiff_id)} has declined the plea deal."
        ))
        return
    
    async def acceptPleaDeal(self):
        self.penalties = self.plea_deal_penalties
        self.plea_deal_penalties = []
        # 
        self.plea_deal_expiration = None
        self.event_log.append(await self.newEvent(
            "plea_deal_accepted",
            f"{self.nameUserByID(self.plaintiff_id)} has accepted the plea deal.",
            f"{self.nameUserByID(self.plaintiff_id)} has accepted the plea deal."
        ))
        return

    async def executePunishments(self):
        for penalty in self.penalties:
            await penalty.Execute()
        return
    
    # doesn't log or document the case closing, or act on punishments, which should all be done by 
    # preceding functions
    async def closeCase(self):
        self.no_tick = True 
        self.stage = 3
        ACTIVECASES.remove(self)
        for evidence in self.evidence:
            await evidence.delete()
        db_ = await db.create_connection("cases")
        await db_.delete_one({"_id": self.id})
        log("Case", "close_case", f"Case {self} ({self.id}) closed.")
        return

    def generateNewID(self):
        candidate = f"{datetime.datetime.now(datetime.timezone.utc).strftime('%m%d%Y')}-{random.randint(100, 999)}"
        while getCaseByID(candidate):
            candidate = f"{datetime.datetime.now(datetime.timezone.utc).strftime('%m%d%Y')}-{random.randint(100, 999)}"
        return candidate

    async def Announce(self, content: str = None, embed: discord.Embed = None, jurors: bool = True, defense: bool = True, prosecution: bool = True, news_wire: bool = True):
        # content = plain text content
        # embed = an embed
        # jurors = whether or not to send this announcement to the jury
        # defense = whether or not to send this announcement to the defense
        # prosucution = whether or not to send this announcement to the prosecution
        # news_wire = whether or not to send this announcement to the public news wire channel

        recipients = []
        if jurors:
            recipients.extend(self.jury_pool())
        if defense:
            recipients.append(self.defense())
        if prosecution:
            recipients.append(self.plaintiff())
        if news_wire:
            recipients.append(self.guild.get_channel(863539768306171928))

        for recipient in recipients:
            try:
                if content:
                    await recipient.send(content)
                if embed:
                    await recipient.send(content, embed=embed)
            except:
                pass

    def registerUser(self, user, anonymousname: str = None):
        # TODO: decide whether known_users is mapped to int or str and remove these double cases
        if user.id in self.known_users or str(user.id) in self.known_users:  # don't re-register
            return
        
        self.known_users[user.id] = utils.normalUsername(user)
        if anonymousname:
            self.anonymization[user.id] = anonymousname

    def nameUserByID(self, userid: int, title: bool = True):
        # TODO: Docstring
        userid = int(userid)
        if userid in self.anonymization:
            res = self.anonymization[userid]
       
        elif str(userid) in self.anonymization:
            res = self.anonymization[str(userid)]
       
        elif userid in self.known_users:
            res = self.known_users[userid]
       
        elif str(userid) in self.known_users:
            res = self.known_users[str(userid)]
    
        # last resort, look them up and register them
        elif self.guild:
            user = self.guild.get_member(userid)
            if user:
                # TODO: change to log
                print(f"nameUserByID for {self} ({self.id}) just had to look up an unregistered user {user} ({user.id}), make sure you're registering users to cases properly")
                self.registerUser(user)
                res = utils.normalUsername(user)

        if title:
            if userid == self.defense_id:
                res += " (Defense)"

            elif userid == self.plaintiff_id:
                res += " (Plaintiff)"
            
            else:
                if userid in self.jury_pool_ids:
                    res += " (Juror)"


        if res:
            return res
        else:
            # TODO: change to log
            print(f"nameUserByID for {self.case} ({self.case.id}) Could not look up {userid}. This should never happen.")
            return f"Unknown User #{utils.int_to_base64(userid)}"
        
    def canVote(self, user: discord.Member):
        if user.id in self.jury_pool_ids:
            return True
        else:
            return False
        
    def canSubmitMotions(self, user: discord.Member):
        if user.id == self.plaintiff_id:
            return True
        if user.id == self.defense_id:
            return True
        if user.id in self.jury_pool_ids:
            return True
        else:
            return False
        
    async def removeJuror(self, user: discord.Member, reason = None):
        user = user if isinstance(user, int) else user.id  # we don't actually care about the member object, just the id

        desc = f"{self.nameUserByID(user)} has left the jury."
        if reason:
            desc += f"\n\nReason: {reason}"
        if user in self.jury_pool_ids:
            self.jury_pool_ids.remove(user)
            self.event_log.append(await self.newEvent(
                "juror_leave",
                f"{self.nameUserByID(user)} has left the jury.",
                desc,
                juror = user
            ))
            await self.Tick()  # immediately tick to check if we need to re-select jurors
            return True
        else:
            return False

    async def findEligibleJurors(self) -> List[discord.Member]:
        t = time.time()
        log("Case", "findEligibleJurors", f"Finding eligible jurors for case {self} ({self.id})")
        d_b = await db.create_connection("users")
        user = await d_b.find({
            # last seen less than 2 weeks ago
            "last_seen": {"$gt": datetime.datetime.utcnow() - datetime.timedelta(days=14)},
            # greater than 100 messages
            "messages": {"$gt": 100},
            # doesn't have "jury_ban" key set
            "jury_ban": {"$exists": False},
        }).to_list(None)

        # resolve user ids to discord.Member objects
        disqualified = []
        for case in ACTIVECASES:
            disqualified.extend([case.defense_id, case.plaintiff_id])

        user_resolved = []
        for u in user:
            if u["_id"] in self.jury_pool_ids:
                continue
            if u["_id"] in self.jury_invites:
                continue
            if u["_id"] in disqualified:
                continue

            disqual_role = self.guild.get_role(config.C["rightwing_role"])
            member: discord.Member = self.guild.get_member(u["_id"])
            if member:
                if member.guild_permissions.administrator:
                    continue
                if member.guild_permissions.ban_members:
                    continue
                if disqual_role and disqual_role in member.roles:
                    continue
                user_resolved.append(member)
        log("Case", "findEligibleJurors", f"Found {len(user_resolved)} eligible jurors for case {self} ({self.id}) in {round(time.time() - t, 5)} seconds")
        return user_resolved
    

    
    async def addJuror(self, user: discord.Member, pseudonym: str = None):
        
        self.jury_pool_ids.append(user.id)

        if user.id in self.jury_invites:
            self.jury_invites.remove(user.id)
        
        self.registerUser(user, pseudonym)
        
        self.event_log.append(await self.newEvent(
            "juror_join",
            f"{self.nameUserByID(user.id)} has joined the jury.",
            f"{self.nameUserByID(user.id)} has joined the jury.",
            juror = user.id
        ))

        # TODO: better introduction and quickstart guide
        msg =  f"You have joined the jury for **{self.title}** (`{self.id}`).\n"
        msg += f"Your job is to vote on motions presented in court, consider evidence, and ultimately decide the verdict.\n"
        msg += f"You will be notified automatically for case updates.\n"

        await user.send(msg)
        await self.Save()

        return
    
    async def Tick(self):
        # await self.Save()
        await self.HeartBeat()
        await self.Save()

    async def HeartBeat(self):  # called by case manager or when certain events happen, like a juror leaving the case

        if self.no_tick:
            return
        
        # Sanity checks, this should be handled by on_member_remove, but just in case, we'll do it here too
        # for if the bot is down or something
        removed_jurors = []
        for juror_id in self.jury_pool_ids:
            user = self.guild.get_member(juror_id)
            if not user:
                self.jury_pool_ids.remove(juror_id)
                removed_jurors.append(juror_id)
        
        if removed_jurors:
            self.event_log.append(await self.newEvent(
                "juror_leave",
                f"{len(removed_jurors)} jurors have left the case.",
                f"{len(removed_jurors)} jurors were removed from the case after leaving the server:\n{', '.join([self.nameUserByID(juror_id) for juror_id in removed_jurors])}",
                jurors = removed_jurors
            ))
        
        # check if plea bargain has expired
        if self.plea_deal_expiration and datetime.datetime.now(datetime.timezone.utc) > self.plea_deal_expiration:
            self.plea_deal_penalties = []
            self.plea_deal_expiration = None
            self.event_log.append(await self.newEvent(
                "plea_deal_expired",
                f"The plea deal has expired.",
                f"The plea deal has expired and is no longer offered.",
                penalties = self.penalties
            ))

        if len(self.jury_pool_ids) < 5:
            # juror left the case, but it was already in the body stage
            # when this happens, the case basically has to revert to the recruitment stage
            if self.stage > 1:  
                self.updateStatus("Jury Re-Selection to Fill Vacancy")
                for motion in self.motion_queue:
                    await motion.CancelVoting(reason=f"Jury cannot act on motions until 5 jurors are present.")
                self.stage = 1  # back in the recruitment stage
            invites_to_send = random.randint(2, 3)  # send 2-3 invites per cycle
            eligible_jurors = await self.findEligibleJurors()
            for invitee in random.sample(eligible_jurors, invites_to_send):
                try:
                    log("Case", "InviteSent", f"Sending jury invite to {utils.normalUsername(invitee)} ({invitee.id}) for case {self} {self.id}")
                    self.jury_invites.append(invitee.id)
                    # await invitee.send(f"You have been invited to be a juror for {self.title} (`{self.id}`).\nTo accept, use `/jury join {self.id}`.")
                except:
                    pass  # already removed from eligible jurors
            return
        
        elif self.stage == 1:  # we have jurors selected, so move the case to the next stage
            self.updateStatus("Argumentation and Case Body")
            self.stage = 2
        
        # switching from stage 1 to 2 should be done by the function which assigns a juror to the case
        if self.stage == 2 and len(self.motion_queue):  # work the motion queue
            
            if self.motion_in_consideration != self.motion_queue[0]:  # putting up a new motion to vote
                await self.motion_queue[0].startVoting()

            elif self.motion_in_consideration.ReadyToClose():  # everybody's voted, doesn't need to expire, or has expired
                await self.motion_in_consideration.Close()
                if len(self.motion_queue):  # if there's another motion in the queue, start voting on it
                    await self.motion_queue[0].startVoting()
            
            return

        if self.stage == 3:  # archive self, end the case
            # unprison prisoned users
            return
        
    def getMotionByID(self, motionid: str) -> "Motion":
        motionid = motionid.lower()
        for motion in self.motion_queue:
            if motion.MotionID.lower() == motionid:
                return motion
        return None
    
    def getEvidenceByID(self, evidenceid: str) -> evidence.Evidence:
        evidenceid = evidenceid.lower()
        for evidence in self.evidence:
            if evidence.id.lower() == evidenceid:
                return evidence
        return None

    def getUser(self, userid: int) -> discord.Member:
        if isinstance(userid, str):
            userid = int(userid)
        return self.guild.get_member(userid)

    def fetchUser(self, userid: int) -> discord.Member:
        if isinstance(userid, str):
            userid = int(userid)
            
        if got := self.getUser(userid):
            return got
        elif got := self.guild.get_member(userid):
            return got

    def plaintiff(self):
        return self.fetchUser(self.plaintiff_id)

    def defense(self):
        return self.fetchUser(self.defense_id)
    
    def jury_pool(self):
        return [self.fetchUser(user) for user in self.jury_pool_ids]

    async def New(self, plaintiff: discord.Member, defense: discord.Member, penalties: List[Penalty], description: str) -> Case:

        if isinstance(penalties, Penalty):
            penalties = [penalties]

        self.title = f"{utils.normalUsername(plaintiff)} v. {utils.normalUsername(defense)}"
        self.description = description
        # "Jury Selection", "Guilty", "Not Guilty", 
        self.status = "Jury Selection"
        self.id = self.generateNewID()
        self.created = datetime.datetime.now(datetime.timezone.utc)
        self.evidence: List[evidence.Evidence] = []
        self.evidence_number = 101

        self.plaintiff_id = plaintiff.id
        self.defense_id = defense.id
        self.penalties: List[Penalty] = penalties

        self.plea_deal_penalties: List[Penalty] = []
        self.plea_deal_expiration: datetime.datetime = None
        self.motion_in_consideration = None


        self.stage = 1
        self.motion_queue: List[Motion] = []
        # used to keep track of timeouts and whatnot
        self.locks = []
        self.personal_statements = []
        self.jury_pool_ids = []
        self.jury_invites = []
        self.anonymization = {}
        
        self.known_users = {}
        self.registerUser(plaintiff)
        self.registerUser(defense)

        # MIGHT REMOVE in favor of delivering verdict ny a motion
        # alternatively, keep in place for archive purposes
        self.votes = {}
        self.event_log: List[Event] = [await self.newEvent(
            "case_filed",
            f"Case {self.id} has been filed.",
            f"Case {self.id} has been filed by {self.nameUserByID(self.plaintiff_id)} against {self.nameUserByID(self.defense_id)}.\n{self.description}"
        )]
        self.juror_chat_log = []
        self.motion_in_consideration: Motion = None
        self.motion_number = 101  # motion IDs start as {caseid}-101, {caseid}-102, etc. 
        self.evidence_number = 101 # evidence IDs start as {caseid}-101, {caseid}-102, etc.

        # if this is set to true, Tick() won't do anything, good for completely freezing the case 
        self.no_tick: bool = False

        log("Case", "New", f"Created new case {self.id} with title {self.title}")
        await self.Save()

        ACTIVECASES.append(self)
        return self

    async def newEvidence(self, author: discord.Member, filename: str, file: io.BytesIO) -> evidence.Evidence:

        self.registerUser(author)  

        evidence_tag = "N"
        if author.id == self.plaintiff_id:
            evidence_tag = "P"
        elif author.id == self.defense_id:
            evidence_tag = "D"
        elif author.id in self.jury_pool_ids:
            evidence_tag = "J"

        evidence_id = f"{self.id}-{evidence_tag}{self.evidence_number}"
        new_evidence = evidence.Evidence(evidence_id)
        await new_evidence.New(filename, file, author.id)

        self.evidence.append(new_evidence)
        self.event_log.append(await self.newEvent(
            "evidence_submit",
            f"{self.nameUserByID(author.id)} has submitted evidence.",
            f"{self.nameUserByID(author.id)} has submitted evidence:\n{filename} ({evidence_id})",
            evidence = new_evidence.__dict__
        ))

        self.evidence_number += 1
        await self.Save()
        return new_evidence

    def LoadFromID(self, case_id, guild):
        self.guild = guild

        ACTIVECASES.append(self)

        return 
    
    def __del__(self):
        log("Case", "CaseDelete", f"Case {self} ({self.id}) has been deleted")

    def __str__(self):
        return self.title
    
    def __repr__(self):
        return self.title
    
    async def updateStatus(self, new_status: str):
        old_status = self.status
        self.status = new_status
        self.event_log.append(await self.newEvent(
            "case_status_update",
            f"The status of the case has been updated.",
            f"Case {self.id} has been updated.\nStatus: {old_status} -> {new_status}"
        ))
        return

    async def Save(self):
        
        t = time.time()
        log("Case", "Save", f"Saving case {self.id} to database")

        case_dict = {
                # metadata
                "_id": self.id,
                "title": self.title,
                "description": self.description,
                "status": self.status,
                "filed_date": self.created,
                "filed_date_timestamp": self.created.timestamp(),

                # plaintiff and defense
                "plaintiff_id": self.plaintiff_id,
                "defense_id": self.defense_id,

                "personal_statements": self.personal_statements,
                "motion_in_consideration": self.motion_in_consideration.MotionID if self.motion_in_consideration else None,

                "locks": self.locks,
                
                "penalties": [penalty.save() for penalty in self.penalties],
                "plea_deal_penalties": [penalty.save() for penalty in self.plea_deal_penalties],
                "plea_deal_expiration": self.plea_deal_expiration,
                
                # processing stuff
                "stage": self.stage,  # 0 - done (archived), 1 - jury selection, 2 - argumentation / body, 3 - ready to close, awaiting archive 
                "guilty": None,
                
                "evidence_number": self.evidence_number,
                "evidence": [evidence.__dict__ for evidence in self.evidence],

                "motion_number": self.motion_number,
                "motion_queue": [motion.Dict() for motion in self.motion_queue],

                # jury stuff
                # TODO: turn jury_pool (list[member]) into jury_pool_ids (list[int]), and use jury_pool() method to resolve jury pool as members instead
                # TODO: do a similar thing with plaintiff and defense 
                "jury_pool_ids": self.jury_pool_ids,
                "jury_invites": self.jury_invites,  # people who have been invited to the jury but are yet to accept

                "anonymization": {str(key): self.anonymization[key] for key in self.anonymization},
                "known_users": {str(key): self.known_users[key] for key in self.known_users},

                "votes": self.votes,  # guilty vs not guilty votes
                "event_log": self.event_log,
                "juror_chat_log": self.juror_chat_log,
                
                "no_tick": self.no_tick
            }

        db_ = await db.create_connection("cases")
        await db_.update_one({"_id": self.id}, {"$set": case_dict}, upsert=True)



        log("Case", "Save", f"Saved case {self.id} to database in {round(time.time() - t, 5)} seconds")

        return case_dict
    
    def loadFromDict(self, d: dict):
        t = time.time()

        self.id = d["_id"]
        self.title = d["title"]
        self.description = d["description"]
        self.status = d["status"]
        self.created = d["filed_date"]

        self.plaintiff_id = d["plaintiff_id"]
        self.defense_id = d["defense_id"]

        self.personal_statements = d["personal_statements"]
        self.locks = d["locks"]

        self.penalties = [penaltyFromDict(self, penalty) for penalty in d["penalties"]]
        self.plea_deal_penalties = [penaltyFromDict(self, penalty) for penalty in d["plea_deal_penalties"]]
        self.plea_deal_expiration = d["plea_deal_expiration"]

        self.stage = d["stage"]
        self.guilty = d["guilty"]

        self.evidence_number = d["evidence_number"]
        self.evidence = [evidence.Evidence(e["id"]).fromDict(e) for e in d["evidence"]]

        self.motion_number = d["motion_number"]
        self.motion_queue = [self.loadMotionFromDict(motion) for motion in d["motion_queue"]]
        self.motion_in_consideration = self.getMotionByID(d["motion_in_consideration"]) if d["motion_in_consideration"] else None

        self.jury_pool_ids = d["jury_pool_ids"]
        self.jury_invites = d["jury_invites"]

        self.anonymization = {int(key): d["anonymization"][key] for key in d["anonymization"]}
        self.known_users = {int(key): d["known_users"][key] for key in d["known_users"]}

        self.event_log = d["event_log"]
        self.juror_chat_log = d["juror_chat_log"]
        self.votes = d["votes"]

        self.no_tick = d["no_tick"]

        log("Case", "Load", f"Loaded saved case {self.id} with title {self.title} in {round(time.time() - t, 5)} seconds")

        return self

    def safedump(self, d: dict):
        def default(o):
            if isinstance(o, (datetime.date, datetime.datetime)):
                return o.isoformat()
            return f"<<non-serializable: {type(o).__qualname__}>>"
        return json.dumps(d, default=default, indent=2)
    
    def sanitize_event(self, event: Event) -> Event:
        san_event = event.copy()
        for key in event:
            if key not in Event.__annotations__ and key in san_event:
                del san_event[key]
        return san_event

    # create in-memory zip file archive of the case
    def Zip(self) -> io.BytesIO:
        zip = zipfile.ZipFile(io.BytesIO(), "w")

        # sanitize the event log to remove any pii or other sensitive information
        zip.writestr("raw/event_log.json", self.safedump([self.sanitize_event(event) for event in self.event_log]))

        # save the event log as a simple text file
        s = ""
        for event in self.event_log:
            desc = event["desc"].replace("\n", "\n\t")
            s += f"{event['timestamp'].isoformat()}: {event['name']}\n\t{desc}\n\n"
        zip.writestr("event_log.log", s)
        
        # TODO: create an evidence manifest and an evidence folder
        # raw/evidence_manifest.json
        # .evidence/manifest.log
        # .evidence/locker/*.* (evidence files)

        # TODO: create a juror chat log
        # raw/juror_chat_log.json
        # juror_chat_log.log

        # Summary file
        # raw/summary.json
        # summary.txt
        # README.md

        return zip
    
    def __init__(self, bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.id = random.randint(100000000000000000, 999999999999999999)
        return

class Motion:

    expiry_days = 1
    expiry_hours = expiry_days * 24

    Case: Case = None

    async def startVoting(self):
        self.Expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=self.expiry_hours)
        self.Votes["Yes"] = []
        self.Votes["No"] = []
        self.Case.motion_in_consideration = self
        self.Case.event_log.append(await self.Case.newEvent(
            "motion_up",
            f"The motion {self.MotionID} has been put up to be considered for a vote by {self.Case.nameUserByID(self.Author.id)}.",
            f"""The motion {self.MotionID} has been put up to be considered for a vote by {self.Case.nameUserByID(self.Author.id)}. 
Unless another vote is rushed, voting will end on {discord_dynamic_timestamp(self.Expiry, 'F')}.""",
            motion = self.Dict()
        ))
    
    async def CancelVoting(self, reason:str = None):
        if not self.Expiry and self.Case.motion_in_consideration != self:
            return
        self.Expiry = None
        self.Case.motion_in_consideration = None
        self.Votes["Yes"] = []
        self.Votes["No"] = []
        explan = f"Voting for motion {self.MotionID} has been cancelled."
        if reason:
            explan += f"\nReason: {reason}"
        self.Case.event_log.append(await self.Case.newEvent(
            "motion_cancel_vote",
            f"Voting for motion {self.MotionID} has been cancelled.",
            explan,
            motion = self.Dict()
        ))

    async def VoteFailed(self):
        yes = ', '.join([self.Case.nameUserByID(user) for user in self.Votes["Yes"]])
        no = ', '.join([self.Case.nameUserByID(user) for user in self.Votes["No"]])
        self.Case.event_log.append(await self.Case.newEvent(
            "motion_failed",
            f"The motion {self.MotionID} has failed its vote.",
            f"The motion {self.MotionID} has failed its jury vote ({len(self.Votes['Yes'])}/{len(self.Votes['No'])}).\n\nIn Support: {yes}\n\nIn Opposition: {no}",
            motion = self.Dict()
        ))
        return

    async def VotePassed(self):
        yes = ', '.join([self.Case.nameUserByID(user) for user in self.Votes["Yes"]])
        no = ', '.join([self.Case.nameUserByID(user) for user in self.Votes["No"]])
        self.Case.event_log.append(await self.Case.newEvent(
            "motion_passed",
            f"The motion {self.MotionID} has passed its vote.",
            f"The motion {self.MotionID} has passed its jury vote ({len(self.Votes['Yes'])}/{len(self.Votes['No'])}).\n\nIn Support: {yes}\n\nIn Opposition: {no}",
            motion = self.Dict()
        ))
        return
    
    async def Execute(self):
        return
    
    def ReadyToClose(self) -> bool:
        if len(self.Votes["Yes"]) + len(self.Votes["No"]) >= len(self.Case.jury_pool_ids):
            return True
        if datetime.datetime.now(datetime.timezone.utc) > self.Expiry:
            return True
        return False

    async def Close(self, delete: bool = True):
        # DEBUG CODE REMOVE LATER

        print(f"Closing motion {self}")
        if len(self.Votes["No"]) >= len(self.Votes["Yes"]):
            await self.VoteFailed()
        else:
            await self.VotePassed()
            await self.Execute()
        if delete:
            self.Case.motion_queue.remove(self)
            if self.Case.motion_in_consideration == self:
                self.Case.motion_in_consideration = None

    # Close without executing, no matter what    
    def forceClose(self):
        self.Case.motion_queue.remove(self)
        if self.Case.motion_in_consideration == self:
            self.Case.motion_in_consideration = None

    def LoadDict(self, DBDocument: dict):
        return self
    
    async def New(self, author) -> Motion:  # the event log entry should be updated by the subtype's New() function
        self.Created = datetime.datetime.now(datetime.timezone.utc)
        self.Author = author
        self.MotionID = f"{self.Case.id}-M{self.Case.motion_number}"  # 11042023-M001 for example
        self.Case.motion_number += 1
        self.Case.motion_queue.append(self)
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
        # DEBUG CODE REMOVE LATER

        print(f"DEL CALLED FOR {self}")
        return
    
    def __str__(self):
        return self.MotionID

    def __repr__(self):
        return self.MotionID

    def Dict(self):  # like Motion.Save() but doesn't save the dictionary, just returns it instead. Motions are saved when their 
        save = self.__dict__
        save["type"] = self.__class__.__name__
        return save

class StatementMotion(Motion):
    
    def __init__(self, Case: Case):
        super().__init__(Case)
        self.statement_content = None

    async def Execute(self):
        self.Case.event_log.append(await self.Case.newEvent(
            "jury_statement",
            f"The jury has made an official statement.",
            f"Pursuant to motion {self.MotionID}, the Jury makes the following statement:\n{self.statement_content}",
            motion = self.Dict()
        ))
    
    async def New(self, author, statement_content: str):
        await super().New(author)
        self.statement_content = statement_content
        self.Case.event_log.append(await self.Case.newEvent(
            "propose_statement",
            f"Motion {self.MotionID} has been filed to make a statement.",
            f"Motion {self.MotionID} has been filed by {self.Case.nameUserByID(self.Author.id)} to have the jury make a statement.\nStatement: {statement_content}",
            motion = self.Dict()
        ))
        return self

    def LoadDict(self, DBDocument: dict):
        super().LoadDict()
        return

class OrderMotion(Motion):
    
    def __init__(self, Case: Case):
        super().__init__(Case)
        self.target = None
        self.order_content = None
    
    async def Execute(self):
        self.Case.event_log.append(await self.Case.newEvent(
            "jury_order",
            f"The jury has given a binding order.",
            f"Pursuant to motion {self.MotionID}, the Jury compels the following entity:\n{self.target}\n\nTo comply with the following order:\n{self.order_content}.\nNot following this order can result in penalties.",
            motion = self.Dict()
        ))

    async def New(self, author, target: str, order_content: str):
        await super().New(author)
        self.target = target
        self.order_content = order_content
        self.Case.event_log.append(await self.Case.newEvent(
            "propose_order",
            f"Motion {self.MotionID} has been filed to give a binding order.",
            f"Motion {self.MotionID} has been filed by {self.Case.nameUserByID(self.Author.id)} to compel the following entity: {target}\nTo comply with the following order:\n{order_content}.",
            motion = self.Dict()
        ))
        return self

class RushMotion(Motion):
    
    def __init__(self, case):
        self.Case = case
        self.Expiry = None  # this is set by the motion manageer based on when it appears on the floors
        self.Votes = {}
        self.Votes["Yes"] = []
        self.Votes["No"] = []
        self.MotionID = "#NO-ID-ERR"
        self.rushed_motion_id = None

    async def New(self, author, rushed_motion_id: str, explanation: str):
        # ported from the old code
        self.Created = datetime.datetime.now(datetime.timezone.utc)
        self.Author = author
        self.MotionID = f"{self.Case.id}-M{self.Case.motion_number}"  # 11042023-M001 for example
        self.Case.motion_number += 1

        # if someone accidentally passes a motion instead of just its id, no worries
        if isinstance(rushed_motion_id, Motion):
            motion = rushed_motion_id
        else:
            motion = self.Case.getMotionByID(rushed_motion_id)

        self.rushed_motion_id = motion.MotionID
        self.explanation = explanation
        self.Case.event_log.append(await self.Case.newEvent(
            "propose_rush_motion",
            f"Motion {self.MotionID} has been filed to rush {self.rushed_motion().MotionID}.",
            f"Motion {self.MotionID} has been filed by {self.Case.nameUserByID(self.Author.id)} to rush motion {self.rushed_motion().MotionID} for an immediate floor vote.\nReason: {explanation}",
            motion = self.Dict(),
            rushed_motion = self.rushed_motion().Dict()
        ))
        for motion in self.Case.motion_queue:
            await motion.CancelVoting(reason=f"Motion {self.MotionID} to rush motion {self.rushed_motion().MotionID} has been filed.")
        
        self.Case.motion_queue = [self] + self.Case.motion_queue
        return self

    def rushed_motion(self):
        return self.Case.getMotionByID(self.rushed_motion_id)

    async def Execute(self):
        self.Case.event_log.append(await self.Case.newEvent(
            "rush_motion",
            f"A motion {self.rushed_motion().MotionID} has been rushed to the front of the queue.",
            f"Pursuant to motion {self.MotionID}, {self.rushed_motion().MotionID} has been rushed to the front of the queue and will now face an immediate vote.",
            motion = self.Dict(),
            rushed_motion = self.rushed_motion().Dict()
        ))
        rushed = self.rushed_motion()
        self.Case.motion_queue.remove(rushed)
        for motion in self.Case.motion_queue:
            if motion == self:
                continue
            await motion.CancelVoting(reason=f"Motion {rushed.MotionID} has been rushed to a vote.")
        self.Case.motion_queue = [rushed] + self.Case.motion_queue
        self.rushed_motion().startVoting()
        

# this motion can batch pass or deny any set of motions
# it is not placed at the end of the queue, rather it is placed 
# before the first motion referenced

class BatchVoteMotion(Motion):
    
    def __init__(self, case):
        super().__init__(case)
    
    async def New(self, author, pass_motion_ids: List[str], deny_motion_ids: List[str], reason: str):
        self.Created = datetime.datetime.now(datetime.timezone.utc)
        self.Author = author
        self.MotionID = f"{self.Case.id}-M{self.Case.motion_number}"  # 11042023-M001 for example
        self.Case.motion_number += 1

        # check if pass_motion_ids and deny_motion_ids are None and change them to []

        if pass_motion_ids is None:     pass_motion_ids = []
        if deny_motion_ids is None:     deny_motion_ids = []

        # you can pass a single motion id instead of a list with 1 item and they will be processed automatically
        if not isinstance(pass_motion_ids, list):       pass_motion_ids = [pass_motion_ids]
        if not isinstance(deny_motion_ids, list):       deny_motion_ids = [deny_motion_ids]
        
        aggregate = pass_motion_ids + deny_motion_ids
        for motion_id in aggregate:
            motion = self.Case.getMotionByID(motion_id)
            if not motion:
                print(self.Case.motion_queue)
                raise Exception(f"Motion {motion_id} does not exist.")
        
        self.pass_motion_ids = pass_motion_ids
        self.deny_motion_ids = deny_motion_ids
        self.reason = reason

        execute_str = ""
        if pass_motion_ids:
            execute_str += f"The following motions will be passed: {','.join(pass_motion_ids)}\n"
        
        if deny_motion_ids:
            execute_str += f"The following motions will be denied: {','.join(deny_motion_ids)}\n"


        self.Case.event_log.append(await self.Case.newEvent(
            "propose_summary_motion",
            f"Motion {self.MotionID} has been filed to pass or deny motions.",
            f"Motion {self.MotionID} has been filed by {self.Case.nameUserByID(self.Author.id)}.\n{execute_str}\nReason: {reason}",
            motion = self.Dict()
        ))

        # add to queue in front of first motion referenced
        for motion in self.Case.motion_queue:
            if motion.MotionID in aggregate:
                index = self.Case.motion_queue.index(motion)
                if index == 0:
                    self.Case.motion_in_consideration.CancelVoting(reason=f"Motion {self.MotionID} has been filed to pass or deny a set of motions.")
                self.Case.motion_queue.insert(self.Case.motion_queue.index(motion), self)
                break
        return self

    async def Execute(self):

        passed = []
        failed = []
        not_found = []
        
        for motion_id in self.pass_motion_ids:
            motion = self.Case.getMotionByID(motion_id)
            if not motion:
                not_found.append(motion_id)
                continue
            passed.append(motion_id)
            await motion.Execute()
            await motion.forceClose()

        for motion_id in self.deny_motion_ids:
            motion = self.Case.getMotionByID(motion_id)
            if not motion:
                not_found.append(motion_id)
                continue
            failed.append(motion_id)
            motion.forceClose()
        
        executed_str = ""
        if passed:
            executed_str += f"The following motions have been passed: {','.join(passed)}\n"
        
        if failed:
            executed_str += f"The following motions have been denied: {','.join(failed)}\n"
        
        if not_found:
            executed_str += f"The following motions were referenced, but not found: {','.join(not_found)}"

        self.Case.event_log.append(await self.Case.newEvent(
            "batch_motion",
            f"Execution on Batch Vote Motion {self.MotionID} has finished.",
            f"Pursuant to motion {self.MotionID}, the following has been executed:\n{executed_str}",
            motion = self.Dict(),
            not_found = not_found,
            passed = passed,
            failed = failed
        ))
        
class AdjustPenaltyMotion(Motion):
    """
    Adjusts the penalty if the case is delivered a guilty verdict.
    This is a WIP, as the way the penalty is tracked and managed may change down the line.
    """

    def __init__(self, case):
        super().__init__(case)
        self.reason: str = None
        self.new_penalties: dict = None

    async def New(self, author, new_penalties: List[Penalty], reason: str) -> Motion:
        await super().New(author)

        if isinstance(new_penalties, Penalty):
            new_penalties = [new_penalties]

        self.reason = reason
        self.new_penalties = new_penalties

        old_penalty_str = self.Case.describePenalties(self.Case.penalties)
    
        new_penalties_str = self.Case.describePenalties(new_penalties)

        # TODO: write a function which describes a penalty in natural language ("7 days prison sentence")
        self.Case.event_log.append(await self.Case.newEvent(
            "propose_new_penalty",
            f"Motion {self.MotionID} has been filed to adjust the Penalty if found guilty.",
            f"Motion {self.MotionID} has been filed by {self.Case.nameUserByID(self.Author.id)} to adjust the penalty of a guilty verdict From:\n{old_penalty_str}\n\nTo:\n{new_penalties_str}\nReason: {reason}",
            motion = self.Dict(),
            old_penalties = [penalty.save() for penalty in self.Case.penalties],
            new_penalties = [penalty.save() for penalty in new_penalties]
        ))
        return self
    
    async def Execute(self):

        old_penalty_str = self.Case.describePenalties(self.Case.penalties)
    
        new_penalties_str = self.Case.describePenalties(self.new_penalties)
    
        old_penalties = [penalty.save() for penalty in self.Case.penalties]
        
        self.Case.penalties = self.new_penalties

        self.Case.event_log.append(await self.Case.newEvent(
            "new_penalty",
            f"The Penalty of the Case has been adjusted.",
            f"Pursuant to motion {self.MotionID}, the guilty penalty has been adjusted From:\n{old_penalty_str}\n\nTo:\n{new_penalties_str}",
            motion = self.Dict(),
            old_penalties = old_penalties,
            new_penalties = [penalty.save() for penalty in self.new_penalties]
        ))

def getEvidenceByIDGlobal(evidenceid: str) -> evidence.Evidence:
    evidenceid = evidenceid.lower()
    for case in ACTIVECASES:
        for evidence in case.evidence:
            if evidence.id.lower() == evidenceid:
                return case, evidence
    return None, None


MOTION_TYPES = {
    "statement": StatementMotion,
    "rush": RushMotion,
    "order": OrderMotion,
    "batch": BatchVoteMotion,
    "penaltyadjust": AdjustPenaltyMotion

}
