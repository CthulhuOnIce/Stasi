from typing import TYPE_CHECKING

import discord

from ..stasilogging import discord_dynamic_timestamp
from ..utils import twemojiPNG

if TYPE_CHECKING:
    from ..casemanager import Motion
    

async def confirmView(msg: discord.Message, cancel_option: bool = False) -> bool:
    
    """This function takes a message, edits it to have a confirm view (yes or no), and returns the value of the view.

    Args:
        msg (discord.Message): The message.
        cancel_option (bool, optional): Whether or not to have a cancel option. Defaults to False. If Cancelled, returns None.

    Returns:
        bool: The value of the view, True or False. If Cancelled, returns None.
    """
    class confirmView(discord.ui.View):

            @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, emoji="✅")
            async def yes_click(self, button, interaction: discord.Interaction):
                for child in self.children:
                    child.disabled = True
                self.value = True
                await msg.edit(view=self)
                await interaction.response.defer()
                self.stop()

            @discord.ui.button(label="No", style=discord.ButtonStyle.red, emoji="❎")
            async def no_click(self, button, interaction: discord.Interaction):
                for child in self.children:
                    child.disabled = True
                self.value = False
                await msg.edit(view=self)
                await interaction.response.defer()
                self.stop()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, emoji="🚫")
            async def cancel_click(self, button, interaction: discord.Interaction):
                for child in self.children:
                    child.disabled = True
                self.value = None
                await msg.edit(view=self)
                await interaction.response.defer()
                self.stop()

            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                if not cancel_option:
                    self.remove_item(self.children[2])
                self.value = None
            
    view = confirmView()
    await msg.edit(view=view)
    await view.wait()
    return view.value

async def voteView(ctx: discord.ApplicationContext, motion: Motion):

    embed = discord.Embed(title="Vote", description=f"**{motion.id}**", color=discord.Color.blurple())

    embed.add_field(name="Proposed By", value=motion.Case.nameUserByID(motion.author_id), inline=False)
    embed.add_field(name="Proposed On", value=discord_dynamic_timestamp(motion.created, 'FR'), inline=False)

    yes_votes = ""
    for voter in motion.votes["Yes"]:
        yes_votes += f"- {motion.Case.nameUserByID(voter)}\n"

    no_votes = ""
    for voter in motion.votes["No"]:
        no_votes += f"- {motion.Case.nameUserByID(voter)}\n"

    if yes_votes:
        embed.add_field(name=f"Yes Votes ({len(motion.votes['Yes'])})", value=yes_votes, inline=True)
    if no_votes:
        embed.add_field(name=f"No Votes ({len(motion.votes['No'])})", value=no_votes, inline=True)

    embed.add_field(name="Voting Ends", value=discord_dynamic_timestamp(motion.expiry, 'FR'), inline=False)

    embed.set_author(name=f"{motion.Case} ({motion.Case.id})", icon_url=twemojiPNG.ballot)

    msg = await ctx.respond(embed=embed, ephemeral=True)

    class voteView(discord.ui.View):

            @discord.ui.button(label="Pass", style=discord.ButtonStyle.green, emoji="✅")
            async def yes_click(self, button, interaction: discord.Interaction):
                for child in self.children:
                    child.disabled = True
                self.value = True
                await ctx.interaction.edit_original_response(view=self)
                await interaction.response.defer()
                self.stop()

            @discord.ui.button(label="Reject", style=discord.ButtonStyle.red, emoji="❎")
            async def no_click(self, button, interaction: discord.Interaction):
                for child in self.children:
                    child.disabled = True
                self.value = False
                await ctx.interaction.edit_original_response(view=self)
                await interaction.response.defer()
                self.stop()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, emoji="🚫")
            async def cancel_click(self, button, interaction: discord.Interaction):
                for child in self.children:
                    child.disabled = True
                self.value = None
                await ctx.interaction.edit_original_response(view=self)
                await interaction.response.defer()
                self.stop()

            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self.value = None

    view = voteView()
    await ctx.interaction.edit_original_response(view=view)
    await view.wait()
    first_vote = view.value

    if first_vote is None:
        await ctx.respond(content = "❌ Voting Cancelled.", ephemeral=True)
        return None

    vote_str = "Pass" if first_vote else "Reject"

    embed = discord.Embed(title=f"Cast Vote For {motion.id}", description=f"Confirm Vote: **{vote_str}**", color=discord.Color.blurple())

    msg = await ctx.respond(embed=embed, ephemeral=True)

    view = await confirmView(msg)

    if view:
        return first_vote
    else:
        return False