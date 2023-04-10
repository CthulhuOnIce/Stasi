from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks

from . import database as db
from . import config
from . import artificalint as ai

class Social(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name='userinfo', description='Get info about a user.')
    @option('user', discord.User, description='The user to get info about')
    @option('ephemeral', bool, description='Whether to send the message as an ephemeral message')
    async def userinfo(self, ctx, user:discord.User, ephemeral:bool=False):
        embed = discord.Embed(title="User Info", description=f"Info about {user.display_name}", color=0x00ff00)
        embed.set_author(name=str(user), icon_url=user.avatar.url if user.avatar else None)
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        embed.add_field(name="Joined Discord", value=user.created_at.strftime("%m/%d/%Y %H:%M:%S"), inline=False)

        if user in ctx.guild.members:
            member = ctx.guild.get_member(user.id)
            embed.add_field(name="Joined Server", value=member.joined_at.strftime("%m/%d/%Y %H:%M:%S"), inline=False)
        
        db_user = await db.get_user(user.id)
        if db_user:
            if "messages" in db_user:
                embed.add_field(name="Total Messages", value=db_user["messages"], inline=False)
            if "reactions" in db_user:
                embed.add_field(name="Total Reactions", value="\n".join([f"{reaction}: {db_user['reactions'][reaction]}" for reaction in db_user["reactions"]]), inline=False)
        
        await ctx.respond(embed=embed, ephemeral=ephemeral)
    
    @slash_command(name='vettinganswers', description='Get a user\'s vetting answers.')
    @option('user', discord.User, description='The user to get answers for')
    @option('ephemeral', bool, description='Whether to send the message as an ephemeral message')
    async def vettinganswers(self, ctx, user:discord.User, ephemeral:bool=True):
        if not ctx.author.guild_permissions.manage_roles:
            await ctx.respond("You do not have permission to use this command.", ephemeral=True)
            return
        db_user = await db.get_user(user.id)
        if not db_user:
            await ctx.respond("User not found.", ephemeral=True)
            return
        if "verification_verdict" not in db_user:
            await ctx.respond("User has not been vetted.", ephemeral=True)
            return
        if "verification_interview" not in db_user:
            await ctx.respond(f"User has no vetting answers. Verdict is lsited as {db_user['verification_verdict']}", ephemeral=True)
            return
        embed = ai.build_verification_embed(user, db_user["verification_interview"], db_user["verification_verdict"])
        await ctx.respond(embed=embed, ephemeral=ephemeral)

    @slash_command(name='notes', description='Get a user\'s admin notes.')
    @option('user', discord.User, description='The user to get notes for')
    @option('ephemeral', bool, description='Whether to send the message as an ephemeral message')
    async def notes(self, ctx, user:discord.User, ephemeral:bool=True):
        if not ctx.author.guild_permissions.manage_roles:
            await ctx.respond("You do not have permission to use this command.", ephemeral=True)
            return

        notes = await db.get_notes(user.id)

        if not notes:
            await ctx.respond("User has no notes.", ephemeral=True)
            return
        
        embed = discord.Embed(title="Notes", description=f"Notes for {user}", color=0x00ff00)
        for note in notes:
            author = self.bot.get_user(note["author"])
            if not author:
                author = await self.bot.fetch_user(note["author"])
            if not author:
                author = "Unknown"
            embed.add_field(name=f'From {author} on {note["timestamp"]}', value=note["note"], inline=False)
        await ctx.respond(embed=embed, ephemeral=ephemeral)
        
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot or reaction.message.author.bot:
            return
        if user == reaction.message.author:
            return

        # if guild emoji and not in guild
        if not isinstance(reaction.emoji, str):
            if isinstance(reaction.emoji, discord.PartialEmoji) or not reaction.emoji.available:
                return
        
        await db.add_reaction(reaction.emoji, reaction.message.author.id)

def setup(bot):
    bot.add_cog(Social(bot))
