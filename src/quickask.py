import discord

async def bool_choice(ctx: discord.ApplicationContext, question, embed: discord.Embed = None, cancel_option: bool = False):
    class yes_no_view(discord.ui.View):

        def __init__(self):
            super().__init__()
            self.value = None

        @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, emoji="✅")
        async def yes_click(self, button, interaction: discord.Interaction):
            for child in self.children:
                if child is not self:
                    child.disabled = True
            self.value = True
            await interaction.response.edit_message(view=self)
            self.stop()

        @discord.ui.button(label="No", style=discord.ButtonStyle.red, emoji="❌")
        async def no_click(self, button, interaction: discord.Interaction):
            for child in self.children:
                if child is not self:
                    child.disabled = True
            self.value = False
            await interaction.response.edit_message(view=self)
            self.stop()
    
    view = yes_no_view()
    
    msg = await ctx.respond(question, embed=embed, view=view, ephemeral=True)
    
    await view.wait()
    return view.value
