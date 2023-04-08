from typing import Optional

import discord
from discord import option, slash_command
from discord.ext import commands, tasks
import asyncio

from . import database as db
from . import config
from . import artificalint as ai
from . import security

class Verification(commands.Cog):

    currently_beta_verifying = []

    @slash_command(name='betaverify', description='Test the new AI-based vetting system.')
    async def betaverify(self, ctx):
        if ctx.author.id in self.currently_beta_verifying:
            return await ctx.respond("You are already being verified.", ephemeral=True)
        # reject if the channel isnt a dm
        if ctx.channel == ctx.author.dm_channel:
            return await ctx.respond("Please don't run this command in your DMs.", ephemeral=True)
        
        await ctx.interaction.response.defer()

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
            elif verdict == "bgtprb":
                return "SYSTEM: Verdict is BGTPRB. You are being overtly offensive."
            else:
                return "SYSTEM: The AI never made a resolution code. Report this to the developers."
            
        embed = discord.Embed(title=f"Verdict: {verdict}", description=explain_verdict(verdict))
        for message in moderator.messages.copy():
            if message["role"] == "system": continue
            if len(message["content"]) > 1024:
                message["content"] = message["content"][:1021] + "..."
            embed.add_field(name=message["role"] if message["role"] != "user" else ctx.author, value=message["content"], inline=False)
        await ctx.respond(embed=embed, ephemeral=False)

        self.currently_beta_verifying.remove(ctx.author.id)
    

    @slash_command(name='asktutor', description='Ask Marxist AI tutor a question. [Answers may be wrong, this is for fun.]')  # TODO: move this where it actually belongs
    async def asktutor(self, ctx, question: str):
        await ctx.interaction.response.defer()
        embed = discord.Embed(title="Question", description=question)
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar.url)
        answer = await ai.tutor_question(question)
        if len(answer) <= 1024:
            embed.add_field(name="Answer", value=answer, inline=False)
        elif len(answer) <= 2048:  # TODO: this can be done more efficiently
            embed.add_field(name="Answer", value=answer[:1024], inline=False)
            embed.add_field(name="Answer (cont.)", value=answer[1024:], inline=False)
        else:
            embed.add_field(name="Answer", value=answer[:1024], inline=False)
            embed.add_field(name="Answer (cont.)", value=answer[1024:2048], inline=False)
            embed.add_field(name="Answer (cont. cont.)", value=answer[2048:], inline=False)
        await ctx.respond(embed=embed, ephemeral=False)

    currently_ai_verifying = {}

    @slash_command(name='verify', description='Verify yourself!')
    async def verify(self, ctx):

        # cant have several lines of questioning at once
        if str(ctx.author.id) in self.currently_beta_verifying:
            return await ctx.respond("You are already being verified.", ephemeral=True)

        # reject if the channel isnt a dm
        if not ctx.guild:
            return await ctx.respond("Please don't run this command in your DMs.", ephemeral=True)

        await ctx.interaction.response.defer()  # running this here because we have to run some stuff before creating mod
        
        unverified_role = ctx.guild.get_role(config.C["unverified_role"])

        # if already verified, just skip
        user = await db.get_user(ctx.author.id)
        if "verification_verdict" in user and user["verification_verdict"]:
            if unverified_role in ctx.author.roles:
                await ctx.author.remove_roles(unverified_role)
            return await ctx.respond("You are already verified.", ephemeral=True)

        # officially start verifying        
        moderator = ai.VettingModerator()

        self.currently_ai_verifying[f"{ctx.author.id}"] = moderator

        verdict = await moderator.vet_user(ctx, ctx.author)

        # sanitize log to not include system messages
        moderator.messages = [message for message in moderator.messages if message["role"] != "system"]

        # log to channel
        log_channel = None
        if "log_channel" in config.C and config.C["log_channel"]:
            log_channel = ctx.guild.get_channel(config.C["log_channel"])
            if not log_channel:
                log_channel = ctx.channel
            if log_channel:
                embed = ai.build_verification_embed(ctx.author, moderator.messages, verdict)
                await log_channel.send(embed=embed)

        # decide which role to use for verification
        verification_role = None
        if verdict == "left":
            verification_role = ctx.guild.get_role(config.C["leftwing_role"])
        elif verdict == "right" or verdict == "bgtprb":
            verification_role = ctx.guild.get_role(config.C["rightwing_role"])
        elif verdict == "areject" or verdict == "error" or verdict == False:
            return self.currently_ai_verifying.pop(f"{ctx.author.id}")
        
        # dm user informing them of their verdict
        embed = discord.Embed(title="✅ Verification Approved", description="Welcome to the server!", color=discord.Color.green())
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar.url)
        await ctx.author.send(embed=embed)

        # update roles
        if verification_role:
            await ctx.author.add_roles(verification_role)
            if unverified_role in ctx.author.roles:
                await ctx.author.remove_roles(unverified_role) # only log the verif in the db if they passed somehow
            await db.add_verification(ctx.author.id, moderator.messages, verdict)  # internal db

        self.currently_ai_verifying.pop(f"{ctx.author.id}")
    


    verifying = discord.SlashCommandGroup("verifying", "Interact with users who are still being verified.")


    @verifying.command(name='yank', description='Yank a currently verifying users\' interview progress.')
    @option('user', discord.Member, description='The user to yank progress for.')
    @option('ephemeral', bool, description='Whether to send the message as an ephemeral message or not.', default=True)
    async def verifyyank(self, ctx, user: discord.Member, ephemeral=True):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        if str(user.id) in self.currently_ai_verifying:
            moderator = self.currently_ai_verifying[f"{user.id}"]
            embed = ai.build_verification_embed(user, [message for message in moderator.messages if message["role"] != "system"], "yanked")
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            await ctx.respond("User is not being verified.", ephemeral=ephemeral)

    @verifying.command(name='list', description='See who is verifying currently.')
    async def verifying(self, ctx):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        if len(self.currently_ai_verifying) == 0:
            return await ctx.respond("No one is currently being verified.", ephemeral=True)
        
        # start building embed
        embed = discord.Embed(title="Currently Verifying", description="These users are currently being verified.")
        
        remove = []  # garbage collector for dangling moderator objects w/o a user to interview anymore

        # sort
        for user_id in self.currently_ai_verifying:
            moderator = self.currently_ai_verifying[user_id]
            if not moderator.user or moderator.user not in ctx.guild.members:
                remove.append(user_id)
                continue
            embed.add_field(name=moderator.user.name, value=f"Messages: {len(moderator.messages)}", inline=False)
        
        # remove dangling moderators, garbage collector should take care of the rest
        for user_id in remove:
            self.currently_ai_verifying.pop(user_id)
        
        if len(remove):
            embed.set_footer(text=f"{len(remove)} users were removed from the list because they left the server, or otherwise have dangling verification")

        await ctx.respond(embed=embed, ephemeral=True)

    @slash_command(name='bypassverify', description='Allow a user to bypass verification')
    @option('user', discord.Member, description='The user to bypass verification for.')
    async def bypassverify(self, ctx, user: discord.Member):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        await db.add_verification(user.id, [{"role": "system", "content": f"Bypassed verification by {ctx.author}"}], "left")
        await user.remove_roles(ctx.guild.get_role(config.C["unverified_role"]))
        await user.add_roles(ctx.guild.get_role(config.C["leftwing_role"]))
        await ctx.respond("User bypassed verification.", ephemeral=True)
    
    @slash_command(name='unverify', description='Remove a user\'s verification record and make them do it again.')
    @option('user', discord.Member, description='The user to unverify.')
    async def unverify(self, ctx, user: discord.Member):
        if not ctx.author.guild_permissions.manage_roles:
            return await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        await db.del_verification(user.id)

        left = ctx.guild.get_role(config.C["leftwing_role"])
        right = ctx.guild.get_role(config.C["rightwing_role"])

        if left in ctx.author.roles:
            await user.remove_roles(left)
        if right in ctx.author.roles:
            await user.remove_roles(right)

        await user.add_roles(ctx.guild.get_role(config.C["unverified_role"]))
        await ctx.respond("User unverified.", ephemeral=True)


    def __init__(self, bot):
        self.bot = bot



def setup(bot):
    bot.add_cog(Verification(bot))
