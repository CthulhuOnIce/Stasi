import discord
from . import config
from .casemanager import Case

class UserReport:

    def __init__(self, bot, reporter, member, description: str = None):
        self.bot = bot
        self.reporter = reporter
        self.member = member
        self.description = description
        self.messages = []
    
    def add_message(self, message):
        self.messages.append(message)

    async def send(self):
        embed = discord.Embed(title="New Report", description=f"Reported by {Case.normalUsername(None, self.reporter)} ({self.reporter.id})")
        embed.add_field(name="Reported user", value=f"{Case.normalUsername(None, self.member)} ({self.member.id})")
        embed.add_field(name="Description", value=self.description)
        embed.add_field(name="Messages", value="\n".join([f"[Jump to message]({msg.jump_url})" for msg in self.messages]), inline=False)
        channel = self.bot.get_channel(config.C["log_channel"])
        msg = await channel.send(embed=embed)
        self.id = msg.id
        return msg
