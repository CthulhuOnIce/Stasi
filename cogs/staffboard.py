# just a template to copy and paste for use in developing cogs in the future

import discord
from discord.ext import commands
import pickle
import dill


C = {}
BOARDS = []
BOARD = None

class Staff_Board(commands.Cog):
	def generate_new_board(self, guild):
		roles = []
		for role in C["authorized"]:
			roleobj = guild.get_role(role)
			if roleobj:
				roles.append(roleobj)
		embed = discord.Embed(title="Staff Board", description="Every Staff Member", color=0xbd6500)
		for role in roles:
			users = []
			for member in role.members:
				if member.top_role != role:
					continue
				users.append(f" - {member.mention} ({member.name}#{member.discriminator})")
			if len(users):	
				embed.add_field(name=f"{role.name}", value="\n".join(users), inline=False)
		return embed

	@commands.command(brief="Print the staff board.")
	async def staffboard(self, ctx):
		await ctx.send(embed=self.generate_new_board(ctx.guild))

def setup(bot, config):
	global C
	C = config
	bot.add_cog(Staff_Board(bot))