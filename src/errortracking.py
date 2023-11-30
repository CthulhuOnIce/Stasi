from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks, pages
import datetime

from . import database as db
from . import config

error_limit = 10
error_cache = []  # the last [error_limit] errors

class ErrorTracking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    runtimes = discord.SlashCommandGroup("runtimes", "Runtime error tracking commands")
    
    @runtimes.command(name="list", description="List the last [error_limit] errors")
    async def list_errors(self, ctx: discord.Interaction):
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        embeds = []
        # create a new embed with the date as the name and the traceback as the description
        for error in error_cache:
            embeds.append(discord.Embed(title=error["date"], description=error["traceback"]))
        embed = discord.Embed(title="Error List", description="\n\n".join(f"`{error['date']}`: {error['traceback']}" for error in error_cache))
        # paginate
        paginator = pages.Paginator(pages=embeds)
        await paginator.respond(ctx.interaction, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        return

def report_error(text):
    global error_cache
    # create a string like "January 1st, 2021 at 12:00:00 AM"
    date = datetime.datetime.now().strftime("%B %d, %Y at %I:%M:%S %p")
    error_cache.append({"date": date, "traceback": text})
    # trim cache
    error_cache = error_cache[-error_limit:]
    

def setup(bot):
    bot.add_cog(ErrorTracking(bot))


