from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks

from . import database as db
from . import config
from . import utils
from . import security
from .stasilogging import log, log_user, discord_dynamic_timestamp

import datetime
import time

class Prison(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot):
        self.bot = bot
        self.prisoner_loop.start()

    async def free_prisoner(self, user: dict, admin = None, reason = "Sentence expired."):
        guild = self.bot.get_guild(config.C["guild_id"])
        if not guild:   return
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
            
        await member.edit(roles=roles)
        
        embed = discord.Embed(title="Released", description=f"{member.mention} has been successfully released from prison and can now access channels normally.", color=0x8ff0a4)
        if admin:
            embed = discord.Embed(title="Released Early", description=f"{member.mention} has been released from prison early by {admin.mention}.", color=0x8ff0a4)
        if "sentenced" in user:
            embed.add_field(name="Sentenced", value=discord_dynamic_timestamp(user["sentenced"], "F"), inline=False)
            embed.add_field(name="Time Served", value=utils.seconds_to_time_long((datetime.datetime.utcnow() - user["sentenced"]).total_seconds()), inline=False)
        if admin:
            embed.add_field(name="Original Release Date", value=discord_dynamic_timestamp(user["expires"], "F"), inline=False)
            embed.add_field(name="Time Left", value=utils.seconds_to_time_long((user["expires"] - datetime.datetime.utcnow()).total_seconds()), inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)

        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            pass

        try:
            log_channel = guild.get_channel(config.C["log_channel"])
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass

        await db.remove_prisoner(user["_id"])

        log("justice", "release", f"{log_user(member)} has been successfully released from prison")


    # TODO: debug command remove later
    @slash_command(name='eligiblejurors', description='Test the speed of the juror selection algorithm.')
    async def eligiblejurors(self, ctx):
        if not security.is_sudoer(ctx.author):
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        # get time
        time_start = time.time()

        d_b = await db.create_connection("users")
        user = await d_b.find({
            # last seen less than 2 weeks ago
            # "last_seen": {"$gt": datetime.datetime.utcnow() - datetime.timedelta(days=14)},
            # greater than 300 messages
            "messages": {"$gt": 200},
        }).to_list(None)

        # get time
        time_db_end = time.time()

        # resolve user ids to discord.Member objects
        user_resolved = [ctx.guild.get_member(u["_id"]) for u in user if u]

        time_resolve_end = time.time()

        # get time difference
        total_time_diff = time_resolve_end - time_start

        return await ctx.respond(f"Found ({len(user)} total/{len(user_resolved)} discord.Member) eligible jurors in {total_time_diff} seconds. (db: {time_db_end - time_start}, resolve: {time_resolve_end - time_db_end})", ephemeral=True)

    @slash_command(name='playercsv', description='Get a CSV of all players.')
    async def playercsv(self, ctx):
        if not security.is_sudoer(ctx.author):
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        
        time_start = time.time()
        d_b = await db.create_connection("users")
        user = await d_b.find().to_list(None)
        time_db_end = time.time()

        with open("logs/usercsv.csv", "a+") as a:
            for u in user:
                if "messages" not in u:
                    u["messages"] = 0
                if "last_seen" not in u:
                    u["last_seen"] = None
                a.write(f"{u['_id']},{u['messages']},{u['last_seen']}\n")

        time_csv_end = time.time()

        total_time_diff = time_csv_end - time_start
        await ctx.respond(f"Found ({len(user)} total) players in {total_time_diff} seconds. (db: {time_db_end - time_start}, csv: {time_csv_end - time_db_end})", ephemeral=True)

    @slash_command(name='prison', description='Prison a user.')
    @option('member', discord.Member, description='The member to prison')
    @option('time', str, description='The time to prison the member for')
    @option('reason', str, description='The reason for the prison')
    @option('ephemeral', bool, description='Whether to send the sentence as an ephemeral message')
    async def prison(self, ctx, member: discord.Member, time: str, reason: str, ephemeral: Optional[bool] = False):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        
        await ctx.interaction.response.defer(ephemeral=ephemeral)

        prison_role = ctx.guild.get_role(config.C["prison_role"])
        time_seconds = utils.time_to_seconds(time)
        release_date = datetime.datetime.utcnow() + datetime.timedelta(seconds=time_seconds)

        member_roles = [role for role in member.roles if str(role) != "@everyone"]
        roles = [role.id for role in member_roles]

        await db.add_prisoner(member.id, ctx.author.id, roles, release_date, reason)

        await member.edit(roles=[prison_role])

        log("justice", "prison", f"{log_user(ctx.author)} imprisoned {log_user(member)} for {time} (reason: {reason})")

        embed=discord.Embed(title="Prisoned!", description=f"{member.mention} has been prisoned by {ctx.author.mention}!", color=0xf66151)
        embed.set_author(name=str(member), icon_url=member.avatar.url if member.avatar else "https://cdn.discordapp.com/embed/avatars/0.png")
        embed.add_field(name="Expires", value=discord_dynamic_timestamp(release_date, 'F'), inline=False)
        embed.add_field(name="Time Left", value=utils.seconds_to_time_long(time_seconds), inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)

        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            pass

        try:
            log_channel = ctx.guild.get_channel(config.C["log_channel"])
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass

        await ctx.respond(embed=embed, ephemeral=ephemeral)

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
        
        if prisoner["expires"] > datetime.datetime.utcnow():
            time_left = utils.seconds_to_time_long((prisoner["expires"] - datetime.datetime.utcnow()).total_seconds())
        else:
            time_left = "Expired: Will be released next prison cycle"

        embed=discord.Embed(title="Prisoner Info", description=f"Info For Prisoner #{member.id}", color=0xf66151)
        embed.set_author(name=str(member), icon_url=member.avatar.url if member.avatar else "https://cdn.discordapp.com/embed/avatars/0.png")
        embed.add_field(name="Current Datetime", value=discord_dynamic_timestamp(datetime.datetime.utcnow(), 'F'))
        if "sentenced" in prisoner:
            embed.add_field(name="Sentenced", value=discord_dynamic_timestamp(prisoner["sentenced"], "F"), inline=False)
            embed.add_field(name='Time Served', value=utils.seconds_to_time_long((datetime.datetime.utcnow() - prisoner["sentenced"]).total_seconds()), inline=False)
        embed.add_field(name="Expires", value=discord_dynamic_timestamp(prisoner["expires"], "F"), inline=False)
        embed.add_field(name="Expires (Relative)", value=discord_dynamic_timestamp(prisoner["expires"], "R"), inline=False)
        embed.add_field(name="Time Left", value=time_left, inline=False)
        embed.add_field(name="Reason", value=prisoner["reason"], inline=False)
        await ctx.respond(embed=embed, ephemeral=ephemeral)
    
    @sentence.command(name='release', description='Release a user from prison.')
    @option('member', discord.Member, description='The member to release')
    @option('reason', str, description='The reason for the release')
    @option('ephemeral', bool, description='Whether to send the sentence as an ephemeral message')
    async def release(self, ctx, member: discord.Member, reason: str, ephemeral: Optional[bool] = False):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)

        prisoner = await db.get_prisoner(member.id)
        if not prisoner:
            return await ctx.respond("That user is not in prison.", ephemeral=True)
        
        await ctx.interaction.response.defer(ephemeral=ephemeral)

        await self.free_prisoner(prisoner, ctx.author, reason)
        log("justice", "release", f"{log_user(ctx.author)} released {log_user(member)} from prison (reason: {reason})")

        await db.add_note(member.id, ctx.author.id, f"Released from prison early for '{reason}'")

        await ctx.respond(f"{member.mention} has been released from prison for `{reason}`.", ephemeral=ephemeral)

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

        embed=discord.Embed(title="Sentence Adjusted", description=f"{member.mention} has had their sentence adjusted by {ctx.author.mention}.", color=0x8ff0a4 if time[0] == "-" else 0xf66151)
        embed.add_field(name="Old Expiration Date", value=discord_dynamic_timestamp(prisoner["expires"], "F"), inline=False)
        embed.add_field(name="New Expiration Date", value=discord_dynamic_timestamp(release_date, "F"), inline=False)
        embed.add_field(name="Difference", value=f"<{time[0]}> {utils.seconds_to_time_long(time_seconds_absolute_value)}", inline=False)
        if time_left_in_new_sentence < 0:
            embed.add_field(name="Time Left", value="Expired: Will be released next prison cycle", inline=False)
        else:
            embed.add_field(name="Time to Release", value=utils.seconds_to_time_long(time_left_in_new_sentence), inline=False)
        embed.set_author(name=str(member), icon_url=member.avatar.url if member.avatar else "https://cdn.discordapp.com/embed/avatars/0.png")

        await db.add_note(member.id, ctx.author.id, f"Sentence adjusted by '{time}', new release date is '{release_date}'")
        result = await db.adjust_sentence(member.id, release_date)

        log("justice", "adjust", f"{log_user(ctx.author)} adjusted sentence of {log_user(member)} by {time} (new release date: {release_date})")
        
        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            pass

        try:
            log_channel = ctx.guild.get_channel(config.C["log_channel"])
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
        
        await ctx.respond(embed=embed, ephemeral=ephemeral)

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

