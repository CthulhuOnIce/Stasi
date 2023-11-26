import discord

async def confirmView(msg: discord.Message):
    class confirmView(discord.ui.View):
            
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self.value = None

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
    view = confirmView()
    await msg.edit(view=view)
    await view.wait()
    return view.value