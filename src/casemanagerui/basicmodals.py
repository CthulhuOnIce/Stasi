import discord
from typing import List

async def universalModal(interaction, title: str, options: List[discord.ui.InputText]):
    modal = discord.ui.Modal(*options, title)
    await interaction.send_modal(modal)
    await modal.wait()
    return options