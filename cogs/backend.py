# just a template to copy and paste for use in developing cogs in the future

from discord.ext import commands
from cyberkevsecurity import authorize_sudoer
import os
import sys
import subprocess
import git
import asyncio

C = {}

class Backend(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.command(brief="Updates the bot.")
	async def update(self, ctx):
		if not authorize_sudoer(ctx.author, C):
			return await ctx.send("⚠ Access Denied!")

		URL = "https://github.com/cthulhuonice/CyberKev"

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
		await message.edit(content="💤 Restarting...")
		os.execv(sys.executable, "main.py")
	
def setup(bot, config):
	global C
	C = config
	bot.add_cog(Backend(bot))