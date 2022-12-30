from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks

from . import database as db
from . import config
from . import security
import git
import os
import sys

class Administration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name='git', description='Get currently running git information.')
    async def git(self, ctx):
        embed = discord.Embed(title='Git Info', description='Currently running environment and version information.')
        embed.add_field(name='Python Version', value=f'`{sys.version}`')
        embed.add_field(name='Discord Module Version', value=f'`{discord.__version__}`')
        embed.add_field(name='Git Commit', value=f'`{git.Repo(search_parent_directories=True).head.object.hexsha}`')
        embed.add_field(name='Git Branch', value=f'`{git.Repo(search_parent_directories=True).active_branch}`')
        embed.add_field(name='Upstream Url', value=f'`{git.Repo(search_parent_directories=True).remotes.origin.url}`')
        await ctx.respond(embed=embed, ephemeral=True)

    @slash_command(name='last10', description='Get the last 10 commits made to the codebase.')
    async def last10(self, ctx):
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
    async def update(self, ctx):
        if not security.is_sudoer(ctx.author):
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)

        repo = git.Repo(search_parent_directories=True)
        if repo.is_dirty() and C["no-dirty-repo"]:  # if there are uncommitted changes, don't update
            await ctx.respond("Did not update, repo is dirty.", ephemeral=True)
            return
        if repo.head.object.hexsha == repo.remotes.origin.refs.main.commit.hexsha:
            await ctx.respond("No change in commit hash, not updating.")
            return
        # pull changes
        try:
            repo.remotes.origin.pull(kill_after_timeout=20)
            print("Restarting bot to apply updates...")
            os.execv(sys.argv[0], sys.argv)
        except Exception as e:  # TODO: make this more specific
            print(e)
            return

    @slash_command(name='simonsays', description='Repeat what Simon says.')
    @option('text', str, description='The text to repeat')
    async def player_info(self, ctx, text:str):
        await ctx.respond("Simon says " + text, ephemeral=True)

    @commands.user_command(name="Print Username")  # create a user command for the supplied guilds
    async def player_information_click(self, ctx, member: discord.Member):  # user commands return the member
        await ctx.respond(f"Hello {member.display_name}!")  # respond with the member's display name

    @commands.Cog.listener()
    async def on_message(self, message):
        return

def setup(bot):
    bot.add_cog(Administration(bot))
