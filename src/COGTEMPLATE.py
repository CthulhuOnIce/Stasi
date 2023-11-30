from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks

from . import database as db
from . import config

class NewCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name='simonsays', description='Repeat what Simon says.')
    @option('text', str, description='The text to repeat')
    async def player_info(self, ctx: discord.ApplicationContext, text:str):
        await ctx.respond("Simon says " + text, ephemeral=True)

    @commands.user_command(name="Print Username")  # create a user command for the supplied guilds
    async def player_information_click(self, ctx: discord.ApplicationContext, member: discord.Member):  # user commands return the member
        await ctx.respond(f"Hello {member.display_name}!")  # respond with the member's display name

    @commands.Cog.listener()
    async def on_message(self, message):
        return

def setup(bot):
    bot.add_cog(NewCog(bot))
