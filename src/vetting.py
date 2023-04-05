from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks
import asyncio

from . import database as db
from . import config
from . import artificalint as ai

class Verification(commands.Cog):

    verification_editing = discord.SlashCommandGroup("veredit", "Edit the verification process")

    @verification_editing.command(name='questions', description='View the verification questions and their IDs.')
    async def verquestions(self, ctx, ephemeral):
        questions = await db.get_verification_questions()
        if not questions:
            return await ctx.respond("There are no verification questions.", ephemeral=True)
        embed = discord.Embed(title="Verification Questions", description="\n\n".join(f"`{i}`. {question}" for i, question in enumerate(questions)))
        await ctx.respond(embed=embed, ephemeral=ephemeral)

    @verification_editing.command(name='add', description='Add a verification question.')
    async def veradd(self, ctx, question: str):
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        await db.add_verification_question(question)
        await ctx.respond("Question added.", ephemeral=True)
    
    @verification_editing.command(name='del', description='Delete a verification question.')
    async def verdel(self, ctx, index: int):
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        await db.del_verification_question(index)
        await ctx.respond("Question deleted.", ephemeral=True)
    
    @verification_editing.command(name='swap', description='Swap two verification questions.')
    async def verswap(self, ctx, index1: int, index2: int):
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        await db.swap_verification_questions(index1, index2)
        await ctx.respond("Questions swapped.", ephemeral=True)
    
    @verification_editing.command(name='edit', description='Clear all verification questions.')
    async def veredit(self, ctx, index: int, question: str):
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        await db.edit_verification_question(index, question)
        await ctx.respond("Question edited.", ephemeral=True)

    currently_beta_verifying = []

    @slash_command(name='betaverify', description='Test the new AI-based vetting system.')
    async def betaverify(self, ctx):
        if ctx.author.id in self.currently_beta_verifying:
            return await ctx.respond("You are already being verified.", ephemeral=True)
        # reject if the channel isnt a dm
        if ctx.channel == ctx.author.dm_channel:
            return await ctx.respond("Please don't run this command in your DMs.", ephemeral=True)
        

        self.currently_beta_verifying.append(ctx.author.id)
        
        moderator = ai.VettingModerator()
        verdict = await moderator.vet_user(ctx, ctx.author)

        def explain_verdict(verdict):
            if verdict == "left":
                return "SYSTEM: Verdict is LEFT. You are a left-winger."
            elif verdict == "right":
                return "SYSTEM: Verdict is RIGHT. You are a right-winger or your leanings or ambiguous."
            elif verdict == "areject":
                return "SYSTEM: Verdict is AREJECT. You are intentionally frustrating the vetting process."
            elif verdict == "bgtp":
                return "SYSTEM: Verdict is BGTP. You are being overtly offensive."
            else:
                return "SYSTEM: The AI never made a resolution code. Report this to the developers."
            
        embed = discord.Embed(title=f"Verdict: {verdict}", description=explain_verdict(verdict))
        for message in moderator.messages:
            embed.add_field(name=message["role"] if message["role"] != "user" else ctx.author, value=message["content"], inline=False)
        await ctx.respond(embed=embed, ephemeral=False)

        del(moderator)

        self.currently_beta_verifying.remove(ctx.author.id)

    @slash_command(name='asktutor', description='Ask Marxist AI tutor a question. [Answers may be wrong, this is for fun.]')  # TODO: move this where it actually belongs
    async def asktutor(self, ctx, question: str):
        await ctx.interaction.response.defer()
        embed = discord.Embed(title="Question", description=question)
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar.url)
        embed.add_field(name="Answer", value=ai.tutor_question(question))
        await ctx.respond(embed=embed, ephemeral=False)

    currently_verifying = []

    @slash_command(name='verify', description='Verify yourself.')
    async def verify(self, ctx):
        questions = await db.get_verification_questions()
        verified_role = ctx.guild.get_role(config.C["verified_role"])
        unverified_role = ctx.guild.get_role(config.C["unverified_role"])

        if not verified_role or not unverified_role:
            return await ctx.respond("Verification role not found.", ephemeral=True)  # if this happens there's a problem with the configs

        if verified_role in ctx.author.roles:
            if unverified_role in ctx.author.roles:
                await ctx.author.remove_roles(unverified_role)
                return await ctx.respond("You are already verified, but you also had the unverified role. I have removed it for you.", ephemeral=True)
            else:
                return await ctx.respond("You are already verified.", ephemeral=True)
        else:
            if await db.get_prisoner(ctx.author.id):
                return await ctx.respond("You are in prison.", ephemeral=True)

            elif "verification" in await db.get_user(ctx.author.id):
                await ctx.author.add_roles(verified_role)
                if unverified_role in ctx.author.roles:
                    await ctx.author.remove_roles(unverified_role)
                return await ctx.respond("You have already been verified, your role has been automatically re-added.", ephemeral=True)

        if not questions:  # skip
            await ctx.author.remove_roles(unverified_role)
            await ctx.author.add_roles(verified_role)
            await ctx.respond("You have been verified.")
            await db.add_verification(ctx.author.id, [])
            self.currently_verifying.remove(ctx.author.id)
            return

        if ctx.author.id in self.currently_verifying:
            return await ctx.respond("You are already being verified.", ephemeral=True)
        
        self.currently_verifying.append(ctx.author.id)

        qna = []  # [(question, answer), ...]
        channel = ctx.author
        intro_embed = discord.Embed(title="Verification", description="Please answer the following questions to verify yourself.\nYou have 10 minutes to answer each question, though it is not expected for you to use all of this time.\nIf you time out, verification will be cancelled.")

        try:
            msg = await channel.send(embed=intro_embed)
            channel = msg.channel    # this is a hack to get the channel, because at this point `channel == ctx.author` is false and we need it to be true
            await ctx.respond("Check your DMs.")
        except discord.Forbidden:
            channel = ctx.channel
            await ctx.respond("Your DMs are disabled; I will ask you the verification questions in this channel.")
            await channel.send(embed=intro_embed)

        def check(m):
            return m.author == ctx.author and m.channel == channel
        
        len_questions = len(questions)

        await asyncio.sleep(1)

        for i, question in enumerate(questions):
            embed = discord.Embed(title=f"Verification Question #{i+1}/{len_questions}", description=question)
            await channel.send(embed=embed)
            try:
                answer = await self.bot.wait_for("message", check=check, timeout=600)
            except asyncio.TimeoutError:
                await channel.send("You took too long to answer.")
                self.currently_verifying.remove(ctx.author.id)
                return
            qna.append((question, answer.clean_content))
        
        await ctx.author.remove_roles(unverified_role)
        await ctx.author.add_roles(verified_role)
        await db.add_verification(ctx.author.id, qna)
        await channel.send("Thank you for answering the questions. You have been verified.")
        self.currently_verifying.remove(ctx.author.id)
    
    @slash_command(name='bypassverify', description='Allow a user to bypass verification')
    @option('user', discord.Member, description='The user to bypass verification for.')
    async def bypassverify(self, ctx, user: discord.Member):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        await db.add_verification(user.id, ["BYPASSED", f"{ctx.author} ({ctx.author.id}) Bypassed verification"])
        await user.remove_roles(ctx.guild.get_role(config.C["unverified_role"]))
        await user.add_roles(ctx.guild.get_role(config.C["verified_role"]))
        await ctx.respond("User bypassed verification.", ephemeral=True)
    
    @slash_command(name='unverify', description='Remove a user\'s verification record and make them do it again.')
    @option('user', discord.Member, description='The user to unverify.')
    async def unverify(self, ctx, user: discord.Member):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        await db.del_verification(user.id)
        await user.remove_roles(ctx.guild.get_role(config.C["verified_role"]))
        await user.add_roles(ctx.guild.get_role(config.C["unverified_role"]))
        await ctx.respond("User unverified.", ephemeral=True)


    def __init__(self, bot):
        self.bot = bot



def setup(bot):
    bot.add_cog(Verification(bot))
