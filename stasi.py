import asyncio
import os
import subprocess
import sys
import traceback

import discord
import yaml
from discord.ext import commands
import git

from src import config, prison, vetting, administration, social, errortracking, justice
from src import stasilogging as logging

# from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice

feedbacktimeout = []

intents = discord.Intents.all()

bot = commands.Bot(intents=intents, owner_id=config.C["sudoers"][0])

logging.log("main", "setup", "Setting up cogs...")

# Setup cogs
i = 0
COGS = [prison, vetting, administration, social, errortracking, justice]
for cog in COGS:
    i += 1
    cog.setup(bot)
    logging.log("main", "setup", f"Cog {i}/{len(COGS)} loaded ({cog.__name__}))")


logging.log("main", "setup", f"Finished setting up {i} cogs")

@bot.event
async def on_connect():
    await bot.sync_commands()
    logging.log("main", "setup", "Connected to discord, synced commands")

@bot.event
async def on_ready():  # I just like seeing basic info like this
    config.G["bot"] = bot
    config.G["guild"] = bot.get_guild(config.C["guild_id"])
    if not config.G["guild"]:
        print("Guild not found, please check your config.yml")
        exit()
    logging.log("main", "setup", f"Bot finished initializing.")
    print("-----------------Info-----------------")
    print(f"Total Servers: {len(bot.guilds)}")
    # git repo info
    repo = git.Repo(search_parent_directories=True)
    if repo:
        sha = repo.head.object.hexsha
        print(f"Git Commit: {sha}")
        message = repo.git.log('-1', '--pretty=%B').replace('\n', '')
        print(f"Commit Message: {message}")
        print(f"Branch: {repo.active_branch}")
        print(f"Last Commit Date: {repo.head.object.committed_datetime}")
        logging.log("main", "git", f"Git Commit: {sha}\nCommit Message: {message}\nBranch: {repo.active_branch}\nLast Commit Date: {repo.head.object.committed_datetime}", False, True)
        

@bot.event
async def on_command_error(ctx: discord.ApplicationContext, error):  # share certain errors with the user
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

    error_raw = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
    errortracking.report_error(error_raw)

    logging.log("main", "runtime", f"Error {logging.lid(error)} in '{ctx.command}' by '{logging.log_user(ctx.author) if ctx.author else 'unknown'}'. Check runtimes.log for more details.")
    logging.log("runtimes", "error", f"Error {logging.lid(error)} in '{ctx.command}' by '{logging.log_user(ctx.author) if ctx.author else 'unknown'}': \n```\n{error_raw}\n```", False, True)

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
    
    error_raw = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
    errortracking.report_error(error_raw)

    logging.log("main", "runtime", f"Error {logging.lid(error)} in '{ctx.command}' by '{logging.log_user(ctx.author) if ctx.author else 'unknown'}'. Check runtimes.log for more details.")
    logging.log("runtimes", "error", f"Error {logging.lid(error)} in '{ctx.command}' by '{logging.log_user(ctx.author) if ctx.author else 'unknown'}': \n```\n{error_raw}\n```", False, True)

    await ctx.respond("That command caused an error. This has been reported to the developer.", ephemeral = True)

bot.run(config.C["token"])
