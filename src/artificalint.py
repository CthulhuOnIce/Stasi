import openai
from . import config
from typing import List
import discord
import asyncio

openai.api_key = config.C["openai"]["key"]

def make_chatgpt_request(messages: List[dict]):
    return openai.ChatCompletion.create(
  model="gpt-3.5-turbo",
  messages=messages
)["choices"][0]

def build_verification_embed(user, messages, verdict):
    embed = discord.Embed(title=f"Verdict: {verdict}", description="Vetting completed.")
    if user:
        embed.set_author(name=user, icon_url=user.avatar.url)
    if verdict == "bgtprb":
        embed.set_footer(text="User is being overtly offensive, exercise caution.")
    elif verdict == "yanked":
        embed.set_footer(text="Interview still in progres.")
    # fill out embed
    for message in messages:
        if len(message["content"]) > 1024:
            message["content"] = message["content"][:1021] + "..."
        embed.add_field(name=message["role"], value=message["content"], inline=False)
    return embed

class VettingModerator:

    user: None

    def generate_response(self):
        response = make_chatgpt_request(self.messages)
        self.messages.append({"role": "assistant", "content": response["message"]["content"]})
        return response["message"]["content"]

    async def vet_user(self, ctx, user):

        self.user = user

        def verdict_check(message):
            message = message.upper()
            if "[LEFT]" in message:
                return "left"
            elif "[RIGHT]" in message:
                return "right"
            elif "[AREJECT]" in message:
                return "areject"
            elif "[BGTPRB]" in message:
                return "bgtprb"
            else:
                return False
            
        self.generate_response()
        try:
            await user.send(self.messages[-1]["content"])
        except discord.Forbidden:
            await ctx.respond("I cannot send messages to you. Please enable DMs from server members and try again.", ephemeral=True)
            return "areject"
    
        await ctx.respond("Check your DMs", ephemeral=True)
        
        while not verdict_check(self.messages[-1]["content"]) and len(self.messages) < 26:
            try:
                message = await ctx.bot.wait_for("message", check=lambda m: m.author == user and not m.guild, timeout=60*20)  # 20 minutes to answer
                self.messages.append({"role": "user", "content": message.clean_content})
            except asyncio.TimeoutError:
                await user.send("SYSTEM: You have timed out (20 minutes). Please try again later.")
                return "areject"
        
            await user.send(self.generate_response())
        
        verdict = verdict_check(self.messages[-1]["content"])

        return verdict 

    def __init__(self):
        self.messages = [{"role": "system", "content": config.C["openai"]["vetting_prompt"]},
            {"role": "user", "content": "[START VETTING]"}].copy()
        self.vetting = True
        

def tutor_question(question):
    return make_chatgpt_request([{"role": "system", "content": config.C["openai"]["tutor_prompt"]}, {"role": "user", "content": question}])["message"]["content"]

            