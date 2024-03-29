from __future__ import annotations
from typing import TYPE_CHECKING
import random

import discord

from ..stasilogging import discord_dynamic_timestamp
from ..utils import twemojiPNG, trees, gems, flowers, birds, space, stones, cities, colors

if TYPE_CHECKING:
    from ..casemanager import Motion, Case
    

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

async def voteView(ctx: discord.ApplicationContext, motion: "Motion"):

    embed = discord.Embed(title="Vote", description=f"**{motion.id}**", color=discord.Color.blurple())

    embed.add_field(name="Proposed By", value=motion.Case.nameUserByID(motion.author_id), inline=False)
    embed.add_field(name="Proposed On", value=discord_dynamic_timestamp(motion.created, 'FR'), inline=False)

    yes_votes = ""
    for voter in motion.votes["Yes"]:
        yes_votes += f"- {motion.Case.nameUserByID(voter, False)}\n"

    no_votes = ""
    for voter in motion.votes["No"]:
        no_votes += f"- {motion.Case.nameUserByID(voter, False)}\n"

    if yes_votes:
        embed.add_field(name=f"Yes Votes ({len(motion.votes['Yes'])})", value=yes_votes, inline=True)
    if no_votes:
        embed.add_field(name=f"No Votes ({len(motion.votes['No'])})", value=no_votes, inline=True)

    undecided = []
    for juror in motion.Case.jury_pool_ids:
        if juror not in motion.votes["Yes"] and juror not in motion.votes["No"]:
            undecided.append(motion.Case.nameUserByID(juror, False))
    
    if undecided:
        embed.add_field(name=f"Undecided ({len(undecided)})", value="\n".join(undecided), inline=False)

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
    
async def caseInfoView(ctx: discord.ApplicationContext, case: "Case"):
        
    # Main case summary
    front_page = discord.Embed(title=str(case), description=str(case.id))
    front_page.add_field(name="Current Status", value=case.status, inline=False)
    front_page.add_field(name="Filed Datetime", value=discord_dynamic_timestamp(case.created, 'F'), inline=True)
    front_page.add_field(name="Filed Relative", value=discord_dynamic_timestamp(case.created, 'R'), inline=True)
    front_page.add_field(name="Filed By", value=case.nameUserByID(case.prosecutor_id), inline=True)
    front_page.add_field(name="Filed Against", value=case.nameUserByID(case.defense_id), inline=True)
    if case.motion_in_consideration is not None:
        front_page.add_field(name="Motion in Consideration", value=case.motion_in_consideration, inline=False)
        front_page.add_field(name="Voting Ends", value=discord_dynamic_timestamp(case.motion_in_consideration.expiry, 'RF'), inline=False)
    front_page.add_field(name="Guilty Penalty", value=case.describePenalties(case.penalties), inline=False)

    jurors = ""
    for juror in case.jury_pool_ids:
        jurors += f"- {case.nameUserByID(juror, False)}\n"
    
    if jurors:
        front_page.add_field(name=f"Jurors ({len(case.jury_pool_ids)})", value=jurors, inline=False)


    # event log summary
    event_page = discord.Embed(title=str(case), description=str(case.id))
    event_page.add_field(name="Event Log Length", value=len(case.event_log), inline=False)
    event_page.add_field(name="Last Event Title", value=case.event_log[-1]["name"])
    event_page.add_field(name="Last Event Desc", value=case.event_log[-1]["desc"])
    event_page.add_field(name="Last Event Datetime", value=discord_dynamic_timestamp(case.event_log[-1]["timestamp"], 'FR'))

    # motion in consideration summary
    motion_in_consideration_page = discord.Embed(title=str(case), description=str(case.id))
    if case.motion_in_consideration is not None:
        motion_in_consideration_page.add_field(name="Motion ID", value=case.motion_in_consideration.id, inline=False)
        motion_in_consideration_page.add_field(name="Motion Author", value=case.nameUserByID(case.motion_in_consideration.author_id), inline=False)
        motion_in_consideration_page.add_field(name="Motion Created", value=discord_dynamic_timestamp(case.motion_in_consideration.created, 'FR'), inline=False)
        motion_in_consideration_page.add_field(name="Motion Expiry", value=discord_dynamic_timestamp(case.motion_in_consideration.expiry, 'FR'), inline=False)

        yes_votes = ""
        for voter in case.motion_in_consideration.votes["Yes"]:
            yes_votes += f"- {case.nameUserByID(voter, False)}\n"
        if yes_votes:
            motion_in_consideration_page.add_field(name=f"Yes Votes ({len(case.motion_in_consideration.votes['Yes'])})", value=yes_votes, inline=True)

        no_votes = ""
        for voter in case.motion_in_consideration.votes["No"]:
            no_votes += f"- {case.nameUserByID(voter, False)}\n"
        if no_votes:
            motion_in_consideration_page.add_field(name=f"No Votes ({len(case.motion_in_consideration.votes['No'])})", value=no_votes, inline=True)

        undecided = ""
        undecided_count = 0
        for juror in case.jury_pool_ids:
            if juror not in case.motion_in_consideration.votes["Yes"] and juror not in case.motion_in_consideration.votes["No"]:
                undecided_count += 1
                undecided += f"- {case.nameUserByID(juror, False)}\n"
        if undecided:
            motion_in_consideration_page.add_field(name=f"Undecided ({undecided_count})", value=undecided, inline=False)



    class caseinfoview(discord.ui.View):
        @discord.ui.button(label="Main Info", style=discord.ButtonStyle.primary, emoji="📔")
        async def main_info(self, button, interaction: discord.Interaction):
            await interaction.response.edit_message(embed=front_page)

        @discord.ui.button(label="Event Log Info", style=discord.ButtonStyle.primary, emoji="📇")
        async def event_log(self, button, interaction: discord.Interaction):
            await interaction.response.edit_message(embed=event_page)
        
        @discord.ui.button(label="Current Motion Info", style=discord.ButtonStyle.primary, emoji="🗳️")
        async def motion_in_consideration(self, button, interaction: discord.Interaction):
            await interaction.response.edit_message(embed=motion_in_consideration_page)
        
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            if not case.motion_in_consideration:
                self.remove_item(self.children[2])
        
    await ctx.respond(embed=front_page, view=caseinfoview(), ephemeral=True)

async def jurorNameView(ctx: discord.ApplicationContext, case: "Case"):

    desc =  "If you want to be in a jury, but don't want to be publicly known, you can use a pseudonym.\n"
    desc += "If you choose this option, you must remember to use commands in DMs with the bot to avoid leaking your identity.\n"
    desc += "It is not against the rules to reveal your identity, but your name cannot be changed or removed in the case file.\n"
    desc += "\nWould you like to use a pseudonym?"

    class firstView(discord.ui.View):

        @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, emoji="✅")
        async def yes_click(self, button, interaction: discord.Interaction):
            for child in self.children:
                child.disabled = True
            self.value = True
            await ctx.interaction.edit_original_response(view=self)
            await interaction.response.defer()
            self.stop()

        @discord.ui.button(label="No", style=discord.ButtonStyle.red, emoji="❎")
        async def no_click(self, button, interaction: discord.Interaction):
            for child in self.children:
                child.disabled = True
            self.value = False
            await ctx.interaction.edit_original_response(view=self)
            await interaction.response.defer()
            self.stop()

        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.value = None
    
    view = firstView()
    await ctx.interaction.edit_original_response(content=desc, view=view)
    await view.wait()
    pseudonym = view.value

    if not pseudonym:
        return None

    def pseudonymEmbed(pseudonym):
        embed = discord.Embed(title=f"Juror Pseudonym", description=f"You may be known as this for the case as:", color=discord.Color.blurple())
        embed.add_field(name="Pseudonym", value=pseudonym, inline=False)
        embed.set_author(name=f"{case} ({case.id})", icon_url=twemojiPNG.label)
        return embed
    
    all_names = trees + gems + flowers + birds + space + stones + cities + colors

    def generatePseudonym(source: list = None):
        if not source:
            source = all_names
        while True:
            pseudonym = f"Juror {random.choice(source).title()}"
            for user in case.anonymization:
                if pseudonym == case.anonymization[user]:
                    continue
            return pseudonym
    

    class generatePseudonymView(discord.ui.View):
            
            async def redraw(self, source: list = None):
                pseudonym = generatePseudonym(source)
                self.value = pseudonym
                embed = pseudonymEmbed(pseudonym)
                await ctx.interaction.edit_original_response(content=None, embed=embed, view=self)
            
            @discord.ui.button(label="Regenerate", style=discord.ButtonStyle.primary, emoji="🔀",row=2)
            async def generate(self, button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.redraw()

            @discord.ui.button(label="Trees", style=discord.ButtonStyle.green, emoji="🌲")
            async def generate_tree(self, button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.redraw(trees)
            
            @discord.ui.button(label="Gems", style=discord.ButtonStyle.green, emoji="💎")
            async def generate_gem(self, button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.redraw(gems)
            
            @discord.ui.button(label="Flowers", style=discord.ButtonStyle.green, emoji="🌸")
            async def generate_flower(self, button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.redraw(flowers)
            
            @discord.ui.button(label="Birds", style=discord.ButtonStyle.green, emoji="🐦")
            async def generate_bird(self, button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.redraw(birds)

            @discord.ui.button(label="Space", style=discord.ButtonStyle.green, emoji="🌌", row=1)
            async def generate_space(self, button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.redraw(space)
            
            @discord.ui.button(label="Stones", style=discord.ButtonStyle.green, emoji="🪨", row=1)
            async def generate_stone(self, button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.redraw(stones)
            
            @discord.ui.button(label="Cities", style=discord.ButtonStyle.green, emoji="🏙️", row=1)
            async def generate_city(self, button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.redraw(cities)
            
            @discord.ui.button(label="Colors", style=discord.ButtonStyle.green, emoji="🎨", row=1)
            async def generate_color(self, button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.redraw(colors)
            
    
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, emoji="🚫", row=2)
            async def cancel(self, button, interaction: discord.Interaction):
                await interaction.response.defer()
                for child in self.children:
                    child.disabled = True
                await ctx.interaction.edit_original_response(view=self)
                self.value = None
                self.stop()

            @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="✅", row=2)
            async def accept(self, button, interaction: discord.Interaction):
                await interaction.response.defer()
                for child in self.children:
                    child.disabled = True
                await ctx.interaction.edit_original_response(view=self)
                self.stop()
    
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self.value = None

    view = generatePseudonymView()
    await view.redraw()
    await view.wait()
    pseudonym = view.value

    if not pseudonym:
        return None
    
    return pseudonym

