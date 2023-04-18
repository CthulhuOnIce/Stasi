from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks, pages

from . import database as db
from . import config
from . import artificalint as ai
from .logging import discord_dynamic_timestamp

class Social(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name='userinfo', description='Get info about a user.')
    @option('user', discord.User, description='The user to get info about')
    @option('ephemeral', bool, description='Whether to send the message as an ephemeral message')
    async def userinfo(self, ctx, user:discord.User, ephemeral:bool=False):
        embed = discord.Embed(title="User Info", description=f"Info about {user.display_name}", color=0x00ff00)
        embed.set_author(name=str(user), icon_url=user.avatar.url if user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png")
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
                react_list = [{"reaction": reaction, "count": db_user["reactions"][reaction]} for reaction in db_user["reactions"]]

                # sort by reaction count, highest to lowest
                react_list.sort(key=lambda x: x["count"], reverse=True)

                # trim to first 10
                react_list = react_list[:10]

                embed.add_field(name="Top 10 Reactions", value="\n".join([f"{i['reaction']}: {i['count']}" for i in react_list]), inline=False)
        
        await ctx.respond(embed=embed, ephemeral=ephemeral)
    
    @slash_command(name='interview', description='Get a user\'s vetting answers.')
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

    @slash_command(name='interviewpaged', description='Get a user\'s vetting answers.')
    @option('user', discord.User, description='The user to get answers for')
    async def vettinganswerspaginated(self, ctx, user:discord.User):
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
        embeds = ai.build_paginated_verification_embeds(user, db_user["verification_interview"], db_user["verification_verdict"])
        paginator = pages.Paginator(pages=embeds)
        await paginator.respond(ctx.interaction, ephemeral=True)

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
        
        embeds = []
        
        embed = discord.Embed(title="Notes", description=f"Notes for {user}", color=0x00ff00)
        embed.set_author(name=str(user), icon_url=user.avatar.url if user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png")
        embed.add_field(name="Total Notes", value=len(notes), inline=False)
        embeds.append(embed)

        author_cache = {}

        for i, note in enumerate(notes):
            author = None
            if note["author"] in author_cache:
                author = author_cache[note["author"]]
            else:
                author = self.bot.get_user(note["author"])

                if not author:
                    try:
                        author = await self.bot.fetch_user(note["author"])
                    except discord.NotFound:
                        author = None
            
            if not author:
                author = note["author"]
            else:
                author_cache[note["author"]] = author
            
            embed = discord.Embed(title=f"Note {i+1}/{len(notes)}", description=f'From {author} on {discord_dynamic_timestamp(note["timestamp"], "F")}', color=0x00ff00)
            embed.add_field(name="Note", value=note["note"], inline=False)
            embed.set_footer(text=f"Note ID: `{note['_id']}`")

            embeds.append(embed)

        paginator = pages.Paginator(pages=embeds)
        await paginator.respond(ctx.interaction, ephemeral=ephemeral)
        
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
