import base64
import datetime
import os
import sys

import discord
import asyncio

from . import config


def discord_dynamic_timestamp(timestamp: datetime.datetime, format_style: str = 'f') -> str:
    """
    Converts a datetime object to a Discord dynamic timestamp.

    Args:
        timestamp (datetime.datetime): The datetime object to be converted.
        format_style (str): The format style for the timestamp. Default is 'f'.
            Available format styles:
                - 't': Short time format (e.g., 1:13 PM)
                - 'T': Long time format (e.g., 1:13:00 PM)
                - 'd': Short date format (e.g., 4/18/23)
                - 'D': Long date format (e.g., April 18, 2023)
                - 'f': Short date and time format (e.g., April 18, 2023 at 1:13 PM)
                - 'F': Long date and time format (e.g., Tuesday, April 18, 2023 at 1:13 PM)
                - 'R': Relative time format (e.g., 2 months ago)
                - 'FR': Custom: F and R (e.g., Tuesday, April 18, 2023 at 1:13 PM (2 months ago))
                - 'RF' Custom: R and F (e.g., 2 months ago (Tuesday, April 18, 2023 at 1:13 PM))

    Returns:
        str: The Discord dynamic timestamp string.
    """
    if format_style not in ['t', 'T', 'd', 'D', 'f', 'F', 'R', 'FR', 'RF']:
        raise ValueError("Invalid format style. Please use one of the following: 't', 'T', 'd', 'D', 'f', 'F'")

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)

    # Convert the timezone aware datetime object to Unix timestamp (epoch time)
    epoch = int(timestamp.timestamp())
    
    if format_style == 'FR':
        return f'<t:{epoch}:F> (<t:{epoch}:R>)'
    
    elif format_style == 'RF':
        return f'<t:{epoch}:R> (<t:{epoch}:F>)'
    
    else:
        return f'<t:{epoch}:{format_style}>'

def log(category_broad, category_fine, message, print_message=True, preserve_newlines=False):
    
    if "--debug" in sys.argv or "--verbose" in sys.argv:
        print_message = True
        
    # create timestamp like JAN 6 2021 12:00:00
    os.makedirs("logs", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%b %d %Y %H:%M:%S")
    if not preserve_newlines:
        message = message.replace("\n", " ")
    # clean emojis, special characters
    print_msg = message.encode("latin-1", "replace").decode('latin-1')
    if print_message: print(f"[{timestamp}] [{category_broad.upper()}] [{category_fine.upper()}] {print_msg}")
    with open(f"logs/{category_broad.lower()}.log", "a+", encoding='utf-8') as f:
        f.write(f"[{timestamp}] [{category_fine.upper()}] {message}\n")

def log_user(user):
    return f"{user} ({user.id})"

def lid(object):  # convert the id(object) to base64
    return base64.b64encode(str(id(object)).encode("utf-8")).decode("utf-8")

async def channelDispatch(content: str = None, embed: discord.Embed = None, channel: discord.TextChannel = None):
    try:
        await channel.send(content=content, embed=embed)
    except discord.Forbidden:
        pass

async def channelLog(content: str = None, embed: discord.Embed = None, category: str = None, dry: bool = False):
    bot = config.get_global("bot")
    if category not in config.C["log_channels"]:
        return
    
    channels = []

    if isinstance(config.C["log_channels"][category], list):
        for channel_id in config.C["log_channels"][category]:
            channel = bot.get_channel(channel_id)
            if channel:
                channels.append(channel)

    elif isinstance(config.C["log_channels"][category], int):
        channel = bot.get_channel(config.C["log_channels"][category])
        if channel:
            channels.append(channel)
    
    else:
        return
    
    if not channels:
        return

    if dry:  # can be used for custom behavior or testing
        return channels

    tasks = []
    for channel in channels:
        asyncio.sleep(0.1)
        tasks.append(channelDispatch(content=content, embed=embed, channel=channel))
    
    asyncio.gather(*tasks)
