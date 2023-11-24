from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks

from . import database as db
from . import config
from . import utils
from . import security
from .stasilogging import log, log_user, discord_dynamic_timestamp
from . import warden

import datetime
import time

class Prison(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot):
        self.bot = bot
        self.prisoner_loop.start()

    warrant = discord.SlashCommandGroup("warrant", "Warrant management commands.")

    @warrant.command(name='new', description='Create a new warrant.')
    async def new_warrant(self, ctx: discord.ApplicationContext):
        user = ctx.guild.get_member(413374859930894336)
        await warden.newWarrant(user, "test", "test", ctx.author.id, 60)

    @warrant.command(name='tick', description='Create a warrant tick event.')
    async def new_warrant(self, ctx: discord.ApplicationContext):
        for prisoner in warden.PRISONERS:
            await prisoner.Tick()
        await ctx.send("Done")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        entry = await guild.audit_logs(limit=1, action=discord.AuditLogAction.ban)
        entry = entry.flatten()
        entry = entry[0]
        await db.add_note(user.id, entry.user.id, f"User Banned: `{entry.reason if entry.reason else 'No reason given'}`")
        log("admin", "ban", f"{log_user(entry.user)} banned {log_user(user)} (reason: {entry.reason if entry.reason else 'No reason given'})")

    @commands.Cog.listener()
    async def on_member_kick(self, guild, user):
        entry = await guild.audit_logs(limit=1, action=discord.AuditLogAction.kick).flatten()[0]
        await db.add_note(user.id, entry.user.id, f"User Kicked: `{entry.reason if entry.reason else 'No reason given'}`")
        log("admin", "kick", f"{log_user(entry.user)} kicked {log_user(user)} (reason: {entry.reason if entry.reason else 'No reason given'})")


    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        await db.add_message(message.author.id)

    @commands.Cog.listener()
    async def on_ready(self):
        await warden.populatePrisoners(self.bot.get_guild(config.C["guild_id"]))
                

    @tasks.loop(minutes=1)
    async def prisoner_loop(self):
        log("justice", "loop", "Running prisoner loop", False)
        for prisoner in warden.PRISONERS:
            await prisoner.Tick()

def setup(bot):
    bot.add_cog(Prison(bot))

