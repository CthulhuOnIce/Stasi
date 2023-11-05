# this file is for testing Case classes, Motion classes, and implementations of such
# PORTED IMPORTS
import datetime
import random

# TESTING IMPORTS  
import base64

# DOC LINKS
# https://docs.pycord.dev/en/stable/api/models.html

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

# --- START DEBUG CLASSES AND FUNCTIONS - THIS IS FOR EMULATING AND TESTING AND SHOULD NOT BE PORTED TO THE BOT ---

nouns = open("../wordlists/nouns.txt", "r").read().split("\n")
adjectives = open("../wordlists/adjectives.txt", "r").read().split("\n")
elements = open("../wordlists/elements.txt", "r").read().split("\n")

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
                ACTIVECASES[0].AddJuror(self, pseudo)
            else:
                print(f"{self} Joining case {ACTIVECASES[0]} without pseudonym")
                ACTIVECASES[0].AddJuror(self)
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
        self.members = [User() for i in range(800)]
        return
    
    def find(self, id):
        for member in self.members:
            if member.id == id:
                return member
        return None

class discord:  # just so that we can use discord.Member and discord.User and port it later
    Member: User = None
    Guild: Guild = None
    User: User = None

# --- END DEBUG CLASSES AND FUNCTIONS - EVERYTHING BELOW MUST BE PORTED TO THE BOT ---

ACTIVECASES = []

class Case:

    motion_timeout_days = 1  # how long it takes for voting to close on a motion in the absence of all parties voting

    def CreateMotion(self):
        return Motion(self).New()

    def new_event(self, event_id: str, name, desc, **kwargs):
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

    def generate_new_id(self):
        # 11042023-01, 11042023-02, etc.
        number = str(len(ACTIVECASES)).zfill(2)
        return f"{datetime.datetime.now(datetime.UTC).strftime('%m%d%Y')}-{number}"
    
    def Announce(self, content = None, embed = None, jurors: bool = True, defense: bool = True, prosecution: bool = True, news_wire: bool = True):
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

    def RegisterUser(self, user, anonymousname: str = None):
        self.known_users[user.id] = self.GenerateKnownUserName(user)
        if anonymousname:
            self.anonymization[user.id] = anonymousname

    def FindEligibleJurors(self):
        # DEBUG CODE REMOVE LATER
        return [user for user in guild.members if user not in self.jury_invites]
    
    def AddJuror(self, user, anonymousname: str = None):
        self.jury_pool.append(user)
        if user in self.jury_invites:
            self.jury_invites.remove(user)
        self.RegisterUser(user, anonymousname)
        return

    def Tick(self):  # called by case manager or when certain events happen, like a juror leaving the case
        if len(self.jury_pool) < 5:
            if self.stage > 1:  # juror left the case
                self.stage = 1  # back in the recruitment stage
            invites_to_send = 1   # 1 per cycle
            eligible_jurors = self.FindEligibleJurors()
            for i in range(invites_to_send):
                invitee = random.choice(eligible_jurors)
                eligible_jurors.remove(invitee)
                try:
                    self.jury_invites.append(invitee)
                    invitee.send(f"You have been invited to be a juror for `{self.id}`.\nTo accept, use `/jury join`.")
                except:
                    pass  # already removed from eligible jurors
            return
        # switching from stage 1 to 2 should be done by the function which assigns a juror to the case
        if self.stage == 2:  # work the motion queue
            
            if self.motion_in_consideration != self.motion_queue[0]:  # putting up a new motion to vote
                self.motion_queue[0].StartVoting()

            elif len(self.motion_in_consideration["votes"]) >= len(self.jury_pool) or datetime.datetime.now(datetime.UTC) < self.motion_in_consideration["expiry"]:  # everybody's voted, doesn't need to expire, or has expired
                if len(self.motion_in_consideration["votes"]["yes"]) <= len(self.motion_in_consideration["votes"]["no"]):  # needs majority yes to pass, this triggers if yes is equal to or less than no
                    explainer = "The motion has failed its vote."
                    if datetime.datetime.now(datetime.UTC) < self.motion_in_consideration["expiry"]:
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

            




    def New(self, title: str, description: str, plaintiff: discord.Member, defense: discord.Member, penalty: dict, guild):
        self.guild = guild

        self.title = title
        self.description = description
        self.id = self.generate_new_id()
        self.created = datetime.datetime.now(datetime.UTC)
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

        self.RegisterUser(plaintiff)
        self.RegisterUser(defense)

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

    def Save(self):
        case_dict = {
                # metadata
                "_id": self.id,
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
                "motion_queue": [motion.Dict() for motion in self.motion_queue],
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
        return case_dict
    
    def __init__(self):
        self.id = random.randint(100000000000000000, 999999999999999999)
        return

class Motion:

    expiry_days = 1
    expiry_hours = expiry_days * 24

    Case: Case = None

    def StartVoting(self):
        self.Expiry = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=self.expiry_hours)
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

    def VoteFailed(self):
        self.Case.event_log.append(self.Case.new_event(
            "motion_failed",
            f"The motion {self.MotionID} has failed its vote.",
            f"The motion {self.MotionID} has failed its jury vote. {len(self.Votes['Yes'])}/{len(self.Votes['No'])}",
            motion = self.Dict()
        ))
        return

    def VotePassed(self):
        self.Case.event_log.append(self.Case.new_event(
            "motion_failed",
            f"The motion {self.MotionID} has passed its vote.",
            f"The motion {self.MotionID} has passed its jury vote. {len(self.Votes['Yes'])}/{len(self.Votes['No'])}",
            motion = self.Dict()
        ))
        return
    
    def Execute(self):
        return

    def Close(self, delete: bool = True):
        if len(self.No) >= len(self.Yes):
            self.VoteFailed()
        else:
            self.VotePassed()
            self.Execute()
        if delete:
            del(self)


    def LoadDict(self, DBDocument: dict):
        return self
    
    def New(self, author):
        self.Created = datetime.datetime.now(datetime.UTC)
        self.Author = author
        self.MotionID = f"{self.Case.id}-M{self.Case.motion_number}"  # 11042023-M001 for example
        self.Case.motion_number += 1
        return self

    def __init__(self, Case: Case):
        self.Case = Case
        self.Expiry = None  # this is set by the motion manageer based on when it appears on the floors
        self.Votes = {}
        self.Votes["Yes"] = []
        self.Votes["No"] = []
        self.MotionID = "#NO-ID-ERR"
        Case.motion_queue.append(self)
        return 

    def __del__(self):
        self.Case.motion_queue.remove(self)
        if self.Case.motion_in_consideration != self:
            self.Case.motion_in_consideration = None
    
    def __str__(self):
        return self.MotionID

    def __repr__(self):
        return self.MotionID

    def Dict(self):  # like Motion.Save() but doesn't save the dictionary, just returns it instead. Motions are saved when their 
        return self.__dict__

class StatementMotion(Motion):
    def Execute(self):
        self.Case.event_log.append(self.Case.new_event(
            "jury_statement",
            f"The jury has made an official statement.",
            f"Pursuant to motion {self.MotionID}, the Jury makes the following statement:\n{self.statement_content}",
            motion = self.Dict()
        ))
    
    def New(self, author, statement_content: str = None):
        super().New(author)
        self.statement_content = statement_content
        return self

    def LoadDict(self, DBDocument: dict):
        super().LoadDict()
        return
    
# CREATE AN ENVIRONMENT SIMILAR TO IDLE

guild = Guild()
case = Case()
plaintiff = random.choice(guild.members)
defense = random.choice(guild.members)

case.New(f"{plaintiff} v. {defense}", "This is a test case.", plaintiff, defense, {"type": "prison", "length": 10}, guild)

for i in range(6):
    case.Tick()

jury = case.jury_pool
i = 0
for juror in jury:
    i += 1
    motion = StatementMotion(case).New(juror, f"This is a test statement {i}")

case.motion_queue[0].Execute()

# by this point the case is filed and the jury is already selected

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

shell()