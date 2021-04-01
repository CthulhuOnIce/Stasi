# just a template to copy and paste for use in developing cogs in the future

from discord.ext import commands

C = {}

class CogName(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.command(brief="Test")
	async def command(self, ctx):
		await ctx.send("Woah!")

def setup(bot, config):
	global C
	C = config
	bot.add_cog(CogName(bot))