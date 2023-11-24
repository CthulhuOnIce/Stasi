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
        
        def lenToEmbed(length: int) -> discord.Embed:
            embed = discord.Embed(title="Prison Sentence", description= utils.seconds_to_time_long(length) if length > 0 else "Permanent", color=0x000000)
            return embed

        sentence = 60*60*24  # 1 day
        msg: discord.interactions.Interaction = await ctx.respond(embed=lenToEmbed(sentence), ephemeral=True)

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

            @discord.ui.button(label="Proceed", style=discord.ButtonStyle.green, emoji="✅")
            async def yes_click(self, button, interaction: discord.Interaction):
                for child in self.children:
                    child.disabled = True
                await msg.edit_original_response(view=self)
                await interaction.response.defer()
                self.stop()

            @discord.ui.button(label="Permanent", style=discord.ButtonStyle.blurple, emoji="🔒")
            async def permanent_click(self, button, interaction: discord.Interaction):
                global sentence
                sentence = -1
                self.value = sentence
                self.embed = lenToEmbed(sentence)
                await msg.edit_original_response(embed=self.embed, view=self)
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
                    await msg.edit_original_response(embed=self.embed, view=self)
                except:
                    await interaction.response.send_message("Invalid length.", ephemeral=True)
                    return
        
        view = lengthView()
        await msg.edit_original_response(view=view)
        await view.wait()
        sentence = view.value

        await ctx.respond(sentence, ephemeral=True)

        # await warden.newWarrant(user, "test", "test", ctx.author.id, 60)

    @warrant.command(name='prisoner', description='View a prisoner\'s warrants.')
    @option(name='prisoner', description='The prisoner to view.', type=discord.Member, required=False)
    async def view_prisoner(self, ctx: discord.ApplicationContext, prisoner: discord.Member = None):
        if not prisoner:
            prisoner = ctx.author
        prisoner = warden.getPrisoner(prisoner)
        if not prisoner:
            await ctx.respond(f"{utils.normalUsername(prisoner)} is not a prisoner.", ephemeral=True)
            return
        embed = discord.Embed(title=f"{utils.normalUsername(prisoner.prisoner())}'s Warrants", color=0x000000)
        for warrant in prisoner.warrants:
            embed.add_field(name=f"{warrant.category} ({warrant._id})", value=f"Status: {warrant.status}\nDescription: {warrant.description}\nAuthor: {utils.normalUsername(ctx.guild.get_member(warrant.author))}\nCreated: {discord_dynamic_timestamp(warrant.created)}\nExpires: {discord_dynamic_timestamp(warrant.expires)}", inline=False)
        await ctx.respond(embed=embed, ephemeral=True)

    @warrant.command(name='tick', description='Create a warrant tick event.')
    async def tick_warrants(self, ctx: discord.ApplicationContext):
        for prisoner in warden.PRISONERS:
            await prisoner.Tick()
        await ctx.respond("Done", ephemeral=True)

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

