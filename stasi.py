import asyncio
import os
import subprocess
import sys
import traceback

import discord
import yaml
import git
from discord.ext import commands

from src import config, prison, vetting, administration, social, errortracking, logging

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
async def on_connect():
    logging.log("main", "setup", "Bot connected to Discord.")

@bot.event
async def on_ready():  # I just like seeing basic info like this
    config.G["bot"] = bot
    config.G["guild"] = bot.get_guild(config.C["guild_id"])
    if not config.G["guild"]:
        print("Guild not found, please check your config.yml")
        exit()
    print("-----------------Info-----------------")
    print(f"Total Servers: {len(bot.guilds)}")
    repo = git.Repo(search_parent_directories=True)
    if repo:
        print(f"Git Commit: {repo.head.object.hexsha}")
        print(f"Git Branch: {repo.active_branch}")
        print(f"Last Commit Date: {repo.head.object.committed_datetime}")
        print(f"Last Commit Message: {repo.head.object.message}")
        logging.log("main", "git", f"Git Commit: {repo.head.object.hexsha}")   
        logging.log("main", "git", f"Git Branch: {repo.active_branch}")
        logging.log("main", "git", f"Last Commit Date: {repo.head.object.committed_datetime}")
        logging.log("main", "git", f"Last Commit Message: {repo.head.object.message}")
    logging.log("main", "ready", "Bot is ready to go!")

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
    traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    error_raw = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
    errortracking.report_error(error_raw)

    logging.log("runtimes", "runtime", f"Runtime {error} by {logging.log_user(ctx.author) if ctx else 'unknown'} at {id(error)}: \n```\n{error_raw}\n```", False)
    logging.log("main", "runtime", f"Runtime at {id(error)}. Check runtimes.log for more info.")

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
    traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    error_raw = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
    errortracking.report_error(error_raw)

    logging.log("runtimes", "runtime", f"Runtime {error} by {logging.log_user(ctx.author) if ctx else 'unknown'} at {id(error)}: \n```\n{error_raw}\n```", False)
    logging.log("main", "runtime", f"Runtime at {id(error)}. Check runtimes.log for more info.")

bot.run(config.C["token"])
