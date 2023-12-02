import datetime
from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, pages, tasks

from . import artificalint as ai
from . import config
from . import database as db
from . import utils
from .stasilogging import discord_dynamic_timestamp, log, log_user, channelLog, ChannelLogCategories


class Social(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bump_reminder.start()

    @slash_command(name='profile', description='Get info about a user.')
    @option('user', discord.User, description='The user to get info about')
    @option('ephemeral', bool, description='Whether to send the message as an ephemeral message')
    async def profile(self, ctx: discord.ApplicationContext, user:discord.User, ephemeral:bool=True):
        embed = discord.Embed(title="User Info", description=f"Info about {user.display_name}", color=0x00ff00)
        embed.set_author(name=str(user), icon_url=user.avatar.url if user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png")
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)

        joined_str = f"{discord_dynamic_timestamp(user.created_at, 'F')} ({discord_dynamic_timestamp(user.created_at, 'R')})"
        embed.add_field(name="Joined Discord", value=joined_str, inline=False)

        if user in ctx.guild.members:
            member = ctx.guild.get_member(user.id)
            joined_str = f"{discord_dynamic_timestamp(member.joined_at, 'F')} ({discord_dynamic_timestamp(member.joined_at, 'R')})"
            embed.add_field(name="Joined Server", value=joined_str, inline=False)
        
        db_user = await db.get_user(user.id)
        if db_user:
            if "messages" in db_user:
                embed.add_field(name="Total Messages", value=db_user["messages"], inline=False)
            if "last_seen" in db_user:
                last_seen_str = f"{discord_dynamic_timestamp(db_user['last_seen'], 'F')} ({discord_dynamic_timestamp(db_user['last_seen'], 'R')})"
                embed.add_field(name="Last Seen", value=last_seen_str, inline=False)
            if "reactions" in db_user:
                react_list = [{"reaction": reaction, "count": db_user["reactions"][reaction]} for reaction in db_user["reactions"]]

                # sort by reaction count, highest to lowest
                react_list.sort(key=lambda x: x["count"], reverse=True)

                # trim to first 10
                react_list = react_list[:10]

                embed.add_field(name="Top 10 Reactions", value="\n".join([f"{i['reaction']}: {i['count']}" for i in react_list]), inline=False)
        
        await ctx.respond(embed=embed, ephemeral=ephemeral)

    # option to right click a user to get their info
    @commands.user_command(name="View Profile")  # create a user command for the supplied guilds
    async def player_information_click(self, ctx: discord.ApplicationContext, member: discord.Member):  # user commands return the member
        await self.profile(ctx, member, ephemeral=True)  # respond with the member's display name
    
    @slash_command(name='interview', description='Get a user\'s vetting answers.')
    @option('user', discord.User, description='The user to get answers for')
    @option('ephemeral', bool, description='Whether to send the message as an ephemeral message')
    async def vettinganswers(self, ctx: discord.ApplicationContext, user:discord.User, ephemeral:bool=True):
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
    async def vettinganswerspaginated(self, ctx: discord.ApplicationContext, user:discord.User):
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

    notes = discord.SlashCommandGroup("notes", "Admin note commands")

    @notes.command(name='view', description='Get a user\'s admin notes.')
    @option('user', discord.User, description='The user to get notes for')
    @option('ephemeral', bool, description='Whether to send the message as an ephemeral message')
    async def viewnotes(self, ctx: discord.ApplicationContext, user:discord.User, ephemeral:bool=True):
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
        
    @notes.command(name='add', description='Add a note to a user.')
    @option('member', discord.Member, description='The member to add the note to')
    @option('note', str, description='The note to add')
    async def addnote(self, ctx: discord.ApplicationContext, member: discord.Member, note: str):
        if not ctx.author.guild_permissions.moderate_members:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)

        note = await db.add_note(member.id, ctx.author.id, note)
        log("admin", "note", f"{log_user(ctx.author)} added note to {log_user(member)} ({note['_id']}: {note['note']})")

        embed = discord.Embed(title="Note", description=f"Note added to **{utils.normalUsername(member)}**\nby **{utils.normalUsername(ctx.author)}**", color=0x00ff6e)
        embed.add_field(name="Note", value=note["note"], inline=False)
        embed.set_footer(text=f"Note ID: `{note['_id']}`")


        await channelLog(embed=embed, category=ChannelLogCategories.stasi_audit_log)

        await ctx.respond(embed=embed, ephemeral=True)

    @notes.command(name='warn', description='Add a warning to a user. (like a note but sends a dm)')
    @option('member', discord.Member, description='The member to add the warning to')
    @option('reason', str, description='The reason for the warning')
    async def warn(self, ctx: discord.ApplicationContext, member: discord.Member, warning: str):
        if not ctx.author.guild_permissions.moderate_members:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)

        note = await db.add_note(member.id, ctx.author.id, f"User Warned: `{warning}`")

        embed = discord.Embed(title="Warning", description=f"**{utils.normalUsername(member)}** has been warned in **{ctx.guild.name}**, by **{utils.normalUsername(ctx.author)}**.") #for\n`{warning}`", color=0xeb6a29)
        embed.add_field(name="Warn Text", value=warning, inline=False)

        embed.set_footer(text=f"Note ID: `{note['_id']}`")

        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            embed.add_field(name="DM", value="*Could Not DM User*", inline=False)
            await ctx.channel.send(member.mention, embed=embed)
        
        await channelLog(embed=embed, category=ChannelLogCategories.stasi_audit_log)

        log("admin", "warn", f"{log_user(ctx.author)} warned {log_user(member)} ({note['_id']}: {note['note']})")
        await ctx.respond(embed=embed, ephemeral=True)

    @notes.command(name='remove', description='Remove a note from a user.')
    @option('note_id', str, description='The id of the note to remove')
    async def removenote(self, ctx: discord.ApplicationContext, note_id: str):
        if not ctx.author.guild_permissions.moderate_members:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        note = await db.get_note(note_id.lower())
        if not note:
            return await ctx.respond("Note not found.", ephemeral=True)
        await db.remove_note(note_id.lower())
        log("admin", "delnote", f"{log_user(ctx.author)} removed note from {note['user']} ({note_id}: {note['note']})")

        user_name = f"<@{note['user']}>"
        if user := self.bot.get_user(note["user"]):
            user_name = utils.normalUsername(user)

        embed = discord.Embed(title="Note Removed", description=f"Note removed from **{user_name}** by {utils.normalUsername(ctx.author)}", color=0x34eb98)
        author = None

        author = self.bot.get_user(note["author"])

        if not author:
            try:
                author = await self.bot.fetch_user(note["author"])
            except discord.NotFound:
                author = None
        
        if not author:
            author = note["author"]

        embed.add_field(name="Original Author", value=author if isinstance(author, int) else author.mention, inline=False)
        embed.add_field(name="Note", value=note["note"], inline=False)
        embed.set_footer(text=f"Note ID: `{note['_id']}`")

        await channelLog(embed=embed, category=ChannelLogCategories.stasi_audit_log)

        await ctx.respond(embed=embed, ephemeral=True)

    @notes.command(name='clear', description='Clear all notes for a user.')
    @option('member', discord.Member, description='The member to clear notes for')
    async def clearnotes(self, ctx: discord.ApplicationContext, member):
        if not ctx.author.guild_permissions.moderate_members:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        
        ret = await db.clear_notes(member.id)
        log("admin", "clearnotes", f"{log_user(ctx.author)} cleared {ret.deleted_count} notes for {log_user(member)}")

        embed = discord.Embed(title="Notes Cleared", description=f"Notes cleared for **{utils.normalUsername(member)}** by **{utils.normalUsername(ctx.author)}**", color=0x34eb98)
        embed.add_field(name="Note Count", value=ret.deleted_count, inline=False)

        await channelLog(embed=embed, category=ChannelLogCategories.stasi_audit_log)

        await ctx.respond(embed=embed, ephemeral=True)

    last_bump = None
    last_bump_channel = None

    @commands.Cog.listener()
    async def on_ready(self):
        last_bump = await db.get_global("last_bump")

        if not last_bump:
            return
        if not last_bump["time"]:
            return
        if not last_bump["channel"]:
            return

        last_bump_time = last_bump["time"].replace(tzinfo=datetime.timezone.utc)  # get the last bump time from the db
        last_bump_channel = self.bot.get_channel(last_bump["channel"]) if last_bump["channel"] else None

        self.last_bump = last_bump_time
        self.last_bump_channel = last_bump_channel

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id == 302050872383242240:  # for bump ping
            if message.embeds and "bump done" in message.embeds[0].description.lower() and message.interaction:

                bumper = message.interaction.user

                await message.channel.send(f"Thanks for bumping, {bumper.mention}! A reminder will be sent in 2 hours to bump again.")
                log("bump", "bumped", f"Bumped by {utils.normalUsername(bumper)}")

                self.last_bump = datetime.datetime.now(datetime.timezone.utc)
                self.last_bump_channel = message.channel
                await db.set_global("last_bump", {"channel": self.last_bump_channel.id, "time": self.last_bump})


        if message.author.bot:
            return
        await db.add_message(message.author.id)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot:
            return
        if before.clean_content == after.clean_content:
            return
    
        embed = discord.Embed(title="Message Edited", description=f"Message edited by **{utils.normalUsername(before.author)}** in {before.channel.mention}", color=0x00ff00)
        embed.add_field(name="Before", value=before.clean_content, inline=False)
        embed.add_field(name="After", value=after.clean_content, inline=False)
        embed.add_field(name="Diff", value=utils.diffMDGrouped(before.clean_content, after.clean_content), inline=False)
        embed.add_field(name="Jump", value=f"[Here]({before.jump_url})", inline=False)
        embed.set_footer(text=f"Message ID: `{before.id}`")

        await channelLog(embed=embed, category=ChannelLogCategories.audit_log)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return
        
        content = message.clean_content if message.clean_content else "*No Content*"
    
        embed = discord.Embed(title="Message Deleted", description=f"Message deleted by **{utils.normalUsername(message.author)}** in {message.channel.mention}", color=0xff0000)
        embed.add_field(name="Content", value=content, inline=False)
        embed.set_footer(text=f"Message ID: `{message.id}`")

        await channelLog(embed=embed, category=ChannelLogCategories.audit_log)

    @tasks.loop(minutes=1, reconnect=True)
    async def bump_reminder(self):  # actually do the bump ping
        if self.last_bump and self.last_bump_channel:
            if (datetime.datetime.now(datetime.timezone.utc) - self.last_bump).total_seconds() > 7200:
                # TODO: make this a config option or a command or something
                log("bump", "reminder", "Bump reminder sent")
                await self.last_bump_channel.send("It's been 2 hours since the last bump! Time to bump again! <@&863539767249338368>")
                self.last_bump_channel = None
                self.last_bump = None
                await db.set_global("last_bump", {"channel": None, "time": None})
    
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
