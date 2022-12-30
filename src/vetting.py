from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks
import asyncio

from . import database as db
from . import config

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name='verquestions', description='View the verification questions and their IDs.')
    @option('ephemeral', bool, description='Whether to send the questions as an ephemeral message or not.', default=True)
    async def verquestions(self, ctx, ephemeral: bool = True):
        questions = await db.get_verification_questions()
        if not questions:
            return await ctx.respond("There are no verification questions.", ephemeral=True)
        embed = discord.Embed(title="Verification Questions", description="\n\n".join(f"`{i}`. {question}" for i, question in enumerate(questions)))
        await ctx.respond(embed=embed, ephemeral=ephemeral)

    @slash_command(name='veradd', description='Add a verification question.')
    @option('question', str, description='The question to add.')
    async def veradd(self, ctx, question: str):
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        await db.add_verification_question(question)
        await ctx.respond("Question added.", ephemeral=True)
    
    @slash_command(name='verdel', description='Delete a verification question.')
    @option('index', int, description='The index of the question to delete.')
    async def verdel(self, ctx, index: int):
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        await db.del_verification_question(index)
        await ctx.respond("Question deleted.", ephemeral=True)
    
    @slash_command(name='verswap', description='Swap two verification questions.')
    @option('index1', int, description='The index of the first question.')
    @option('index2', int, description='The index of the second question.')
    async def verswap(self, ctx, index1: int, index2: int):
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        await db.swap_verification_questions(index1, index2)
        await ctx.respond("Questions swapped.", ephemeral=True)
    
    @slash_command(name='veredit', description='Clear all verification questions.')
    @option('index', int, description='The index of the question to edit.')
    @option('question', str, description='The new question.')
    async def veredit(self, ctx, index: int, question: str):
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        await db.edit_verification_question(index, question)
        await ctx.respond("Question edited.", ephemeral=True)


    currently_verifying = []

    @slash_command(name='verify', description='Verify yourself.')
    async def verify(self, ctx):
        questions = await db.get_verification_questions()
        verified_role = ctx.guild.get_role(config.C["verified_role"])

        if verified_role in ctx.author.roles:
            return await ctx.respond("You are already verified.", ephemeral=True)
        else:
            if await db.get_prisoner(ctx.author.id):
                return await ctx.respond("You are in prison.", ephemeral=True)

            elif "verification" in await db.get_user(ctx.author.id):
                await ctx.author.add_roles(verified_role)
                return await ctx.respond("You have already been verified, your role has been automatically re-added.", ephemeral=True)


        if not verified_role:
            return await ctx.respond("Verification role not found.", ephemeral=True)  # if this happens there's a problem with the config

        if not questions:  # skip
            await ctx.author.add_roles(verified_role)
            await ctx.respond("You have been verified.")
            await db.add_verification(ctx.author.id, [])
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
            await ctx.respond("Check your DMs.", ephemeral=True)
        except discord.Forbidden:
            channel = ctx.channel
            await ctx.respond("Your DMs are disabled; I will ask you the verification questions in this channel.", ephemeral=True)
            await channel.send(embed=intro_embed)

        def check(m):
            return m.author == ctx.author and m.channel == channel
        
        len_questions = len(questions)

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
        
        await ctx.author.add_roles(verified_role)
        await db.add_verification(ctx.author.id, qna)
        await channel.send("Thank you for answering the questions. You have been verified.")
        self.currently_verifying.remove(ctx.author.id)

def setup(bot):
    bot.add_cog(Verification(bot))
