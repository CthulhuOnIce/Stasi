from __future__ import annotations
from typing import *
import pyperclip

# this file is for testing Case classes, Motion classes, and implementations of such
# PORTED IMPORTS
import datetime
import random

# TESTING IMPORTS  
import base64
import json
from discord import Embed

# DOC LINKS
# https://docs.pycord.dev/en/stable/api/models.html

# BUGS
# - motion_in_consideration is not being set as the motion queue is worked

# # UTILS
class utils:
    def int_to_base64(self, n: int):
        # Convert integer to bytes
        int_bytes = n.to_bytes((n.bit_length() + 7) // 8, 'big') or b'\0'
        
        # Encode bytes to base64
        base64_bytes = base64.b64encode(int_bytes)
        
        # Convert bytes to string for the output
        base64_string = base64_bytes.decode('utf-8')
        
        return base64_string

def shell():
    while True:
        try:
            user_input = input(">>> ")
            if user_input.strip() == "":
                continue
            else:
                exec(user_input)
        except Exception as e:
            print(f"Error: {e}")

# --- START DEBUG CLASSES AND FUNCTIONS - THIS IS FOR EMULATING AND TESTING AND SHOULD NOT BE PORTED TO THE BOT ---

nouns = open("../wordlists/nouns.txt", "r").read().split("\n")
adjectives = open("../wordlists/adjectives.txt", "r").read().split("\n")
elements = open("../wordlists/elements.txt", "r").read().split("\n")

def safedump(d: dict):
    default = lambda o: f"<<non-serializable: {type(o).__qualname__}>>"
    return json.dumps(d, default=default, indent=2)

class User:
    def __init__(self):
        self.id = random.randint(100000000000000000, 999999999999999999)
        self.old_user = random.choice([True, False])
        # AdjectiveAdjectiveNoun 
        self.name = f"{random.choice(adjectives).title()}{random.choice(adjectives).title()}{random.choice(nouns).title()}"
        if self.old_user:
            self.discriminator = random.randint(1000, 9999)
        else:
            self.discriminator = 0
    
    def send(self, content):
        print(f"Sent message to {self}: {content}")
        if "You have been invited to be a juror for" in content:
            # if 10% chance, accept the invite
            if random.choice([True, False]):
                pseudo = f"Juror {random.choice(nouns).title()}"
                print(f"{self} Joining case {ACTIVECASES[0]} as " + pseudo)
                ACTIVECASES[0].addJuror(self, pseudo)
            else:
                print(f"{self} Joining case {ACTIVECASES[0]} without pseudonym")
                ACTIVECASES[0].addJuror(self)
        return
     
    # what is printed when this object is printed
    def __str__(self):
        return f"{self.name}#{self.discriminator}"
    
    # __str__ isn't working, why?
    def __repr__(self):
        return f"{self.name}#{self.discriminator}"

class Guild:
    name = "Test Guild"
    def __init__(self):
        self.members: List[discord.Member] = [User() for i in range(800)]
        return
    
    def get_user(self, id):
        for member in self.members:
            if member.id == id:
                return member
        return None

class discord:  # just so that we can use discord.Member and discord.User and port it later
    Member: User = None
    Guild: Guild = None
    User: User = None
    Embed = Embed

# --- END DEBUG CLASSES AND FUNCTIONS - EVERYTHING BELOW MUST BE PORTED TO THE BOT ---

ACTIVECASES: List[Case] = []

# makes intellisense work for event dictionaries
class Event(TypedDict):
    event_id: str
    name: str
    desc: str
    timestamp: datetime.datetime
    timestamp_utc: float

def eventToEmbed(event: Event) -> discord.Embed:
    embed = discord.Embed(title=event["name"], description=event["desc"], timestamp=event["timestamp"])
    embed.set_footer(text=f"Event ID: {event['event_id']}")
    return embed

class Case:

    motion_timeout_days = 1  # how long it takes for voting to close on a motion in the absence of all parties voting

    def createMotion(self) -> "Motion":
        return Motion(self).New()

    def newEvent(self, event_id: str, name, desc, **kwargs) -> Event:
        event = {
                    "event_id": event_id,
                    "name": name,
                    "desc": desc,
                    "timestamp": datetime.datetime.now(datetime.UTC),
                    "timestamp_utc": datetime.datetime.now(datetime.UTC).timestamp(),
                }
        for kw in kwargs:
            event[kw] = kwargs[kw]
        return event
    
    class Statement(TypedDict):
        author_id: int
        content: str

    def personalStatement(self, author, text):

        statement: self.Statement = {
            "author_id": author.id,
            "content": text,
            "timestamp": datetime.datetime.now(datetime.UTC)
        }

        self.personal_statements.append(statement)
        self.event_log.append(self.newEvent(
            "personal_statement",
            f"{self.nameUserByID(statement['author_id'])} has submitted a personal statement",
            f"{self.nameUserByID(statement['author_id'])} has submitted a personal statement:\n{statement['content']}",
            statement = statement
        ))

    def generateNewID(self):
        # 11042023-01, 11042023-02, etc.
        number = str(len(ACTIVECASES)).zfill(2)
        return f"{datetime.datetime.now(datetime.UTC).strftime('%m%d%Y')}-{number}"
    
    def Announce(self, content: str = None, embed: discord.Embed = None, jurors: bool = True, defense: bool = True, prosecution: bool = True, news_wire: bool = True):
        # content = plain text content
        # embed = an embed
        # jurors = whether or not to send this announcement to the jury
        # defense = whether or not to send this announcement to the defense
        # prosucution = whether or not to send this announcement to the prosecution
        # news_wire = whether or not to send this announcement to the public news wire channel
        return
    
    def normalUsername(self, user):
        if not user.discriminator:
            return f"@{user.name}"
        else:
            return f"{user}"
    
    def nameUserByID(self, userid: int):
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

    def registerUser(self, user, anonymousname: str = None):
        self.known_users[user.id] = self.normalUsername(user)
        if anonymousname:
            self.anonymization[user.id] = anonymousname

    def findEligibleJurors(self) -> List[discord.Member]:
        # DEBUG CODE REMOVE LATER
        return [user for user in guild.members if user not in self.jury_invites]
    
    def addJuror(self, user, pseudonym: str = None):
        self.jury_pool.append(user)
        if user in self.jury_invites:
            self.jury_invites.remove(user)
        self.registerUser(user, pseudonym)
        return

    def Tick(self):  # called by case manager or when certain events happen, like a juror leaving the case

        if self.no_tick:
            return

        if len(self.jury_pool) < 5:
            # juror left the case, but it was already in the body stage
            # when this happens, the case basically has to revert to the recruitment stage
            if self.stage > 1:  
                self.updateStatus("Jury Re-Selection to Fill Vacancy")
                for motion in self.motion_queue:
                    motion.CancelVoting(reason=f"Jury cannot act on motions until 5 jurors are present.")
                self.stage = 1  # back in the recruitment stage
            invites_to_send = 1   # 1 per cycle
            eligible_jurors = self.findEligibleJurors()
            for i in range(invites_to_send):
                invitee = random.choice(eligible_jurors)
                eligible_jurors.remove(invitee)
                try:
                    self.jury_invites.append(invitee)
                    invitee.send(f"You have been invited to be a juror for {self.title} (`{self.id}`).\nTo accept, use `/jury join`.")
                except:
                    pass  # already removed from eligible jurors
            return
        
        elif self.stage == 1:  # we have jurors selected, so move the case to the next stage
            self.updateStatus("Argumentation and Case Body")
            self.stage = 2
        
        # switching from stage 1 to 2 should be done by the function which assigns a juror to the case
        if self.stage == 2 and len(self.motion_queue):  # work the motion queue
            
            if self.motion_in_consideration != self.motion_queue[0]:  # putting up a new motion to vote
                self.motion_queue[0].startVoting()

            elif self.motion_in_consideration.ReadyToClose():  # everybody's voted, doesn't need to expire, or has expired
                self.motion_in_consideration.Close()
            
            return

        if self.stage == 3:  # archive self, end the case
            # unprison prisoned users
            return
        
    def getMotionByID(self, motionid: str) -> "Motion":
        for motion in self.motion_queue:
            # TODO: remove prints later
            if motion.MotionID.lower() == motionid.lower():
                return motion
        return None

    def getUser(self, userid: int) -> discord.Member:
        if isinstance(userid, str):
            userid = int(userid)
        return self.guild.get_user(userid)

    def fetchUser(self, userid: int) -> discord.Member:
        if isinstance(userid, str):
            userid = int(userid)
            
        if got := self.getUser(userid):
            return got
        elif got := self.guild.get_member(userid):
            return got
        elif got := self.guild.fetch_member(userid):
            return got


    def New(self, guild: discord.Guild, bot, title: str, description: str, plaintiff: discord.Member, defense: discord.Member, penalty: dict) -> Case:
        self.guild = guild
        self.bot = bot

        self.title = title
        self.description = description
        # "Jury Selection", "Guilty", "Not Guilty", 
        self.status = "Jury Selection"
        self.id = self.generateNewID()
        self.created = datetime.datetime.now(datetime.UTC)
        self.plaintiff = plaintiff.id
        self.defense = defense.id
        self.penalty = penalty
        self.stage = 1
        self.motion_queue: List[Motion] = []
        # used to keep track of timeouts and whatnot
        self.locks = []
        self.personal_statements = []
        self.jury_pool = []
        self.jury_invites = []
        self.anonymization = {}
        self.known_users = {}
        # MIGHT REMOVE in favor of delivering verdict ny a motion
        self.votes = {}
        self.event_log = [self.newEvent(
            "case_filed",
            f"Case {self.id} has been filed.",
            f"Case {self.id} has been filed by {self.nameUserByID(self.plaintiff.id)} against {self.nameUserByID(self.defense.id)}.\n{self.description}"
        )]
        self.juror_chat_log = []
        self.motion_in_consideration: Motion = None
        self.motion_number = 101  # motion IDs start as {caseid}-101, {caseid}-102, etc. 

        # if this is set to true, Tick() won't do anything, good for completely freezing the case 
        self.no_tick: bool = False

        self.Save()

        self.registerUser(plaintiff)
        self.registerUser(defense)

        ACTIVECASES.append(self)
        return self

    def LoadFromID(self, case_id, guild):
        self.guild = guild

        ACTIVECASES.append(self)

        return 
    
    def __del__(self):
        ACTIVECASES.remove(self)

    def __str__(self):
        return self.title
    
    def __repr__(self):
        return self.title
    
    def updateStatus(self, new_status: str):
        old_status = self.status
        self.status = new_status
        self.event_log.append(self.newEvent(
            "case_status_update",
            f"The status of the case has been updated.",
            f"Case {self.id} has been updated by {self.nameUserByID(self.plaintiff.id)}.\nStatus: {old_status} -> {new_status}"
        ))
        return

    def Save(self):
        case_dict = {
                # metadata
                "_id": self.id,
                "title": self.title,
                "description": self.description,
                "status": self.status,
                "filed_date": self.created,
                "filed_date_timestamp": self.created.timestamp(),

                # plaintiff and defense
                "plaintiff_id": self.plaintiff.id,
                "defense_id": self.defense.id,

                "personal_statements": self.personal_statements,

                "locks": self.locks,
                
                "penalty": self.penalty,
                
                # processing stuff
                "stage": self.stage,  # 0 - done (archived), 1 - jury selection, 2 - argumentation / body, 3 - ready to close, awaiting archive 
                "guilty": None,
                
                "motion_number": self.motion_number,
                "motion_queue": [motion.Dict() for motion in self.motion_queue],

                # jury stuff
                "jury_pool": [user.id for user in self.jury_pool],
                "jury_invites": [user.id for user in self.jury_invites],  # people who have been invited to the jury but are yet to accept
                
                "anonymization": self.anonymization,  # id: name - anybody in this list will be anonymized and referred to by their dict value
                "known_users": self.known_users,

                "votes": self.votes,  # guilty vs not guilty votes
                "event_log": self.event_log,
                "juror_chat_log": self.juror_chat_log,
                
                "no_tick": self.no_tick
            }
        return case_dict
    
    def __init__(self):
        self.id = random.randint(100000000000000000, 999999999999999999)
        return

class Motion:

    expiry_days = 1
    expiry_hours = expiry_days * 24

    Case: Case = None

    def startVoting(self):
        self.Expiry = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=self.expiry_hours)
        self.Votes["Yes"] = []
        self.Votes["No"] = []
        self.Case.motion_in_consideration = self
        self.Case.event_log.append(self.Case.newEvent(
            "motion_up",
            f"The motion {self.MotionID} has been put up to be considered for a vote by {self.Case.nameUserByID(self.Author.id)}.",
            f"The motion {self.MotionID} has been put up to be considered for a vote by {self.Case.nameUserByID(self.Author.id)}. \
            Unless another vote is rushed, voting will end on <t:{self.Expiry.timestamp()}:F>.",
            motion = self.Dict()
        ))
    
    def CancelVoting(self, reason:str = None):
        if not self.Expiry and self.Case.motion_in_consideration != self:
            return
        self.Expiry = None
        self.Case.motion_in_consideration = None
        self.Votes["Yes"] = []
        self.Votes["No"] = []
        explan = f"Voting for motion {self.MotionID} has been cancelled."
        if reason:
            explan += f"\nReason: {reason}"
        self.Case.event_log.append(self.Case.newEvent(
            "motion_cancel_vote",
            f"Voting for motion {self.MotionID} has been cancelled.",
            explan,
            motion = self.Dict()
        ))

    def VoteFailed(self):
        self.Case.event_log.append(self.Case.newEvent(
            "motion_failed",
            f"The motion {self.MotionID} has failed its vote.",
            f"The motion {self.MotionID} has failed its jury vote. {len(self.Votes['Yes'])}/{len(self.Votes['No'])}",
            motion = self.Dict()
        ))
        return

    def VotePassed(self):
        self.Case.event_log.append(self.Case.newEvent(
            "motion_passed",
            f"The motion {self.MotionID} has passed its vote.",
            f"The motion {self.MotionID} has passed its jury vote. {len(self.Votes['Yes'])}/{len(self.Votes['No'])}",
            motion = self.Dict()
        ))
        return
    
    def Execute(self):
        return
    
    def ReadyToClose(self) -> bool:
        if len(self.Votes["Yes"]) + len(self.Votes["No"]) == len(self.Case.jury_pool):
            return True
        if datetime.datetime.now(datetime.UTC) > self.Expiry:
            return True
        return False

    def Close(self, delete: bool = True):
        # DEBUG CODE REMOVE LATER

        print(f"Closing motion {self}")
        if len(self.Votes["No"]) >= len(self.Votes["Yes"]):
            print("VOTE FAILED")
            self.VoteFailed()
        else:
            print("VOTE PASSED")
            self.VotePassed()
            self.Execute()
        if delete:
            self.Case.motion_queue.remove(self)
            if self.Case.motion_in_consideration == self:
                self.Case.motion_in_consideration = None

    # Close without executing, no matter what    
    def ForceClose(self):
        self.Case.motion_queue.remove(self)
        if self.Case.motion_in_consideration == self:
            self.Case.motion_in_consideration = None


    def LoadDict(self, DBDocument: dict):
        return self
    
    def New(self, author) -> Motion:  # the event log entry should be updated by the subtype's New() function
        self.Created = datetime.datetime.now(datetime.UTC)
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
        return self.__dict__

class StatementMotion(Motion):
    
    def __init__(self, Case: Case):
        super().__init__(Case)
        self.statement_content = None

    def Execute(self):
        self.Case.event_log.append(self.Case.newEvent(
            "jury_statement",
            f"The jury has made an official statement.",
            f"Pursuant to motion {self.MotionID}, the Jury makes the following statement:\n{self.statement_content}",
            motion = self.Dict()
        ))
    
    def New(self, author, statement_content: str):
        super().New(author)
        self.statement_content = statement_content
        self.Case.event_log.append(self.Case.newEvent(
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
    
    def Execute(self):
        self.Case.event_log.append(self.Case.newEvent(
            "jury_order",
            f"The jury has given a binding order.",
            f"Pursuant to motion {self.MotionID}, the Jury compels the following entity: {self.target}\nTo comply with the following order:\n{self.order_content}.\nNot following this order can result in penalties.",
            motion = self.Dict()
        ))

    def New(self, author, target: str, order_content: str):
        super().New(author)
        self.target = target
        self.order_content = order_content
        self.Case.event_log.append(self.Case.newEvent(
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
        # TODO: cancel all other votes
        self.rushed_motion_id = None

    def New(self, author, rushed_motion_id: str, explanation: str):
        # ported from the old code
        self.Created = datetime.datetime.now(datetime.UTC)
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
        self.Case.event_log.append(self.Case.newEvent(
            "propose_rush_motion",
            f"Motion {self.MotionID} has been filed to rush {self.rushed_motion().MotionID}.",
            f"Motion {self.MotionID} has been filed by {self.Case.nameUserByID(self.Author.id)} to rush motion {self.rushed_motion().MotionID} for an immediate floor vote.\nReason: {explanation}",
            motion = self.Dict(),
            rushed_motion = self.rushed_motion().Dict()
        ))
        for motion in self.Case.motion_queue:
            motion.CancelVoting(reason=f"Motion {self.MotionID} to rush motion {self.rushed_motion().MotionID} has been filed.")
        
        self.Case.motion_queue = [self] + self.Case.motion_queue

    def rushed_motion(self):
        return self.Case.getMotionByID(self.rushed_motion_id)

    def Execute(self):
        self.Case.event_log.append(self.Case.newEvent(
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
            motion.CancelVoting(reason=f"Motion {rushed.MotionID} has been rushed to a vote.")
        self.Case.motion_queue = [rushed] + self.Case.motion_queue
        self.rushed_motion().startVoting()
        

# this motion can batch pass or deny any set of motions
# it is not placed at the end of the queue, rather it is placed 
# before the first motion referenced

class BatchVoteMotion(Motion):
    
    def __init__(self, case):
        super().__init__(case)
    
    def New(self, author, pass_motion_ids: List[str], deny_motion_ids: List[str], reason: str):
        super().New(author)

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
                raise Exception(f"Motion {motion_id} does not exist.")
        
        self.pass_motion_ids = pass_motion_ids
        self.deny_motion_ids = deny_motion_ids
        self.reason = reason

        # add to queue in front of first motion referenced
        for motion in self.Case.motion_queue:
            if motion.MotionID in aggregate:
                index = self.Case.motion_queue.index(motion)
                if index == 0:
                    self.Case.motion_in_consideration.CancelVoting(reason=f"Motion {self.MotionID} has been filed to pass or deny a set of motions.")
                self.Case.motion_queue.insert(self.Case.motion_queue.index(motion), self)
                break

        self.Case.event_log.append(self.Case.newEvent(
            "propose_summary_motion",
            f"Motion {self.MotionID} has been filed to pass or deny motions.",
            f"Motion {self.MotionID} has been filed by {self.Case.nameUserByID(self.Author.id)} to pass the following motions: {','.join(pass_motion_ids)}\nAnd to deny the following motions: {','.join(deny_motion_ids)}\nReason: {reason}",
            motion = self.Dict()
        ))
        return self

    def Execute(self):

        passed = []
        failed = []
        not_found = []
        
        for motion_id in self.pass_motion_ids:
            motion = self.Case.getMotionByID(motion_id)
            if not motion:
                not_found.append(motion_id)
                continue
            passed.append(motion_id)
            motion.Execute()
            motion.ForceClose()

        for motion_id in self.deny_motion_ids:
            motion = self.Case.getMotionByID(motion_id)
            if not motion:
                not_found.append(motion_id)
                continue
            failed.append(motion_id)
            motion.ForceClose()
        
        self.Case.event_log.append(self.Case.newEvent(
            "batch_motion",
            f"Execution on Batch Vote Motion {self.MotionID} has finished.",
            f"Pursuant to motion {self.MotionID}, the following motions have been executed:\n{','.join(passed)}\nThe following motions have been denied:\n{','.join(failed)}\nThe following motions were referenced, but not found:\n{','.join(not_found)}",
            motion = self.Dict(),
            not_found = not_found,
            passed = passed,
            failed = failed
        ))
        
class AdjustPenalty(Motion):
    """
    Adjusts the penalty if the case is delivered a guilty verdict.
    This is a WIP, as the way the penalty is tracked and managed may change down the line.
    """

    def __init__(self, case):
        super().init(case)
        self.reason: str = None
        self.new_penalty: dict = None

    def New(self, author, new_penalty: dict, reason: str) -> Motion:
        super().New(author)

        old_penalty = self.Case.penalty
        self.reason = reason
        self.new_penalty = new_penalty

        # TODO: write a function which describes a penalty in natural language ("7 days prison sentence")
        # TODO: include new and old penalty in event body.
        self.Case.event_log.append(self.Case.newEvent(
            "propose_new_penalty",
            f"Motion {self.MotionID} has been filed to adjust the Penalty if found guilty.",
            f"Motion {self.MotionID} has been filed by {self.Case.nameUserByID(self.Author.id)} to adjust the penalty of a guilty verdict From:\n{old_penalty}\nTo:\n{new_penalty}\nReason: {reason}",
            motion = self.Dict(),
            old_penalty = old_penalty,
            new_penalty = new_penalty
        ))
    
    def Execute(self):
        old_penalty = self.Case.penalty
        self.Case.penalty = self.new_penalty
        self.Case.event_log.append(self.Case.newEvent(
            "propose_new_penalty",
            f"Pursuant to Motion {self.MotionID}, the guilty penalty has been adjusted",
            f"Pursuant to motion {self.MotionID}, the guilty penalty has been adjusted From:\n{old_penalty}\nTo:\n{self.new_penalty}",
            motion = self.Dict(),
            old_penalty = old_penalty,
            new_penalty = self.new_penalty
        ))
    


MOTION_TYPES = {
    "statement": StatementMotion,
    "rush": RushMotion,
    "order": OrderMotion,
    "batch": BatchVoteMotion,
    "penaltyadjust": AdjustPenalty

}

# CREATE AN ENVIRONMENT SIMILAR TO IDLE

guild = Guild()
case = Case()
plaintiff = random.choice(guild.members)
defense = random.choice(guild.members)

# case.New(f"{plaintiff} v. {defense}", "This is a test case.", plaintiff, defense, {"type": "prison", "length": 10}, guild)
# updated for new style
case.New(guild, None, f"{plaintiff} v. {defense}", "This is a test case.", plaintiff, defense, {"type": "prison", "length": 10})

# TODO: plea deal logic here

# appoint jury
for i in range(6):
    case.Tick()

def random_pass(jury, motion):
    # populate the motion with a passing amount of votes
    return

def random_fail(jury, motion):
    # populate the motion with a failing amount of votes
    return

jury = case.jury_pool
mq = case.motion_queue

prosecutor_statement = case.personalStatement(plaintiff, "This is a test personal statement from the plaintiff")
defense_statement = case.personalStatement(defense, "This is a test personal statement from the defense")

jury_statement_one = StatementMotion(case).New(jury[0], f"This is the first test statement. It should be voted on and then dismissed from a batch motion.")  # BATCH FAIL @ batch_motion
jury_statement_two = StatementMotion(case).New(jury[1], f"This is the first test statement. It should be voted on and then passed from a batch motion.") # BATCH PASS @  batch_motion

case.Tick()

# jury_statement_one should be the active motion now.

# now jury[1] tries to dismiss jury_statement_one and pass jury_statement_two
batch_motion = BatchVoteMotion(case).New(jury[1], jury_statement_two.MotionID, jury_statement_one.MotionID, "This is a test of batch motions.") # PASS

# At this point, BatchVoteMotion().New() should have removed jury_statement_one from the vote and at the front, but voting shouldn't begin yet


jury_order_one = OrderMotion(case).New(jury[2], f"{defense} and {plaintiff}", "This is a test of the order motion.")  # PASS then FAIL after rushed statement motion
case.Tick()

# now voting for the batch motion should begin

# everybody votes for it
random_pass(jury, batch_motion)
case.Tick()

# now it should have passed and taken effect

case.Tick()

# now jury_order_one should be voted on
random_pass(jury, jury_order_one)

# juror #4 files statement motion and rushes it
jury_statement_three_rushed = StatementMotion(case).New(jury[3], f"This is the third test statement motion, it should be rushed and then passed before {jury_order_one} is voted on for the second time, this time failing.")
rush_motion = RushMotion(case).New(jury[3], jury_statement_three_rushed, "Rush motion test.")

# just for fun, defense makes a statement
case.personalStatement(defense, "This is the defense's second personal statement")

# now the votes for jo1 should be cancelled and js3r should be first in queue but not voted on.

# this should start voting on rush_motion and get it the votes to pass
case.Tick()
random_pass(jury, rush_motion)

# officially pass and execute the motion
# TODO: decide whether Tick() should both execute AND put up the next motion for a vote, or allow this 15 minutes to act as a recess
case.Tick()

# if Tick() only executes the voted-on motion, this should place jo1 up for vote again
# if Tick() executes AND starts the next vote, this should do nothing
case.Tick()



# instead of terminating, open an interactive environment
shell()