# just a template to copy and paste for use in developing cogs in the future

from discord.ext import commands
from cyberkevsecurity import authorize_sudoer
import os
import sys
import subprocess
import git
import asyncio
import discord

C = {}

class Backend(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.command(brief="See system info.")
	async def sysinfo(self, ctx):
		repo = git.Repo('.')
		embed = discord.Embed(title="Sysinfo", description="Currently running environment info.")
		embed.add_field(name="Current Git Revision", value=repo.head.commit.hexsha, inline=False)
		embed.add_field(name="Committed Date", value=repo.head.commit.committed_datetime, inline=False)
		embed.add_field(name="Authored By", value=repo.head.commit.author, inline=False)
		embed.add_field(name="Description", value=repo.head.commit.message, inline=False)
		embed.set_footer(text=C["repourl"])
		await ctx.send(embed=embed)

	@commands.command(brief="Updates the bot.")
	async def update(self, ctx):
		if not authorize_sudoer(ctx.author, C):
			return await ctx.send("⚠ Access Denied!")

		URL = C["repourl"]

		message = await ctx.send("💾 Cloning update...")
		p = subprocess.Popen(["git", "clone", URL, "staged-update"])
		p.wait()
		await message.edit(content="🔁 Copying config...")
		p = subprocess.Popen(["cp", "config.yml", "staged-update/config.yml"])
		p.wait()
		await message.edit(content="📀 Installing and updating modules...")
		p = subprocess.Popen([sys.executable, "-m", "pip", "install", "--upgrade", "-r", "staged-update/requirements.txt"])
		p.wait()
		await message.edit(content="🧪 Testing update...")
		process = subprocess.Popen([sys.executable, "staged-update/main.py"])
		await asyncio.sleep(10)
		if process.returncode:
			if process.returncode == 0:
				await message.edit(content="✅ No Crashes Detected!")
			else:
				await message.edit(content="❎ Code Crashed, update terminated.")
				p = subprocess.Popen(["rm", "-rf", "staged-update"])
				p.wait()
				await message.edit(content="⚠ Update failed: Code unexecutable.")
				return
		else:
			await message.edit(content="✅ No Crashes Detected!")
		process.kill()
		await message.edit(content="🧹 Cleaning up...")
		p = subprocess.Popen(["rm", "-rf", "staged-update"])
		p.wait()
		await message.edit(content="🔃 Applying update...")
		subprocess.Popen(["git", "pull"])
		p.wait()
		await asyncio.sleep(3)  # do what its gotta do
		await message.edit(content="💤 Restarting...")
		os.execv(sys.executable, ['python'] + sys.argv)
	
def setup(bot, config):
	global C
	C = config
	bot.add_cog(Backend(bot))