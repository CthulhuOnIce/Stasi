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
from .stasilogging import *
from . import casemanager as cm



class Justice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CaseManager.start()

    @slash_command(name='filetestcase', description='File a test case.')
    @option("member", discord.Member, description="The member to file a case against.")
    @option("reason", str, description="The reason for filing a case.")
    async def test_case(self, ctx, member: discord.Member, reason: str):
        await cm.Case().New(ctx.guild, self.bot, f"{cm.Case.normalUsername(None, ctx.author)} v. {cm.Case.normalUsername(None, member)}", reason, ctx.author, member, cm.WarningPenalty(cm.Case))

    # add option to report a user by right clicking a message
    @commands.message_command(name="Report Message to Server Staff")
    async def report_message(self, ctx, message: discord.Message):
        return await ctx.respond("This command is not yet implemented.", ephemeral=True)

    @commands.user_command(name="Report User to Server Staff")
    async def report_user(self, ctx, member: discord.Member):
        return await ctx.respond("This command is not yet implemented.", ephemeral=True)

    @tasks.loop(minutes=15)
    async def CaseManager(self):
        log("Justice", "CaseManager", "Doing Periodic Case Manager Loop")
        for case in cm.ACTIVECASES:
            await case.Tick()
        return

def setup(bot):
    bot.add_cog(Justice(bot))
