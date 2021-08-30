# just a template to copy and paste for use in developing cogs in the future

from discord.ext import commands
from cyberkevsecurity import authorize, authorize_sudoer
import discord
import asyncio

C = {}

class Democracy(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.command(brief="Hold a vote to public opinion")
	async def addvote(self, ctx, *, explan:str):
		if not authorize(ctx.author, C):
			return await ctx.send("⚠ Access Denied")
		channel = ctx.guild.get_channel(C["votechannel"])

		embed = discord.Embed(title="Vote", description=explan)
		embed.add_field(name="Proposal Made By", value=f"{ctx.author.mention} ({ctx.author.name}#{ctx.author.discriminator})", inline=False)
		
		message = await channel.send(embed=embed)
		await message.add_reaction("✅")
		await message.add_reaction("❌")

		await asyncio.sleep(C["decidelength"])

		yes = 0
		no = 0
		for reaction in message.reactions:
			if reaction.emoji == "✅":	yes += 1
			if reaction.emoji == "❌":	no += 1
		
		if yes > no:
			await message.reply(f"{ctx.author.mention}: This vote passed! ({yes}Y/{no}N)")
		elif no > yes:
			await message.reply(f"{ctx.author.mention}: This vote failed! ({yes}Y/{no}N)")
		else:
			await message.reply(f"{ctx.author.mention}: This vote was a draw! ({yes}Y/{no}N)")
		
			

def setup(bot, config):
	global C
	C = config
	bot.add_cog(Democracy(bot))