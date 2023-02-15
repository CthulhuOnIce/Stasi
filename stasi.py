import asyncio
import os
import subprocess
import sys
import traceback

import discord
import yaml
from discord.ext import commands

from src import config, prison, vetting, administration, social, errortracking

# from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice

feedbacktimeout = []

intents = discord.Intents.all()

bot = commands.Bot(intents=intents, owner_id=config.C["sudoers"][0])

# Setup cogs
prison.setup(bot)
vetting.setup(bot)
administration.setup(bot)
social.setup(bot)
errortracking.setup(bot)
# debug.setup(bot, C)
# electionmanager.setup(bot, C)
# legislation.setup(bot, C)
# source.setup(bot, C)


@bot.event
async def on_ready():  # I just like seeing basic info like this
    config.G["bot"] = bot
    config.G["guild"] = bot.get_guild(config.C["guild_id"])
    if not config.G["guild"]:
        print("Guild not found, please check your config.yml")
        exit()
    print("-----------------Info-----------------")
    print(f"Total Servers: {len(bot.guilds)}")

@bot.event
async def on_command_error(ctx, error):  # share certain errors with the user
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"Bad Argument: {error}")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing Argument: {error}")
        return
    if isinstance(error, commands.CommandInvokeError):
        original = error.original
        if isinstance(original, IndexError):
            await ctx.send(f"IndexError: {original}\n[This might mean your search found no results]")
            return
    await ctx.send("That command caused an error. This has been reported to the developer.")
    print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
    traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
    if ctx:
        print(f"Author: {ctx.author}")
        print(f"Command: {ctx.message.clean_content}")
    error_raw = ''.join(traceback.format_exception(error))
    errortracking.report_error(error_raw)

@bot.event
async def on_application_command_error(ctx, error):  # share certain errors with the user
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"Bad Argument: {error}")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing Argument: {error}")
        return
    if isinstance(error, commands.CommandInvokeError):
        original = error.original
        if isinstance(original, IndexError):
            await ctx.send(f"IndexError: {original}\n[This might mean your search found no results]")
            return
    await ctx.respond("That command caused an error. This has been reported to the developer.", ephemeral = True)
    print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
    traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
    if ctx:
        print(f"Author: {ctx.author}")
    error_raw = ''.join(traceback.format_exception(error))
    errortracking.report_error(error_raw)


@bot.event
async def on_error(event, one, two):
    error_raw = ''.join(traceback.format_exc())
    errortracking.report_error(error_raw)

bot.run(config.C["token"])
