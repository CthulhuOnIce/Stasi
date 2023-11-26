import asyncio
import datetime
import random
import time
from typing import Optional

import discord
import motor  # doing this locally instead of in database.py for greater modularity
from discord import option, slash_command
from discord.ext import commands, tasks

from . import casemanager as cm
from . import casemanagerui as cmui
from . import config
from . import database as db
from . import quickask as qa
from . import report as rm
from . import utils
from .stasilogging import *

case_selection = {}

def setActiveCase(member: discord.Member, case: cm.Case):
    case_selection[member.id] = case.id

def getActiveCase(member: discord.Member) -> cm.Case:
    return cm.getCaseByID(case_selection.get(member.id, None))

class Justice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CaseManager.start()

    @commands.Cog.listener()
    async def on_ready(self):
        await cm.populateActiveCases(self.bot, self.bot.get_guild(config.C["guild_id"]))
        log("Case", "CaseManager", "Justice module ready.")

    async def active_case_options(ctx: discord.AutocompleteContext):
        return [f"{case}: {case.id}" for case in cm.ACTIVECASES]

    case = discord.SlashCommandGroup("case", "Basic case management commands")
    @case.command(name="select", description="Select a case as your active case.")
    async def select_case(self, ctx: discord.ApplicationContext, case: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(active_case_options))):
        case = cm.getCaseByID(case.split(" ")[-1])
        if case is None:
            return await ctx.respond("Invalid case ID.", ephemeral=True)
        
        setActiveCase(ctx.author, case)
        return await ctx.respond(f"Selected case **{case}** (`{case.id}`) as your active case.", ephemeral=True)

    @case.command(name='file', description='File a case against a user.')
    @option("member", discord.Member, description="The member to file a case against.")
    async def file_case(self, ctx: discord.ApplicationContext, member: discord.Member):
        
        # Collect Reason from User

        class ReasonModal(discord.ui.Modal):
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)

                self.add_item(discord.ui.InputText(label="Reason for Filing Case Against User", style=discord.InputTextStyle.long))

            async def callback(self, interaction: discord.Interaction):
                self.value = self.children[0].value
                self.interaction = interaction

        modal = ReasonModal(title="Reason for Filing Case Against User")
        await ctx.send_modal(modal)
        await modal.wait()
        if modal.value is None:
            return await modal.interaction.response.send_message("You must provide a reason for filing a case.", ephemeral=True)
        await modal.interaction.response.defer()
        

        def generateEmbed(text):
            embed = discord.Embed(title="Confirm Reason", description=f"Is this your reason for filing a case against {utils.normalUsername(member)}?")
            embed.add_field(name="Reason", value=text)
            return embed

        embed = generateEmbed(modal.value)
        msg = await ctx.respond(embed=embed, ephemeral=True)

        class confirmView(discord.ui.View):
            
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self.value = modal.value
                self.embed = generateEmbed(modal.value)

            @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, emoji="✅")
            async def yes_click(self, button, interaction: discord.Interaction):
                for child in self.children:
                    child.disabled = True
                await msg.edit(view=self)
                
                await interaction.response.defer()
                self.stop()

            @discord.ui.button(label="No", style=discord.ButtonStyle.red, emoji="❎")
            async def no_click(self, button, interaction: discord.Interaction):
                modal = ReasonModal(title="Reason for Filing Case Against User")
                await interaction.response.send_modal(modal)
                await modal.wait()
                self.value = modal.value
                await modal.interaction.response.defer()
                await msg.edit(embed=generateEmbed(modal.value))
        
        cf = confirmView()
        await msg.edit(embed=embed, view=cf)
        await cf.wait()
        reason = cf.value

        await ctx.respond(f"Filed case against {utils.normalUsername(member)} for reason: {reason}", ephemeral=True)

        guild = self.bot.get_guild(config.C["guild_id"])
        case = await cm.Case(self.bot, guild).New(ctx.author, member, cm.WarningPenalty(cm.Case).New("This is a test warning"), reason)
        setActiveCase(ctx.author, case)
        setActiveCase(member, case)

    # TODO: Confirmation message
    @case.command(name="statement", description="Make a statement in your active case.")
    async def statement(self, ctx: discord.ApplicationContext, statement: str):
        case = getActiveCase(ctx.author)
        if case is None:
            return await ctx.respond("You do not have an active case.", ephemeral=True)
        if not case.canSubmitMotions(ctx.author):
            return await ctx.respond("You cannot make a statement in this case.", ephemeral=True)
        await case.personalStatement(ctx.author, statement)
        await ctx.respond("Statement added.", ephemeral=True)

    @case.command(name="info", description="Get information about a case.")
    async def case_info(self, ctx: discord.ApplicationContext, ephemeral: bool = True):
        case = getActiveCase(ctx.author)
        if case is None:
            return await ctx.respond("You do not have an active case.", ephemeral=True)

        front_page = discord.Embed(title=str(case), description=str(case.id))
        front_page.add_field(name="Current Status", value=case.status, inline=False)
        front_page.add_field(name="Filed Datetime", value=discord_dynamic_timestamp(case.created, 'F'), inline=True)
        front_page.add_field(name="Filed Relative", value=discord_dynamic_timestamp(case.created, 'R'), inline=True)
        front_page.add_field(name="Filed By", value=case.nameUserByID(case.plaintiff_id), inline=True)
        front_page.add_field(name="Filed Against", value=case.nameUserByID(case.defense_id), inline=True)
        if case.motion_in_consideration is not None:
            front_page.add_field(name="Motion in Consideration", value=case.motion_in_consideration, inline=False)
            front_page.add_field(name="Voting Ends", value=discord_dynamic_timestamp(case.motion_in_consideration.expiry, 'RT'), inline=False)
        front_page.add_field(name="Guilty Penalty", value=case.describePenalties(case.penalties), inline=False)

        event_page = discord.Embed(title=str(case), description=str(case.id))
        event_page.add_field(name="Event Log Length", value=len(case.event_log), inline=False)
        event_page.add_field(name="Last Event Title", value=case.event_log[-1]["name"])
        event_page.add_field(name="Last Event Desc", value=case.event_log[-1]["desc"])
        event_page.add_field(name="Last Event Datetime", value=discord_dynamic_timestamp(case.event_log[-1]["timestamp"], 'F'))

        class caseinfoview(discord.ui.View):
            @discord.ui.button(label="Main Info", style=discord.ButtonStyle.primary, emoji="📔")
            async def main_info(self, button, interaction: discord.Interaction):
                await interaction.response.edit_message(embed=front_page)

            @discord.ui.button(label="Event Log Info", style=discord.ButtonStyle.primary, emoji="📇")
            async def event_log(self, button, interaction: discord.Interaction):
                await interaction.response.edit_message(embed=event_page)
            
        await ctx.respond(embed=front_page, view=caseinfoview(), ephemeral=ephemeral)


    move = case.create_subgroup("move", "Commands for basic case motions and management.")

    @move.command(name="statement", description="Move to have the court issue an official statement.")
    async def statement_motion(self, ctx: discord.ApplicationContext):
        case = getActiveCase(ctx.author)
        if case is None:
            return await ctx.respond("You do not have an active case.", ephemeral=True)
        if not case.canSubmitMotions(ctx.author):
            return await ctx.respond("You cannot submit a motion in this case.", ephemeral=True)

        statement = await cmui.universalModal(ctx.interaction, "Statement", [discord.ui.InputText(label="Enter Statement", style=discord.InputTextStyle.long, min_length=40, max_length=1024)])
        statement = statement[0].value

        if statement is None:
            return await ctx.respond("You must provide a statement.", ephemeral=True)
        
        embed = discord.Embed(title="Confirm Statement", description=f"Is this the statement you wish to submit?")
        embed.add_field(name="Statement", value=statement)
        msg = await ctx.respond(embed=embed, ephemeral=True)
        
        choice = await cmui.confirmView(msg)

        if choice is None or choice is False:
            return await ctx.respond("Cancelled", ephemeral=True)
        
        motion = await cm.StatementMotion(case).New(ctx.author, statement)

        await ctx.respond(f"Motion `{motion.id}` Submitted.", ephemeral=True)

    @move.command(name="order", description="Move to have the court issue a binding order.")
    async def order_motion(self, ctx: discord.ApplicationContext):
        case = getActiveCase(ctx.author)
        if case is None:
            return await ctx.respond("You do not have an active case.", ephemeral=True)
        if not case.canSubmitMotions(ctx.author):
            return await ctx.respond("You cannot submit a motion in this case.", ephemeral=True)

        new_options = await cmui.universalModal(ctx.interaction, "Court Order", [discord.ui.InputText(label="Name of Order Target", style=discord.InputTextStyle.short),
                   discord.ui.InputText(label="Enter Order Content", style=discord.InputTextStyle.long, min_length=40, max_length=1024)])
        
        embed = discord.Embed(title="Confirm Order", description=f"Is this the statement you wish to submit?")
        embed.add_field(name="The Court Orders: ", value=new_options[0].value, inline=False)
        embed.add_field(name="To Comply With The Following Order: ", value=new_options[1].value, inline=False)
        msg = await ctx.respond(embed=embed, ephemeral=True)
        
        choice = await cmui.confirmView(msg)

        if choice is None or choice is False:
            return await ctx.respond("Cancelled", ephemeral=True)
        
        motion = await cm.OrderMotion(case).New(ctx.author, new_options[0].value, new_options[1].value)

        await ctx.respond(f"Motion `{motion.id}` Submitted.", ephemeral=True)

    evidence = case.create_subgroup(name="evidence", description="Commands for managing evidence in your active case.")

    @evidence.command(name="upload", description="Upload a file as evidence to your active case.")
    async def evidence_upload(self, ctx: discord.ApplicationContext):
        case = getActiveCase(ctx.author)
        if case is None:
            return await ctx.respond("You do not have an active case.", ephemeral=True)
        if not case.canSubmitMotions(ctx.author):
            return await ctx.respond("You cannot submit evidence to this case.", ephemeral=True)
    
        await ctx.respond("Upload the file here. You have 5 minutes.", ephemeral=True)
        try:
            file_message: discord.Message = await self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id, timeout=300)
        except asyncio.TimeoutError:
            return await ctx.respond("You took too long to upload the file.", ephemeral=True)

        if len(file_message.attachments) == 0:
            return await ctx.respond("You must upload a file.", ephemeral=True)
        if len(file_message.attachments) > 1:
            return await ctx.respond("You can only upload one file.", ephemeral=True)
        
        file = file_message.attachments[0]
        if file.size > 8388608*4:
            return await ctx.respond("File size must be less than 32MB.", ephemeral=True)
        
        # give upload progress regularly 
        
        msg = await ctx.respond(f"Processing file {file.filename}...", ephemeral=True)

        file_bytes = await file.read()

        await msg.edit(content=f"Uploading file {file.filename}...", embed=None)

        new_evidence = await case.newEvidence(ctx.author, file.filename, file_bytes)
        await msg.edit(f"Uploaded evidence **{new_evidence.filename}** (`{new_evidence.id}`) to case **{case}** (`{case.id}`)")

    async def evidence_options(ctx: discord.AutocompleteContext):
        case = getActiveCase(ctx.interaction.user)
 
        if case is None:     
            pool = []   
            for case in cm.ACTIVECASES:
                pool.extend(case.evidence)
            # sort based on 'created' attribute
            pool.sort(key=lambda e: e.created, reverse=True)
            return [f"{evidence.filename}: {evidence.id}" for evidence in pool]
        else:
            return [f"{evidence.filename}: {evidence.id}" for evidence in sorted(case.evidence, key = lambda e: e.created, reverse=True)]

    @evidence.command(name="view", description="View a piece of evidence in your active case.")
    @option("evidence_id", str, description="The ID of the evidence to view.", autocomplete=discord.utils.basic_autocomplete(evidence_options))
    @option("ephemeral", bool, description="Whether to send the evidence privately.", default=True)
    async def evidence_view(self, ctx: discord.ApplicationContext, evidence_id: str, ephemeral: bool = True):
        if ":" in evidence_id:
            evidence_id = evidence_id.split(" ")[-1]
        
        case: cm.Case
        file: cm.Evidence

        case, file = cm.getEvidenceByIDGlobal(evidence_id)
        if file is None:
            return await ctx.respond("Invalid evidence ID.", ephemeral=True)
        
        if file.isSealed() and not case.canSubmitMotions(ctx.author):
            # TODO: file.describeSealsEmbed() or something
            return await ctx.respond("You cannot view this evidence, as it has been placed under seal.", ephemeral=True)
        
        response = await ctx.respond(f"Loading evidence...", ephemeral=ephemeral)
    
        file_name, file_bytes = await file.getRawFile()
        embed = discord.Embed(title=f"Viewing Evidence: {file_name}", description=f"**{case}** (`{case.id}`)")
        embed.add_field(name="Evidence ID", value=file.id, inline=False)
        embed.add_field(name="Evidence Filename", value=file.filename, inline=False)
        embed.add_field(name="Filed By", value=case.nameUserByID(file.author), inline=False)
        embed.add_field(name="Filed On", value=discord_dynamic_timestamp(file.created, 'FR'), inline=False)

        await ctx.interaction.edit_original_response(content=None, embed=embed, file=discord.File(file_bytes, file_name))

    jury = discord.SlashCommandGroup("jury", "Jury commands")
    
    async def juror_case_options(ctx: discord.AutocompleteContext):
        return [f"{case}: {case.id}" for case in cm.ACTIVECASES if case.stage == 1 and ctx.interaction.user.id in case.jury_pool_ids]

    @jury.command(name="join", description="Join an active case as a juror.")
    async def jury_join(self, ctx: discord.ApplicationContext, case: discord.Option(str, autocomplete=discord.utils.basic_autocomplete(juror_case_options))):
        case = cm.getCaseByID(case.split(" ")[-1])
        if case is None:
            return await ctx.respond("Invalid case ID.", ephemeral=True)
        if ctx.author.id not in case.jury_invites:
            return await ctx.respond("You have not been invited to this case.", ephemeral=True)
        
        setActiveCase(ctx.author, case)
        await case.addJuror(ctx.author)

        return await ctx.respond(f"Joined case **{case}** (`{case.id}`) as a juror.", ephemeral=True)
    
    @jury.command(name="say", description="Say something privately to the other jurors.")
    async def jury_say(self, ctx: discord.ApplicationContext, message: str):
        case = getActiveCase(ctx.author)
        if case is None:
            return await ctx.respond("You do not have an active case.", ephemeral=True)
        if ctx.author.id not in case.jury_pool_ids:
            return await ctx.respond("You are not a juror in this case.", ephemeral=True)
        
        await case.juror_say(ctx.author, message)
        await ctx.respond("Message sent.", ephemeral=True)

    dbg = discord.SlashCommandGroup("debug", "Debug commands for testing purposes")

    @dbg.command(name='wipecases', description='Wipe all cases from the database.')
    async def wipe_cases(self, ctx: discord.ApplicationContext):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        
        for c in cm.ACTIVECASES:
            await c.closeCase()
        await ctx.respond("Cases wiped.", ephemeral=True)

    # TODO: remove when done debugging
    @dbg.command(name="tickone", description="DEBUG: trigger a tick event on your active case.")
    async def tick_case(self, ctx: discord.ApplicationContext):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        case = getActiveCase(ctx.author)
        if case is None:
            return await ctx.respond("You do not have an active case.", ephemeral=True)
        await case.Tick()
        await ctx.respond("Tick triggered.", ephemeral=True)

    @dbg.command(name='appointjuror', description='Appoint a juror to a case.')
    @option("member", discord.Member, description="The member to appoint as a juror.")
    @option("pseudonym", str, description="The pseudonym to use for the juror.", optional=True)
    async def appoint_juror(self, ctx: discord.ApplicationContext, member: discord.Member, pseudonym: Optional[str] = None):
        case = getActiveCase(ctx.author)
        if not ctx.author.guild_permissions.administrator:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        if case is None:
            return await ctx.respond("You do not have an active case.", ephemeral=True)
        if case.stage != 0:
            return await ctx.respond("This case is not in the jury selection stage.", ephemeral=True)
        if member.id in case.jury_pool_ids:
            return await ctx.respond("This member is already a juror in this case.", ephemeral=True)

        await case.addJuror(member, pseudonym)
        await ctx.respond(f"Appointed {utils.normalUsername(member)} as a juror in this case.", ephemeral=True)

    reports = {}

    report = discord.SlashCommandGroup("report", "Commands for managing reports to server staff")

    @report.command(name="submit", description="Submit your active report.")
    async def submit_report(self, ctx: discord.ApplicationContext):
        if ctx.author.id not in self.reports:
            return await ctx.respond("You do not have an active report.", ephemeral=True)

        report = self.reports[ctx.author.id]
        await report.send()
        del self.reports[ctx.author.id]
        await ctx.respond("Report sent.", ephemeral=True)
    
    @report.command(name="cancel", description="Cancel your active report.")
    async def cancel_report(self, ctx: discord.ApplicationContext):
        if ctx.author.id not in self.reports:
            return await ctx.respond("You do not have an active report.", ephemeral=True)
        
        del self.reports[ctx.author.id]
        await ctx.respond("Report cancelled.", ephemeral=True)

    # add option to report a user by right clicking a message
    @commands.message_command(name="Report Message to Server Staff")
    async def report_message(self, ctx: discord.ApplicationContext, message: discord.Message):
        if ctx.author.id in self.reports:
            self.reports[ctx.author.id].add_message(message)
            await ctx.respond("Message added to report.", ephemeral=True)
        else:
            report = rm.UserReport(self.bot, ctx.author, message.author)
            report.add_message(message)
            await report.send()
            await ctx.respond("Report sent.", ephemeral=True)

    @commands.user_command(name="Report User to Server Staff")
    async def report_user(self, ctx: discord.ApplicationContext, member: discord.Member):
        if ctx.author.id in self.reports:
            return await ctx.respond("You already have an active report. Submit it to start a new one.", ephemeral=True)

        self.reports[ctx.author.id] = rm.UserReport(self.bot, ctx.author, member)
        await ctx.respond("Report started. Select offending messages and hit 'Report Message to Server Staff' to add evidence. Then use /report submit to submit the report.", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        for case in cm.ACTIVECASES:
            if member.id in case.jury_pool_ids:
                log("Case", "CaseManager", f"Removing Juror {utils.normalUsername(member)} from case {case.id} as they left the server.")
                await case.removeJuror(member, "Juror left the server.")
        # for case in cm.ACTIVECASES:
            # if member.id == case.defense_id:
            #     await case.defendantLeave()
            # elif member.id in case.jury_pool_ids:
            #     await case.jurorLeave(member)
            # elif member.id == case.plaintiff_id:
            #     await case.plaintiffLeave()

    @tasks.loop(minutes=15)
    async def CaseManager(self):
        log("Case", "CaseManager", "Doing Periodic Case Manager Loop")
        for case in cm.ACTIVECASES:
            await case.Tick()
        return

def setup(bot):
    bot.add_cog(Justice(bot))
