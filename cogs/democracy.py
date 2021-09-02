# just a template to copy and paste for use in developing cogs in the future

from discord.ext import commands
from cyberkevsecurity import authorize, authorize_sudoer
import discord
import asyncio
from discord.utils import get

C = {}

def time_to_text(length): # TODO: atm it only allows one number and one unit, ie "5h", allow it to split and do multiple units, ie "1h30m"
	days = round(length // (24 * 3600))
	length = length % (24 * 3600)
	hours = round(length // 3600)
	length %= 3600
	minutes = round(length // 60)
	length %= 60
	seconds = round(length)
	txt = ""
	if seconds:  txt = f"{seconds} second{'s' if seconds != 1  else ''}"
	if minutes:   txt = f"{minutes} minute{'s' if minutes != 1 else ''}, " + txt
	if hours:     txt = f"{hours} hour{'s' if hours != 1 else ''}, " + txt
	if days:      txt = f"{days} day{'s' if days != 1 else ''}, " + txt
	return txt.strip(", ")

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
		embed.set_footer(text=f"Vote ends in {time_to_text(C['decidelength'])}")


		message = await channel.send(embed=embed)
		await message.add_reaction("✅")
		await message.add_reaction("❌")

		await ctx.message.add_reaction("🗳")

		await asyncio.sleep(C["decidelength"]*60)

		message = await channel.fetch_message(message.id)  # to update reactions in the cache, we have to fetch a new message obj from the old id

		yes = get(message.reactions, emoji="✅").count
		no = get(message.reactions, emoji="❌").count
		
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