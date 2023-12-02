import discord
from . import database as db
from typing import *
import datetime
import random
from . import config
from .stasilogging import *
from . import utils

"""
This module manages the "Prison" system within the server.
Whether or not a user is in prison is determined by the presence and status of Warrants.
Warrants are issued by moderators or other cogs and are stored in the database.
Warrants are stored under a "Prisoner" object which includes information like their role list and time committed.
This is so that warrants can be individually managed and issued.

Warrants with a sentence are served one after the other, in the order they are issued.
Warrants with no sentence are served indefinitely, until they are voided, frozen, or stayed.
Timed warrants and indefinite warrants can be served at the same time, but no two timed warrants can be served at the same time.

Voided warrants are removed entirely.
Stayed warrants are not served, but are not removed until they expire, time spent stayed is counted towards the sentence.
Frozen warrants are not served, but are saved until they are unfrozen. Time spent frozen is not counted towards the sentence.

Generally, when filing a new warrant. newWarrant() should be used, which will automatically create a new prisoner if one does not exist.

When voiding a warrant from another cog, use the in-built warrant voiding functions as they are designed to fail gracefully if the warrant does not exist for having been voided already.

Completion Guide
- [ ] Handle warrants correctly if user has left the server. (db.set_roles())
- [ ] Function which voids all warrants under a certain Prisoner's name.
- [ ] Function which voids all warrants under a certain category for a certain Prisoner.
- [ ] Jumping back and forth in the warrant activation queue based on freeze status etc.
"""

PRISONERS: List["Prisoner"] = []

class Warrant:
    def __init__(self):
        self._id = None
        self.category = None
        self.description = None
        self.author = None
        self.author_name = None
        self.created = None
        self.started = None
        self.len_seconds = 0
        self.expires = None
        self.frozen = None
        self.no_enforce = None

    def embed(self) -> discord.Embed:
        embed = discord.Embed(title="Warrant Info", description=f"Warrant `{self._id}`", color=discord.Color.red())
        if self.author:
            embed.add_field(name="Author", value=f"{self.author_name}", inline=False)
        if self.prisoner():
            embed.add_field(name="Target", value=f"{self.prisoner().prisoner_name}", inline=False)
        embed.add_field(name="Description", value=self.description, inline=False)
        if self.started:
            embed.add_field(name="Started", value=discord_dynamic_timestamp(self.started, "F"), inline=False)
        if self.expires:
            embed.add_field(name="Expires", value=discord_dynamic_timestamp(self.expires, "FR"), inline=False)
        if self.len_seconds > 0:
            embed.add_field(name="Sentence Length", value=utils.seconds_to_time_long(self.len_seconds), inline=False)
        if self.frozen:
            embed.add_field(name="Frozen", value="Yes", inline=False)
        if self.no_enforce:
            embed.add_field(name="No Enforce", value="Yes", inline=False)
        return embed

    def prisoner(self):
        for prisoner in PRISONERS:
            for warrant in prisoner.warrants:
                if warrant._id == self._id:
                    return prisoner

    def status(self) -> str:
        if self.expires:
            time_left_seconds = (self.expires - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
            return f"Active ({utils.seconds_to_time_long(time_left_seconds)} remaining)"
        elif self.len_seconds == -1:
            return "Active (indefinite)"
        elif self.len_seconds > 0:
            return f"Pending Sentence ({utils.seconds_to_time_long(self.len_seconds)})"
        elif self.frozen:
            return f"Frozen ({utils.seconds_to_time_long(self.len_seconds)} remaining)"

    def activate(self):
        self.started = datetime.datetime.now(datetime.timezone.utc)
        self.expires = self.started + datetime.timedelta(seconds=self.len_seconds)

    def deactivate(self):
        if self.expires:
            diff = self.expires - datetime.datetime.now(datetime.timezone.utc)
            self.len_seconds = diff.total_seconds()
            self.expires = None
        
    def freeze(self):
        self.deactivate()
        self.frozen = True

    def generateNewID(self):
        return f"{random.randint(1000,9999)}-{random.choice(utils.elements).title()}-{random.choice(utils.elements).title()}-{random.choice(utils.elements).title()}"

    def New(self, category: str, description: str, author: int, author_name: str, len_seconds: int) -> "Warrant":
        self._id = self.generateNewID()
        self.category = category
        self.description = description
        self.author = author
        self.author_name = author_name
        self.created = datetime.datetime.now(datetime.timezone.utc)
        self.len_seconds = len_seconds
        log("justice", "warrant", f"New warrant: ({self._id})")
        return self
    
    def loadFromDict(self, data):
        self._id = data["_id"]
        self.category = data["category"]
        self.description = data["description"]
        self.author = data["author"]
        self.author_name = data["author_name"]

        self.created = data["created"]
        if self.created:
            self.created = self.created.replace(tzinfo=datetime.timezone.utc)

        self.started = data["started"]
        if self.started:
            self.started = self.started.replace(tzinfo=datetime.timezone.utc)

        self.len_seconds = data["len_seconds"]
        
        self.expires = data["expires"]
        if self.expires:
            self.expires = self.expires.replace(tzinfo=datetime.timezone.utc)
       
        self.frozen = data["frozen"]
        self.no_enforce = data["no_enforce"]
        return self

class Prisoner:
    
    def __init__(self, guild):
        self.guild: discord.Guild = guild
        self._id = None
        self.prisoner_name = None
        self.roles = []
        self.committed = None
        self.warrants: List[Warrant] = []

    def New(self, user: discord.Member, user_name: str) -> "Prisoner":
        self._id = user.id
        self.user_name = user_name
        log("justice", "prisoner", f"New prisoner: {utils.normalUsername(user)} ({user.id})")
        return self
    
    def embed(self) -> discord.Embed:
        embed = discord.Embed(title="Prisoner Info", description=f"Prisoner `{self._id}`", color=discord.Color.red())
        embed.add_field(name="Name", value=f"{self.prisoner_name}", inline=False)
        embed.add_field(name="Committed", value=discord_dynamic_timestamp(self.committed, "FR"), inline=False)
        if self.warrants:
            embed.add_field(name=f"Warrants ({len(self.warrants)})", value="\n\n".join([f"`{warrant._id}` - {warrant.status()}" for warrant in self.warrants]), inline=False)
        else:
            embed.add_field(name="Warrants", value="None", inline=False)
        return embed

    async def communicate(self, content: str = None, embed: discord.Embed = None):
        try:
            await self.prisoner().send(content=content, embed=embed)
        except discord.Forbidden:
            pass
        
        await channelLog(content=content, embed=embed, category=ChannelLogCategories.warrant_updates)

        channel = self.guild.get_channel(config.C["log_channel"])
        await channel.send(content=content, embed=embed)

    def prisoner(self) -> Optional[discord.Member]:
        return self.guild.get_member(self._id)
    
    def total_time_served(self) -> int:
        if not self.committed:
            return 0
        return (datetime.datetime.now(datetime.timezone.utc) - self.committed).total_seconds()

    def total_time_remaining(self) -> int:
        if not self.committed:
            return 0
        full_warrants = sum([warrant.len_seconds for warrant in self.warrants if not warrant.expires])
        until_expires = sum([(warrant.expires - datetime.datetime.now(datetime.timezone.utc)).total_seconds() for warrant in self.warrants if warrant.expires])
        return full_warrants + until_expires

    async def book(self):  # takes their roles, memorizes time committed, and gives them the prisoner role
        if self.roles:
            return

        log("justice", "prisoner", f"Booking prisoner: {utils.normalUsername(self.prisoner())} ({self._id})")

        prisoner_role = self.guild.get_role(config.C["prison_role"])
        user = self.prisoner()
        if prisoner_role in user.roles:
            return
        self.roles = [role.id for role in user.roles]
        self.committed = datetime.datetime.now(datetime.timezone.utc)
        await user.edit(roles=[prisoner_role])

    async def release(self):  # gives them roles back and nothing more
        if not self.roles:
            return
        log("justice", "prisoner", f"Releasing prisoner: {utils.normalUsername(self.prisoner())} ({self._id})")

        embed = discord.Embed(title="Prisoner Released", description=f"You have been released from prison and can now access channels normally.", color=discord.Color.green())
        embed.add_field(name="Time Served", value=utils.seconds_to_time_long((datetime.datetime.now(datetime.timezone.utc) - self.committed).total_seconds()))
        embed.add_field(name="Committed", value=discord_dynamic_timestamp(self.committed, "FR"), inline=False)
        embed.add_field(name="Released", value=discord_dynamic_timestamp(datetime.datetime.now(datetime.timezone.utc), "F"), inline=False)
        embed.set_author(name=utils.normalUsername(self.prisoner()), icon_url=utils.twemojiPNG.unlock)
        await self.communicate(embed=embed)

        user = self.prisoner()
        await user.edit(roles=[self.guild.get_role(role_id) for role_id in self.roles])
        self.roles = []

    def getNextWarrant(self) -> Optional[Warrant]:
        if not self.warrants:
            return None
        for warrant in self.warrants:
            if not warrant.expires:
                if not warrant.frozen and warrant.len_seconds != -1:  # stayed warrants are still served, they're just served out of prison
                    return warrant
            else:
                return None

    def canFree(self):  # whether or not the prisoner can have their roles back
        if not self.warrants:
            return True
        for warrant in self.warrants:
            if not warrant.frozen and not warrant.no_enforce:
                return False
        
    def canArchive(self):
        if self.warrants:
            return False
        if self.roles:
            return False
        return True

    def loadFromDict(self, data):
        self._id = data["_id"]
        self.roles = data["roles"]
        self.committed = data["committed"]
        if self.committed:
            self.committed = self.committed.replace(tzinfo=datetime.timezone.utc)
        self.warrants = [Warrant().loadFromDict(warrant) for warrant in data["warrants"]]
        self.prisoner_name = data["prisoner_name"]
        log("justice", "prisoner", f"Loaded prisoner: {utils.normalUsername(self.prisoner())} ({self._id})")
        return

    async def Archive(self):
        log("justice", "prisoner", f"Archiving prisoner: {utils.normalUsername(self.prisoner())} ({self._id})")
        db_ = await db.create_connection("Warden")
        grab = await db_.delete_one({"_id": self._id})
        PRISONERS.remove(self)

    async def Save(self):
        db_ = await db.create_connection("Warden")
        save = self.__dict__.copy()
        save["warrants"] = [warrant.__dict__ for warrant in save["warrants"]]
        save["guild"] = save["guild"].id
        await db_.update_one({"_id": self._id}, {"$set": save}, upsert=True)

    async def Tick(self):
        await self.HeartBeat()
        if not self.canArchive():
            await self.Save()

    async def HeartBeat(self):
        
        for warrant in self.warrants:
            if warrant.expires and datetime.datetime.now(datetime.timezone.utc) > warrant.expires:
                self.warrants.remove(warrant)

                embed = discord.Embed(title="Warrant Expired", description=f"Warrant {warrant._id} has expired.", color=discord.Color.red())
                embed.set_author(name=utils.normalUsername(self.prisoner()), icon_url=utils.twemojiPNG.chain)
                await self.communicate(embed=embed)

                log("justice", "warrant", f"Warrant expired: {utils.normalUsername(self.prisoner())} ({warrant._id})")
        
        if nxt := self.getNextWarrant():
            nxt.activate()

            embed = discord.Embed(title="Warrant Activated", description=f"Warrant `{nxt._id}` has been activated, you are now serving your sentence for this warrant specifically.", color=discord.Color.red())
            embed.add_field(name="Description", value=nxt.description)
            embed.add_field(name="Started", value=discord_dynamic_timestamp(nxt.started, "F"), inline=False)
            embed.add_field(name="Expires", value=discord_dynamic_timestamp(nxt.expires, "FR"), inline=False)
            # expires - started 
            sentence_seconds = (nxt.expires - nxt.started).total_seconds()
            embed.add_field(name="Expires (S)", value=utils.seconds_to_time_long(sentence_seconds), inline=False)
            embed.set_author(name=utils.normalUsername(self.prisoner()), icon_url=utils.twemojiPNG.chain)

            await self.communicate(embed=embed)

            log("justice", "warrant", f"Warrant activated: {utils.normalUsername(self.prisoner())} ({nxt._id})")
        
        if self.canFree():
            await self.release()
        else:
            await self.book()

        if self.canArchive():
            await self.Archive()

async def populatePrisoners(guild: discord.Guild):
    db_ = await db.create_connection("Warden")
    prisoners = await db_.find({}).to_list(length=None)
    for prisoner in prisoners:
        p = Prisoner(guild)
        p.loadFromDict(prisoner)
        PRISONERS.append(p)

async def voidWarrantByID(warrant_id: str, reason: str = None):
    for prisoner in PRISONERS:
        for warrant in prisoner.warrants:
            if warrant._id == warrant_id:
                prisoner.warrants.remove(warrant)
                embed = discord.Embed(title="Warrant Voided", description=f"Warrant `{warrant._id}` has been voided.", color=discord.Color.red())
                if warrant.expires:
                    embed.add_field(name="Expires", value=discord_dynamic_timestamp(warrant.expires, "FR"), inline=False)
                    time_left_seconds = (warrant.expires - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                    embed.add_field(name="Expires (S)", value=utils.seconds_to_time_long(time_left_seconds), inline=False)
                else:
                    embed.add_field(name="Sentence Length", value=utils.seconds_to_time_long(warrant.len_seconds) if warrant.len_seconds > 0 else "Indefinite", inline=False)
                embed.add_field(name="Description", value=warrant.description, inline=False)
                if reason:
                    embed.add_field(name="Reason For Voiding", value=reason, inline=False)
                embed.set_author(name=utils.normalUsername(prisoner.prisoner()), icon_url=utils.twemojiPNG.ticket)
                await prisoner.communicate(embed=embed)
                log("justice", "warrant", f"Warrant voided: {utils.normalUsername(prisoner.prisoner())} ({warrant._id})")
                return

def getWarrantByID(warrant_id: str) -> Optional[Warrant]:
    for prisoner in PRISONERS:
        for warrant in prisoner.warrants:
            if warrant._id == warrant_id:
                return warrant

def getPrisonerByWarrantID(warrant_id: str) -> Optional[Prisoner]:
    for prisoner in PRISONERS:
        for warrant in prisoner.warrants:
            if warrant._id == warrant_id:
                return prisoner

def getPrisonerByID(user_id: int) -> Optional[Prisoner]:
    for prisoner in PRISONERS:
        if prisoner._id == user_id:
            return prisoner

async def newWarrant(target: discord.Member, category: str, description: str, author: int, author_name: str, len_seconds: int) -> Warrant:
    warrant = Warrant().New(category, description, author, author_name, len_seconds)

    embed = discord.Embed(title="Warrant Issued", description=f"Warrant `{warrant._id}` has been issued.", color=discord.Color.red())
    embed.add_field(name="Author", value=f"{author_name}", inline=False)
    embed.add_field(name="Sentence Length", value=utils.seconds_to_time_long(warrant.len_seconds) if warrant.len_seconds > 0 else "Indefinite", inline=False)
    embed.add_field(name="Description", value=warrant.description, inline=False)
    embed.set_author(name=utils.normalUsername(target), icon_url=utils.twemojiPNG.penlock)

    author_member = target.guild.get_member(author)
    await db.add_note(
        target.id, 
        f"Warrant Issued: {warrant._id}", 
        f"**Category**: {warrant.category}\n**Description**: {warrant.description}\n**Sentence Length**: {utils.seconds_to_time_long(warrant.len_seconds) if warrant.len_seconds > 0 else 'Indefinite'}\n**Author**: {utils.normalUsername(author_member)} ({author})"
    )

    if prisoner := getPrisonerByID(target.id):
        prisoner.warrants.append(warrant)
        await prisoner.communicate(embed=embed)
        await prisoner.Tick()
        return warrant
    else:
        prisoner = Prisoner(target.guild).New(target, utils.normalUsername(target))
        prisoner.warrants.append(warrant)
        PRISONERS.append(prisoner)
        await prisoner.communicate(embed=embed)
        await prisoner.Tick()
        return warrant