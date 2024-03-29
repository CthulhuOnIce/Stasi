from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks
import simplejson as json

from . import database as db
from . import config
from . import security
import git
import os
import sys
import io

class Administration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name='git', description='Get currently running git information.')
    async def git(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(title='Git Info', description='Currently running environment and version information.')
        embed.add_field(name='Python Version', value=f'`{sys.version}`', inline=False)
        embed.add_field(name='Discord Module Version', value=f'`{discord.__version__}`', inline=False)
        embed.add_field(name='Git Commit', value=f'`{git.Repo(search_parent_directories=True).head.object.hexsha}`', inline=False)
        embed.add_field(name='Git Branch', value=f'`{git.Repo(search_parent_directories=True).active_branch}`', inline=False)
        embed.add_field(name='Upstream Url', value=f'`{git.Repo(search_parent_directories=True).remotes.origin.url}`', inline=False)
        await ctx.respond(embed=embed, ephemeral=True)

    @slash_command(name='last10', description='Get the last 10 commits made to the codebase.')
    async def last10(self, ctx: discord.ApplicationContext):
        repo = git.Repo(search_parent_directories=True)
        embed = discord.Embed(title='Last 10 Commits', description='The last 10 commits made to the codebase.')
        limit = 10
        count = 0
        for commit in repo.iter_commits():
            if count == limit:
                break
            embed.add_field(name=f"`{commit.hexsha[:6]}` by {commit.author}", value=f'`{commit.message}`', inline=False)
            count += 1
        await ctx.respond(embed=embed, ephemeral=True)

    @slash_command(name='update', description='Update the bot.')
    @option(name='force', description='Force update even if repo is dirty.', type=bool, required=False, default=False)
    async def update(self, ctx: discord.ApplicationContext, force: bool = False):
        if not security.is_sudoer(ctx.author):
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)

        repo = git.Repo(search_parent_directories=True)
        if repo.is_dirty() and not force:  # if there are uncommitted changes, don't update
            await ctx.respond("Did not update, repo is dirty.", ephemeral=True)
            return
            
        # pull changes
        try:
            repo.remotes.origin.pull(kill_after_timeout=20)
            await ctx.respond("Restarting bot to apply updates...", ephemeral=True)
            os.execv(sys.argv[0], sys.argv)
        except Exception as e:  # TODO: make this more specific
            print(e)
            return


    @commands.Cog.listener()
    async def on_message(self, message):
        return

def setup(bot):
    bot.add_cog(Administration(bot))
