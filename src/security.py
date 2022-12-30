import discord
from . import database as db
from . import config

def is_sudoer(member: discord.Member):
    return member.id in config.C["sudoers"]
