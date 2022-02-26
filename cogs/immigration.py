# just a template to copy and paste for use in developing cogs in the future
import discord
from discord.ext import commands
import kevdb as db
import cyberkevsecurity as s

C = {}

class Immigration(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.command(brief="Verify yourself!")
	async def verify(self, ctx):
		verified = ctx.guild.get_role(C["verifiedrole"])
		rwverified = ctx.guild.get_role(C["rightwingverifiedrole"])
		unverified = ctx.guild.get_role(C["unverifiedrole"])
		
		if verified in ctx.author.roles or rwverified in ctx.author.roles:
			await ctx.message.reply("You're already verified!")
			return
		
		leftist = ctx.guild.get_role(C["ideology"]["leftist"])
		rightist = ctx.guild.get_role(C["ideology"]["rightist"])

		# convert to two bools to clean up the code a little
		left = leftist in ctx.author.roles
		right = rightist in ctx.author.roles

		if (not left and not right):
			await ctx.message.reply(f"Please get roles first! Specifically one or more of the following roles:\n{leftist.mention}, {rightist.mention}")
			return
		
		questions = ["How did you find this server?", "Why do you want to join this server?", "How would you describe yourself politically?"]  # can have up to 5
		qa = {}  # dictionary with questions mapped to answers

		channel = None
		try:
			await ctx.author.send("Starting verification... Please use a bit of detail in your responses (>15 chars).")
			channel = ctx.author
			await ctx.message.add_reaction("📩")
		except:  # dms turned off, don't bother telling them to turn them off, just do the process in the channel
			channel = ctx.channel

		for question in questions:

			await channel.send(question)

			def check(m):
				if m.author == ctx.author:
					if len(m.clean_content) < 15:
						return False
					if channel == ctx.author:
						return isinstance(m.channel, discord.channel.DMChannel)
					else:
						return m.channel == channel
				else:
					return False

			msg = await self.bot.wait_for("message", check=check)

			qa[question] = msg.clean_content

		# interview done, one more question
		await channel.send("Do you agree to follow the rules? (Type 'Yes' or 'No')")
		def check(m):
			if m.author == ctx.author:
				if channel == ctx.author:
					return isinstance(m.channel, discord.channel.DMChannel)
				else:
					return m.channel == channel
			else:
				return False

		msg = await self.bot.wait_for("message", check=check)
		r = msg.clean_content.upper().replace("!", "").replace(".", "").replace("?", "")  # ignore capitalization and punctuation

		if r in ["YEAH", "YES", "YESSIR", "YUP", "YEA", "YE", "Y"]:  # it specifically asks "yes" or "no" but some people are stupid
			await channel.send("You have passed verification, please wait...")
			dbqa = [(None, None), (None, None), (None, None), (None, None), (None, None)]
			i = 0
			for q in qa:
				a = qa[q]
				dbqa[i] = (q, a)
				i += 1
			
			ideology = None
			if left and right:	ideology = "CENTRIST"
			if left:			ideology = "LEFTIST"
			if right:			ideology = "RIGHTIST"

			db.verify_user(ctx.author.id, ideology, dbqa)
			await ctx.author.remove_roles(unverified)

			if right or (left and right):
				await ctx.author.add_roles(rightist)
			else:
				await ctx.author.add_roles(leftist)
			
			await ctx.message.reply(f"Verified as {ideology.lower()}.")

			await channel.send("Welcome to the server!")	

		else:
			await ctx.author.kick(reason="Failed verification")
			await ctx.message.reply("Kicked for non-agreement to the rules.")
		
	@commands.command(brief="[Admins Only] See a User's response to the verification questions.")
	async def passport(self, ctx, user:discord.User):
		if not s.authorize(ctx.author, C):
			await ctx.message.reply("You are not authorized to use this command!")
			return
		
		results = db.fetch_verification(user.id)
		if not results:
			await ctx.message.reply("No verification record found for this user!")
			return
		
		color = 0xef2929 if results[2] == "LEFTIST" else 0x729fcf
		embed=discord.Embed(title="Verification Record", description=f"Verification Record for {user.mention} ({user.id})")
		embed.add_field(name="Timestamp", value=str(results[1]), inline=False)
		embed.add_field(name="Ideology", value=results[2], inline=False)
		scan = [3, 5, 7, 9, 11]
		for i in scan:
			if results[i]:
				embed.add_field(name=results[i], value=results[i+1], inline=False)
		try:
			await ctx.author.send(embed=embed)
		except:
			await ctx.send(embed=embed)



def setup(bot, config):
	global C
	C = config
	bot.add_cog(Immigration(bot))