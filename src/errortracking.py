from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks

from . import database as db
from . import config

error_limit = 10
error_cache = []  # the last [error_limit] errors


class ErrorTracking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    group = discord.SlashCommandGroup("error", "Error tracking commands")

    @group.command(name="new", description="Debug: create a new test error")
    async def new_errors(self, ctx):
        global error_cache

        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
    
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_cache.append({"date": date, "traceback": f"Debug error created by {ctx.author}"})
        error_cache = error_cache[-error_limit:]

    
    @group.command(name="list", description="List the last [error_limit] errors")
    async def list_errors(self, ctx):
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        embeds = []
        # create a new embed with the date as the name and the traceback as the description
        for error in error_cache:
            embeds.append(discord.Embed(title=error["date"], description=error["traceback"]))
        embed = discord.Embed(title="Error List", description="\n\n".join(f"`{error['date']}`: {error['traceback']}" for error in error_cache))
        # paginate
        paginator = pages.Paginator(pages=embeds, per_page=1)
        await paginator.respond(ctx.interaction, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        return

def report_error(text):
    global error_cache
    # create a string like "2021-01-01 12:00:00"
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    error_cache.append({"date": date, "traceback": text})
    # trim cache
    error_cache = error_cache[-error_limit:]
    

def setup(bot):
    bot.add_cog(ErrorTracking(bot))


