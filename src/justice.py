from typing import Optional

import motor  # doing this locally instead of in database.py for greater modularity
import datetime

import discord
from discord import option, slash_command
from discord.ext import commands, tasks

from . import database as db
from . import config
from . import utils

"""
case = {
    "case_id": "Red-Rebel-98",
    "plaintiff_id": int,
    "plaintiff_is_prosecutor": 0,
    "defense_ids": [int, int, int],
    "pentalty": {
        "penalty_code": "ban",
        "expiry": timestamp
    },
    "guilty": None, # true, false, None
    "filed_date": datetime,
    "filed_date_utc": utc_int,
    "jury_pool": [int, int, int],
    "jury_pool_anonymization": {
        user_id_int: "Nickname"
    },
    "judgement_day": None,  # or datetime
    "votes": {
        juror_id: None, True, False
    },
    "event_log": [
        {
            event_id: "something_happened"
            name: "Something happened"
            author_id: 000  #
            desc: "Someone did something!"
            timestamp: datetime
            datetime_utc: int

        }
    ],
    "juror_chat_log": [
        {"id": int, "name": str, "content": int, "datetime": int}
    ],
}
"""

client = db.client
create_connection = db.create_connection

class Case:
    
    def json(self):
          return {
            "case_id": self.case_id,
            "plaintiff_id": self.plaintiff_id,
            "plaintiff_is_prosecutor": self.plaintiff_is_prosecutor,
            "defense_ids": self.defense
          }

    async def select_jurors(self):
        return
    
    async def build_new_case(self, plaintiff, defense_ids, penalty, jury_size=7):
        return
    
    async def save(self):
        db = await create_connection("cases")
        await db.insert_one(self.json(), upsert=True)

    def __init__():
        return

class NewCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name='')

    @slash_command(name='simonsays', description='Repeat what Simon says.')
    @option('text', str, description='The text to repeat')
    async def player_info(self, ctx, text:str):
        await ctx.respond("Simon says " + text, ephemeral=True)

    @commands.user_command(name="Print Username")  # create a user command for the supplied guilds
    async def player_information_click(self, ctx, member: discord.Member):  # user commands return the member
        await ctx.respond(f"Hello {member.display_name}!")  # respond with the member's display name

    @commands.Cog.listener()
    async def on_message(self, message):
        return

def setup(bot):
    bot.add_cog(NewCog(bot))
