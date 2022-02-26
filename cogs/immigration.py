# just a template to copy and paste for use in developing cogs in the future

from discord.ext import commands
import kevdb as db

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
			await ctx.author.send("Starting verification...")
			channel = ctx.author
		except:  # dms turned off, don't bother telling them to turn them off, just do the process in the channel
			channel = ctx.channel

		for question in questions:

			await channel.send(question)

			def check(m):
				return m.author == ctx.author and m.channel == channel and len(m.clean_content) > 12

			msg = await bot.wait_for("message", check=check)

			qa[question] = msg.clean_content

		# interview done, one more question
		await channel.send("Do you agree to follow the rules? (Type 'Yes' or 'No')")
		def check(m):
			return m.author == ctx.author and m.channel == channel

		msg = await bot.wait_for("message", check=check)
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

		else:
			await ctx.author.kick(reason="Failed verification")



def setup(bot, config):
	global C
	C = config
	bot.add_cog(Immigration(bot))