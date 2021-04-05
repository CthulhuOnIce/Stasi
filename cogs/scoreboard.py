# just a template to copy and paste for use in developing cogs in the future
import discord
from discord.ext import commands
import pickle
import datetime

C = {}
SAVE = {}
START = datetime.datetime(2021, 4, 5) # datetime.datetime(2021, 4, 5)

def load():
	global SAVE
	with open("data/scoreboard.p", "rb") as rb:
		SAVE = pickle.loads(rb.read())

def save():
	with open("data/scoreboard.p", "wb+") as wb:
		wb.write(pickle.dumps(SAVE))

def update():
	global SAVE
	old_save = SAVE.copy()
	load()
	for value in old_save:
		if value not in SAVE:
			SAVE[value] = old_save[value]
	save()

try:
	update()
except FileNotFoundError:
	save()


class Scoreboard(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
	
	async def get_potential_invites(self, guild): # GOOD
		ret = []
		for invite in await guild.invites():
			if invite.created_at < START:			continue  # no invites counted past start date
			if invite.inviter.bot:					continue  # no bots
			if not invite.uses:						continue  # skip if never used
			ret.append(invite)
		return ret

	async def update_save(self, guild):  # works
		potentials = await self.get_potential_invites(guild)
		for potential in potentials:
			if not potential.id in SAVE:	SAVE[potential.id] = {}
			SAVE[potential.id]["invited"] = potential.uses
			SAVE[potential.id]["owner"] = potential.inviter.id
		save()

	async def save_only_active(self, guild):  # return SAVE, minus users that aren't in the server
		returnme = SAVE.copy()
		for i in SAVE:
			invite = SAVE[i]
			if not guild.get_member(invite["owner"]):
				returnme.pop(i)
		return returnme

	@commands.Cog.listener()
	async def on_member_join(self, member):
		await self.update_save(member.guild)

	@commands.command(brief="Print top ten on scoreboard.")
	async def scoreboard(self, ctx, inserver:bool = False):
		message = await ctx.send("Generating scoreboard, just one second...")
		global SAVE
		await self.update_save(ctx.guild)
		scores = {}
		for i in (await self.save_only_active(ctx.guild) if inserver else SAVE):
			invite = SAVE[i]
			if invite["owner"] in scores:
				scores[invite["owner"]] += invite["invited"]
			else:
				scores[invite["owner"]] = invite["invited"]
		scores = dict(sorted(scores.items(), key=lambda item: item[1])[::-1][0:10])
		embed=discord.Embed(title="Scoreboard", description="The state of the contest!")
		for i in scores:
			user = await self.bot.fetch_user(i)
			invites = scores[i]
			embed.add_field(name=f"{user.name}#{user.discriminator} ({user.id})", value=f"{invites}", inline=False)
		await message.edit(content="", embed=embed)


def setup(bot, config):
	global C
	C = config
	bot.add_cog(Scoreboard(bot))