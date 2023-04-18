from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks

from . import database as db
from . import config
from . import utils
from .logging import log, log_user

import datetime

class Prison(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot):
        self.bot = bot

    async def free_prisoner(self, user: dict):
        guild = self.bot.get_guild(config.C["guild"])
        member = guild.get_member(user["_id"])

        if not member:  # the user left the server, remove them from database only
            # get their roles to see if they are in the guild
            roles = await db.get_roles(user["_id"])
            if roles:
                await db.add_roles_stealth(user["_id"], user["roles"])  # so they get their original roles if they rejoin
            await db.remove_prisoner(user["_id"])
            log("justice", "expired-nouser", f"Prisoner {user['_id']} expired but is no longer in the guild.")
            return

        prison_role = guild.get_role(config.C["prison_role"])

        await member.remove_roles(prison_role)

        roles = []
        for role_id in user["roles"]:
            role = guild.get_role(role_id)
            if role and role < guild.me.top_role:
                roles.append(role)
            
        await member.add_roles(*roles)
        embed = embed=discord.Embed(title="Released", description="You have been released from prison and can now access channels normally.", color=0x8ff0a4)
        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            pass

        await db.remove_prisoner(user["_id"])

        log("justice", "expired", f"{log_user(member)}'s sentence has expired and they have been released from prison")


    @slash_command(name='prison', description='Prison a user.')
    @option('member', discord.Member, description='The member to prison')
    @option('time', str, description='The time to prison the member for')
    @option('reason', str, description='The reason for the prison')
    async def prison(self, ctx, member: discord.Member, time: str, reason: str):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)

        prison_role = ctx.guild.get_role(config.C["prison_role"])
        time_seconds = utils.time_to_seconds(time)
        release_date = datetime.datetime.utcnow() + datetime.timedelta(seconds=time_seconds)

        await member.add_roles(prison_role)
        roles = [role.id for role in member.roles]
        await db.add_prisoner(member.id, ctx.author.id, roles, release_date, reason)

        for role in member.roles:
            try:
                await member.remove_roles(role)
            except Exception as e:
                log("debug", "roleissue", f"Role {role} on user {log_user(member)}: {e}")

        log("justice", "prison", f"{log_user(ctx.author)} imprisoned {log_user(member)} for {time} (reason: {reason})")

        embed=discord.Embed(title="Prisoned!", description=f"{member} has been prisoned!", color=0xf66151)
        embed.set_author(name=str(member), icon_url=member.avatar.url if member.avatar else "https://cdn.discordapp.com/embed/avatars/0.png")
        embed.add_field(name="Expires", value=release_date.strftime("%m/%d/%Y %H:%M:%S"), inline=False)
        embed.add_field(name="Time Left", value=utils.seconds_to_time_long(time_seconds), inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)

        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            pass

        await ctx.respond(embed=embed)



    sentence = discord.SlashCommandGroup("sentence", "View or edit prisoner sentences")
    
    @sentence.command(name='view', description='Get the sentence of a user.')
    @option('member', discord.Member, description='The member to get the sentence of')
    @option('ephemeral', bool, description='Whether to send the sentence as an ephemeral message')
    async def view_sentence(self, ctx, member: discord.Member = None, ephemeral: Optional[bool] = True):
        if not member:
            member = ctx.author

        prisoner = await db.get_prisoner(member.id)
        if not prisoner:
            return await ctx.respond("That user is not in prison.", ephemeral=True)
        
        time_left = utils.seconds_to_time_long((prisoner["expires"] - datetime.datetime.utcnow()).total_seconds())

        embed=discord.Embed(title="Prisoner Info", description=f"Info For Prisoner #{member.id}", color=0xf66151)
        embed.set_author(name=str(member), icon_url=member.avatar.url if member.avatar else "https://cdn.discordapp.com/embed/avatars/0.png")
        embed.add_field(name="Expires", value=prisoner["expires"].strftime("%m/%d/%Y %H:%M:%S"), inline=False)
        embed.add_field(name="Time Left", value=time_left, inline=False)
        embed.add_field(name="Reason", value=prisoner["reason"], inline=False)
        await ctx.respond(embed=embed, ephemeral=ephemeral)
    
    @sentence.command(name='release', description='Release a user from prison.')
    @option('member', discord.Member, description='The member to release')
    @option('reason', str, description='The reason for the release')
    async def release(self, ctx, member: discord.Member, reason: str):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)

        prisoner = await db.get_prisoner(member.id)
        if not prisoner:
            return await ctx.respond("That user is not in prison.", ephemeral=True)

        await self.free_prisoner(prisoner)
        log("justice", "release", f"{log_user(ctx.author)} released {log_user(member)} from prison (reason: {reason})")

        await db.add_note(member.id, ctx.author.id, f"Released from prison early for '{reason}'")

        try:
            await member.send(f"You have been released from prison early for `{reason}`.")
        except discord.Forbidden:
            pass

        await ctx.respond(f"{member.mention} has been released from prison for `{reason}`.")

    @sentence.command(name='adjust', description='Adjust the sentence of a user.')
    @option('member', discord.Member, description='The member to adjust the sentence of')
    @option('time', str, description='The time to adjust the sentence by')
    @option('ephemeral', bool, description='Whether to send the sentence as an ephemeral message')
    async def adjustsentence(self, ctx, member: discord.Member, time: str, ephemeral: Optional[bool] = True):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        
        if time[0] not in ["+", "-"]:
            return await ctx.respond("Time must start with `+` or `-`.", ephemeral=True)
        
        time_abs = time[1:]
        time_seconds = utils.time_to_seconds(time_abs)

        if time[0] == "-":
            time_seconds = -time_seconds

        time_seconds_absolute_value = abs(time_seconds)

        prisoner = await db.get_prisoner(member.id)
        if not prisoner:
            return await ctx.respond("That user is not in prison.", ephemeral=True)
        
        release_date = prisoner["expires"] + datetime.timedelta(seconds=time_seconds)

        time_left_in_new_sentence = (release_date - datetime.datetime.utcnow()).total_seconds()

        embed=discord.Embed(title="Sentence Adjusted", description=f"{member} has had their sentence adjusted.", color=0x8ff0a4 if time[0] == "-" else 0xf66151)
        embed.add_field(name="Old Expiration Date", value=prisoner["expires"].strftime("%m/%d/%Y %H:%M:%S"), inline=False)
        embed.add_field(name="New Expiration Date", value=release_date.strftime("%m/%d/%Y %H:%M:%S"), inline=False)
        embed.add_field(name="Difference", value=f"{time[0]} {utils.seconds_to_time_long(time_seconds_absolute_value)}", inline=False)
        embed.add_field(name="Time to Release", value=utils.seconds_to_time_long(time_left_in_new_sentence), inline=False)
        embed.set_author(name=str(member), icon_url=member.avatar.url if member.avatar else "https://cdn.discordapp.com/embed/avatars/0.png")

        await db.add_note(member.id, ctx.author.id, f"Sentence adjusted by '{time}', new release date is '{release_date}'")
        result = await db.adjust_sentence(member.id, release_date)

        log("justice", "adjust", f"{log_user(ctx.author)} adjusted sentence of {log_user(member)} by {time} (new release date: {release_date})")
        
        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            pass
        
        await ctx.respond(embed=embed, ephemeral=ephemeral)
    
    @slash_command(name='note', description='Add a note to a user.')
    @option('member', discord.Member, description='The member to add the note to')
    @option('note', str, description='The note to add')
    async def note(self, ctx, member: discord.Member, note: str):
        if not ctx.author.guild_permissions.moderate_members:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)

        note = await db.add_note(member.id, ctx.author.id, note)
        log("admin", "note", f"{log_user(ctx.author)} added note to {log_user(member)} ({note['_id']}: {note['note']})")
        await ctx.respond(f"Added note to {member.mention}: {note['note']}. ({note['_id']})", ephemeral=True)

    @slash_command(name='warn', description='Add a warning to a user.')
    @option('member', discord.Member, description='The member to add the warning to')
    @option('reason', str, description='The reason for the warning')
    async def warn(self, ctx, member: discord.Member, warning: str):
        if not ctx.author.guild_permissions.moderate_members:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        
        embed = discord.Embed(title="Warning", description=f"You have been warned in {ctx.guild.name}, by `{ctx.author}` for\n`{warning}`", color=discord.Color.red())

        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            embed.description += "\n\n*I was unable to DM you.*"
            await ctx.channel.send(member.mention, embed=embed)

    
        note = await db.add_note(member.id, ctx.author.id, f"User Warned: `{warning}`")
        log("admin", "warn", f"{log_user(ctx.author)} warned {log_user(member)} ({note['_id']}: {note['note']})")
        await ctx.respond(f"User has been warned.", embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        entry = await guild.audit_logs(limit=1, action=discord.AuditLogAction.ban)
        entry = entry.flatten()
        entry = entry[0]
        await db.add_note(user.id, entry.user.id, f"User Banned: `{entry.reason if entry.reason else 'No reason given'}`")
        log("admin", "ban", f"{log_user(entry.user)} banned {log_user(user)} (reason: {entry.reason if entry.reason else 'No reason given'})")

    @commands.Cog.listener()
    async def on_member_kick(self, guild, user):
        entry = await guild.audit_logs(limit=1, action=discord.AuditLogAction.kick).flatten()[0]
        await db.add_note(user.id, entry.user.id, f"User Kicked: `{entry.reason if entry.reason else 'No reason given'}`")
        log("admin", "kick", f"{log_user(entry.user)} kicked {log_user(user)} (reason: {entry.reason if entry.reason else 'No reason given'})")


    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        await db.add_message(message.author.id)
                

    @tasks.loop(minutes=1)
    async def prisoner_loop(self):
        log("justice", "loop", "Running prisoner loop", False)
        for user in await db.get_expired_prisoners():
            await self.free_prisoner(user)

def setup(bot):
    bot.add_cog(Prison(bot))
