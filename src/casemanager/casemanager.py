from __future__ import annotations

import datetime
import io
import random
import time
import zipfile
from typing import *

import discord
import simplejson as json
from discord import Embed

from .. import config
from .. import database as db
from .. import utils, warden
from ..stasilogging import *
from . import evidence
from .motion import *
from .penalties import *

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
- [ ] /case move prison - Prison the defendant for a set time, or until the case is resolved

- [ ] /case move expedite - File a motion to expedite another motion
- [ ] /case move batch - File a motion to batch dismiss or pass other motions

- [ ] /case evidence strike - File a motion to strike evidence from the case, or if you submitted it, strike it from the case immediately.
- [ ] /case evidence interview - Interview a user through Stasi and admit it as evidence
- [ ] /case evidence statement - Ask a user for a single statement through Stasi and admit that as evidence.
- [ ] /case evidence message - Submit a message link to have it archived as evidence
- [x] /case evidence upload - Upload a file as evidence

- [ ] /case motion withdraw - To withdraw a motion

Bugs:
- [ ]

Optimizations:
- [ ] Communication with discord is slow af when working with files on evidence upload and view
- [ ] Break this file up into multiple files, or even a submodule
- [ ] Make sure security checks are good on debug and all new commands

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