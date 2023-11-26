import discord

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