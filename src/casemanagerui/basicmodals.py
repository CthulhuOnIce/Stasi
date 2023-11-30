import discord
from typing import List

async def universalModal(interaction, title: str, options: List[discord.ui.InputText]) -> List[discord.ui.InputText]:
    modal = discord.ui.Modal(*options, title=title)
    
    async def callback(interaction: discord.Interaction):
        await interaction.response.defer()
        return
    
    modal.callback = callback

    if getattr(interaction, "send_modal", None):
        await interaction.send_modal(modal)
    elif getattr(interaction, "response", None):
        await interaction.response.send_modal(modal)
        
    await modal.wait()

    return options