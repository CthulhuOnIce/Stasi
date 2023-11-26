import discord
from .penalties import *

async def editPenalties(ctx, penalties: List[Penalty] = []):

    msg = await ctx.send("Loading...")

    class editPenaltyView(discord.ui.View):
        def embed(self):
            embed = discord.Embed(title="Edit Penalties", color=discord.Color.blurple())
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url)
            return embed

        def __init__(self):
            selected_penalty_index = 0



