from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks

from . import database as db
from . import config
from . import utils
from . import security
from .stasilogging import log, log_user, discord_dynamic_timestamp
from . import warden

import datetime
import time

class Prison(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot):
        self.bot = bot
        self.prisoner_loop.start()

    warrant = discord.SlashCommandGroup("warrant", "Warrant management commands.")

    @warrant.command(name='new', description='Create a new warrant.')
    @option(name='target', description='The target of the warrant.', type=discord.Member, required=True)
    async def new_warrant(self, ctx: discord.ApplicationContext, target: discord.Member):
        if not ctx.author.guild_permissions.manage_roles:
            await ctx.respond("You do not have permission to create warrants.", ephemeral=True)
            return

        class ReasonModal(discord.ui.Modal):
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self.add_item(discord.ui.InputText(label="Reason for Prison Sentence", style=discord.InputTextStyle.long))

            async def callback(self, interaction: discord.Interaction):
                self.value = self.children[0].value
                self.interaction = interaction

        def generateEmbed(reason: str) -> discord.Embed:
            embed = discord.Embed(title="Prison Reason", description=reason, color=0x000000)
            embed.set_author(name=utils.normalUsername(target), icon_url=utils.twemojiPNG.memo)
            return embed

        modal = ReasonModal(title="Reason for Prison Sentence")
        await ctx.send_modal(modal)
        await modal.wait()
        await modal.interaction.response.defer()

        msg = await ctx.respond(embed=generateEmbed(modal.value), ephemeral=True)

        class confirmView(discord.ui.View):
            
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self.value = modal.value
                self.embed = generateEmbed(modal.value)
                self.timed_out = False

            async def on_timeout(self) -> None:
                self.timed_out = True
                return await super().on_timeout()

            @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="✅")
            async def yes_click(self, button, interaction: discord.Interaction):
                for child in self.children:
                    child.disabled = True
                await msg.edit(view=self)
                
                await interaction.response.defer()
                self.stop()

            @discord.ui.button(label="Edit", style=discord.ButtonStyle.red, emoji="📝")
            async def no_click(self, button, interaction: discord.Interaction):
                modal = ReasonModal(title="Reason for Prison Sentece")
                await interaction.response.send_modal(modal)
                await modal.wait()
                self.value = modal.value
                await modal.interaction.response.defer()
                await msg.edit(embed=generateEmbed(modal.value))

        def lenToEmbed(length: int) -> discord.Embed:
            embed = discord.Embed(title="Prison Sentence", description= utils.seconds_to_time_long(length) if length > 0 else "Permanent", color=0x000000)
            embed.set_author(name=utils.normalUsername(target), icon_url=utils.twemojiPNG.swatch)
            return embed

        view = confirmView()
        await msg.edit(embed=view.embed, view=view)
        await view.wait()
        if view.timed_out:
            await ctx.respond("Timed out. Run the command again to re-file", ephemeral=True)
            return
        reason = view.value

        sentence = 60*60*24  # 1 day

        msg = await ctx.respond(embed=lenToEmbed(sentence), ephemeral=True)

        class LengthModal(discord.ui.Modal):
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)

                self.add_item(discord.ui.InputText(label="Length (ex. 1d1h1m1s)", style=discord.InputTextStyle.short))

            async def callback(self, interaction: discord.Interaction):
                self.value = self.children[0].value
                self.interaction = interaction
    
        class lengthView(discord.ui.View):
            
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self.value = sentence
                self.embed = lenToEmbed(sentence)
                self.timed_out = False

            async def on_timeout(self) -> None:
                self.timed_out = True
                return await super().on_timeout()

            @discord.ui.button(label="Proceed", style=discord.ButtonStyle.green, emoji="✅")
            async def yes_click(self, button, interaction: discord.Interaction):
                for child in self.children:
                    child.disabled = True
                await msg.edit(view=self)
                await interaction.response.defer()
                self.stop()

            @discord.ui.button(label="Permanent", style=discord.ButtonStyle.blurple, emoji="🔒")
            async def permanent_click(self, button, interaction: discord.Interaction):
                global sentence
                sentence = -1
                self.value = sentence
                self.embed = lenToEmbed(sentence)
                await msg.edit(embed=self.embed, view=self)
                await interaction.response.defer()

            @discord.ui.button(label="Edit Sentence", style=discord.ButtonStyle.red, emoji="📝")
            async def edit_click(self, button, interaction: discord.Interaction):
                modal = LengthModal(title="Length of Prison Sentence")
                await interaction.response.send_modal(modal)
                await modal.wait()
                await modal.interaction.response.defer()
                try:
                    sentence = utils.time_to_seconds(modal.value)
                    self.value = sentence
                    self.embed = lenToEmbed(sentence)
                    await msg.edit(embed=self.embed, view=self)
                except:
                    await interaction.response.send_message("Invalid length.", ephemeral=True)
                    return
        
        view = lengthView()
        await msg.edit(view=view)
        await view.wait()
        if view.timed_out:
            await ctx.respond("Timed out. Run the command again to re-file", ephemeral=True)
            return
        sentence = view.value

        embed = discord.Embed(title="New Warrant", description=f"Warrant To Be Filed Against {utils.normalUsername(target)}", color=0x000000)
        embed.add_field(name="Sentence Length", value=utils.seconds_to_time_long(sentence) if sentence > 0 else "Permanent / Indefinite", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_author(name=utils.normalUsername(target), icon_url=utils.twemojiPNG.normal)

        msg = await ctx.respond(embed=embed, ephemeral=True)

        class FinalConfirmation(discord.ui.View):
                
                def __init__(self, *args, **kwargs) -> None:
                    super().__init__(*args, **kwargs)
                    self.decision = False
                    self.timed_out = False
    
                async def on_timeout(self) -> None:
                    self.timed_out = True
                    return await super().on_timeout()
    
                @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✅")
                async def yes_click(self, button, interaction: discord.Interaction):
                    for child in self.children:
                        child.disabled = True
                    self.decision = True
                    await msg.edit(view=self)
                    await interaction.response.defer()
                    self.stop()
    
                @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, emoji="🚫")
                async def no_click(self, button, interaction: discord.Interaction):
                    for child in self.children:
                        child.disabled = True
                    await msg.edit(view=self)
                    await interaction.response.defer()
                    self.stop()

        view = FinalConfirmation()
        await msg.edit(view=view)
        await view.wait()
        if view.timed_out:
            await ctx.respond("Timed out. Run the command again to re-file.", ephemeral=True)
            return
        if not view.decision:
            await ctx.respond("Cancelled. Run the command again to re-file.", ephemeral=True)
            return
        
        warrant = await warden.newWarrant(target, "admin", reason, ctx.author.id, sentence)
        await ctx.respond(f"Created warrant `{warrant._id}`", ephemeral=True)

    @warrant.command(name='prisoner', description='View a prisoner\'s warrants.')
    @option(name='prisoner', description='The prisoner to view.', type=discord.Member, required=False)
    async def view_prisoner(self, ctx: discord.ApplicationContext, prisoner: discord.Member = None):
        if not prisoner:
            prisoner = ctx.author
        prisoner = warden.getPrisonerByID(prisoner.id)
        if not prisoner:
            await ctx.respond(f"{utils.normalUsername(prisoner)} is not a prisoner.", ephemeral=True)
            return
        embed = discord.Embed(title=f"{utils.normalUsername(prisoner.prisoner())}'s Warrants", color=0x000000)
        for warrant in prisoner.warrants:
            if warrant.expires:
                embed.add_field(name=f"{warrant.category} ({warrant._id})", value=f"Status: {warrant.status()}\nDescription: {warrant.description}\nAuthor: {utils.normalUsername(ctx.guild.get_member(warrant.author))}\nCreated: {discord_dynamic_timestamp(warrant.created)}\nExpires: {discord_dynamic_timestamp(warrant.expires)}", inline=False)
            else:
                embed.add_field(name=f"{warrant.category} ({warrant._id})", value=f"Status: {warrant.status()}\nDescription: {warrant.description}\nAuthor: {utils.normalUsername(ctx.guild.get_member(warrant.author))}\nCreated: {discord_dynamic_timestamp(warrant.created)}", inline=False)
        await ctx.respond(embed=embed, ephemeral=True)
    
    admin = warrant.create_subgroup(name='admin', description='Admin warrant commands.')

    @admin.command(name='void', description='Void a warrant.')
    @option(name='warrant', description='The warrant to void.', type=str, required=True)
    async def void_warrant(self, ctx: discord.ApplicationContext, warrant: str):
        if not ctx.author.guild_permissions.manage_roles:
            await ctx.respond("You do not have permission to void warrants.", ephemeral=True)
            return
        warrant = warden.getWarrantByID(warrant)
        if not warrant:
            await ctx.respond(f"Warrant {warrant} not found.", ephemeral=True)
            return
        prisoner = warden.getPrisonerByWarrantID(warrant._id)
        await warden.voidWarrantByID(warrant._id)
        log("justice", "warrant", f"Warrant voided by {utils.normalUsername(ctx.author)}: {utils.normalUsername(prisoner.prisoner())} ({warrant._id})")
        await ctx.respond(f"Voided warrant {warrant._id}", ephemeral=True)

    @admin.command(name='voiduser', description='Void all warrants for a user.')
    @option(name='user', description='The user to void warrants for.', type=discord.Member, required=True)
    async def void_user(self, ctx: discord.ApplicationContext, user: discord.Member):
        if not ctx.author.guild_permissions.manage_roles:
            await ctx.respond("You do not have permission to void warrants.", ephemeral=True)
            return
        prisoner = warden.getPrisonerByID(user.id)
        if not prisoner:
            await ctx.respond(f"{utils.normalUsername(user)} is not a prisoner.", ephemeral=True)
            return
        count = len(prisoner.warrants)

        prisoner.warrants = []

        log("justice", "warrant", f"All warrants voided by {utils.normalUsername(ctx.author)}: {utils.normalUsername(prisoner.prisoner())} ({count})")
        embed = discord.Embed(title="Warrants Voided", description=f"All ({count}) warrants for {utils.normalUsername(user)} have been voided.", color=0x000000)
        embed.add_field(name="Voided By", value=utils.normalUsername(ctx.author), inline=False)
        embed.add_field(name="Voided At", value=discord_dynamic_timestamp(datetime.datetime.utcnow()), inline=False)
        embed.add_field(name="Initially Committed At", value=discord_dynamic_timestamp(prisoner.committed), inline=False)
        embed.add_field(name="Total Time Served", value=utils.seconds_to_time_long(prisoner.total_time_served()), inline=False)
        embed.add_field(name="Total Time Remaining", value=utils.seconds_to_time_long(prisoner.total_time_remaining()), inline=False)
        embed.set_author(name=utils.normalUsername(prisoner.prisoner()), icon_url=utils.twemojiPNG.ticket)
        await prisoner.communicate(embed=embed)

        await prisoner.Tick()
        await ctx.respond(embed=embed, ephemeral=True)

    @admin.command(name='tick', description='Create a warrant tick event.')
    async def tick_warrants(self, ctx: discord.ApplicationContext):
        if not ctx.author.guild_permissions.administrator:
            await ctx.respond("You do not have permission to tick warrants.", ephemeral=True)
            return
        for prisoner in warden.PRISONERS:
            await prisoner.Tick()
        await ctx.respond("Done", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        roles = [role.id for role in member.roles]
        await db.set_roles(member.id, roles)
        log("admin", "leave", f"{log_user(member)} left the server")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        user = await db.get_user(member.id)
        if "roles" in user:
            roles = [member.guild.get_role(role) for role in user["roles"]]
            await member.edit(roles=roles)

        elif user == {}:
            unverified_role = member.guild.get_role(config.C["unverified_role"])
            await member.edit(roles=[unverified_role])

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

    @commands.Cog.listener()
    async def on_ready(self):
        await warden.populatePrisoners(self.bot.get_guild(config.C["guild_id"]))
                

    @tasks.loop(minutes=1)
    async def prisoner_loop(self):
        log("justice", "loop", "Running prisoner loop", False)
        for prisoner in warden.PRISONERS:
            await prisoner.Tick()

def setup(bot):
    bot.add_cog(Prison(bot))

