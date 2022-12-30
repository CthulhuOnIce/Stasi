from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks

from . import database as db
from . import config

class Social(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name='userinfo', description='Get info about a user.')
    @option('user', discord.User, description='The user to get info about')
    @option('ephemeral', bool, description='Whether to send the message as an ephemeral message')
    async def userinfo(self, ctx, user:discord.User, ephemeral:bool=False):
        embed = discord.Embed(title="User Info", description=f"Info about {user.display_name}", color=0x00ff00)
        embed.set_author(name=str(user), icon_url=user.avatar.url)
        embed.set_thumbnail(url=user.avatar.url)
        embed.add_field(name="Joined Discord", value=user.created_at.strftime("%d/%m/%Y %H:%M:%S"))

        if user in ctx.guild.members:
            member = ctx.guild.get_member(user.id)
            embed.add_field(name="Joined Server", value=member.joined_at.strftime("%d/%m/%Y %H:%M:%S"))
        
        db_user = await db.get_user(user.id)
        if db_user:
            if "messages" in db_user:
                embed.add_field(name="Total Messages", value=db_user["messages"])
            if "reactions" in db_user:
                embed.add_field(name="Total Reactions", value="\n".join([f"{reaction}: {db_user['reactions'][reaction]}" for reaction in db_user["reactions"]]))
        
        await ctx.respond(embed=embed, ephemeral=ephemeral)

def setup(bot):
    bot.add_cog(Social(bot))
