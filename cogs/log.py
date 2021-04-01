# just a template to copy and paste for use in developing cogs in the future

from discord.ext import commands
import discord

C = {}
LOGCHANNEL = None

def message_to_embed(message):
	embed=discord.Embed(title=f"\u200b", description=message.content)
	embed.set_author(name=f"{message.author.name}#{message.author.discriminator}", icon_url=message.author.avatar_url_as())
	return embed

def message_to_list(message):
	ret = []
	ret.append(message_to_embed(message))
	for embed in message.embeds:
		ret.append(embed)
	return ret

class Log(commands.Cog):

	def logchannel(self):
		global LOGCHANNEL
		if not LOGCHANNEL:
			LOGCHANNEL = self.bot.get_channel(C['logchannel'])
		return LOGCHANNEL

	def __init__(self, bot):
		self.bot = bot
	
	@commands.Cog.listener()
	async def on_message_delete(self, message):
		await self.logchannel().send("Message deleted.")
		for embed in message_to_list(message):
			await self.logchannel().send(embed=embed)

	@commands.Cog.listener()
	async def on_bulk_message_delete(self, messages):
		await self.logchannel().send("Messages bulk deleted.")
		messages.sort(key=lambda r: r.created_at)
		for message in messages:
			for embed in message_to_list(message):
				await self.logchannel().send(embed=embed)

	@commands.Cog.listener()
	async def on_member_unban(self, guild, user):
		await self.logchannel().send(f"Member unbanned: `{user.name}#{user.discriminator} ({user.id})`")

	@commands.Cog.listener()
	async def on_member_ban(self, guild, user):
		await self.logchannel().send(f"Member banned: `{user.name}#{user.discriminator} ({user.id})`")

def setup(bot, config):
	global C
	C = config
	bot.add_cog(Log(bot))