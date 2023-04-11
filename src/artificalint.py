import openai
from . import config
from typing import List
import discord
import asyncio
from .logging import log, log_user

openai.api_key = config.C["openai"]["key"]

async def make_chatgpt_request(messages: List[dict]):
    res = await openai.ChatCompletion.acreate(
  model="gpt-3.5-turbo",
  messages=messages
)
    return res["choices"][0]

def build_verification_embed(user, messages, verdict):
    messages = messages.copy()
    embed = discord.Embed(title=f"Verdict: {verdict}", description="Vetting completed." if verdict != "yanked" else "Vetting in progress.")
    if user:
        embed.set_author(name=user, icon_url=user.avatar.url if user.avatar else None)
    if verdict == "bgtprb":
        embed.set_footer(text="User is being overtly offensive, exercise caution.")
    elif verdict == "yanked":
        embed.set_footer(text="Interview still in progress.")
    # fill out embed, i
    for message in messages:
        if len(message["content"]) > 1024:
            message["content"] = message["content"][:1021] + "..."
        embed.add_field(name=message["role"], value=message["content"], inline=False)
    return embed

class VettingModerator:

    user: None

    async def generate_response(self):
        response = await make_chatgpt_request(self.messages)
        self.messages.append({"role": "assistant", "content": response["message"]["content"]})
        return response["message"]["content"]

    def verdict_check(self, message):
        message = message.upper()
        if "LEFT]" in message:
            return "left"
        elif "RIGHT]" in message:
            return "right"
        elif "AREJECT]" in message:
            return "areject"
        elif "BGTPRB]" in message:
            return "bgtprb"
        else:
            return False

    async def vet_user(self, ctx, user):

        log("aivetting", "startvetting", f"{id(self)} starting vetting for {log_user(user)}")

        self.user = user
            
        await self.generate_response()
        try:
            await user.send(self.messages[-1]["content"])
        except discord.Forbidden:
            log("aivetting", "dmfail", f"Failed to send DM to {log_user(user)}")
            await ctx.respond("I cannot send messages to you. Please enable DMs from server members and try again.", ephemeral=True)
            return "areject"
    
        await ctx.respond("Check your DMs", ephemeral=True)
        
        while not self.verdict_check(self.messages[-1]["content"]) and len(self.messages) < 26:
            try:
                message = await ctx.bot.wait_for("message", check=lambda m: m.author == user and not m.guild, timeout=60*20)  # 20 minutes to answer
                self.messages.append({"role": "user", "content": message.clean_content})
                log("aivetting", "readmessage", f"{id(self)} Read message from {log_user(user)}: {message.clean_content}")
            except asyncio.TimeoutError:
                log("aivetting", "timeout", f"User {log_user(user)} timed out.")
                await user.send("SYSTEM: You have timed out (20 minutes). Please try again later.")
                return "areject"
        
            response = await self.generate_response()
            await user.send(response)
        
        verdict = self.verdict_check(self.messages[-1]["content"])

        return verdict 

    def __init__(self):
        log("aivetting", "newmod", f"New moderator {id(self)} created.")
        self.messages = [{"role": "system", "content": config.C["openai"]["vetting_prompt"]},
            {"role": "user", "content": "[START VETTING]"}].copy()
        self.vetting = True

    def __del__(self):
        log("aivetting", "delmod", f"Moderator {id(self)} deleted.")
        

async def tutor_question(question):
    res = await make_chatgpt_request([{"role": "system", "content": config.C["openai"]["tutor_prompt"]}, {"role": "user", "content": question}])
    return res["message"]["content"]


class BetaVettingModerator(VettingModerator):

    async def one_off_assistant(self, system, user):
        messages = [{"role": "system", "content": system}, {"role": "assistant", "content": user}]
        res = await make_chatgpt_request(messages)
        return res["message"]["content"]

    async def one_off(self, system, user):
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        res = await make_chatgpt_request(messages)
        return res["message"]["content"]

    async def generate_response(self):
        log("aivetting", "betaairesponse", f"Beta AI {id(self)} Generating response...")
        response = await make_chatgpt_request(self.messages)
        response = response["message"]["content"]

        if not self.verdict_check(response):  # if there is no resolution code, check if the ai just forgot to include one
            prompt = "Evaluate the message given. If it seems like the user has made a final decision regarding someone else's ideology, respond with \"[END]\" If the user is not sure yet, or the interview is otherwise ongoing, do not respond with the code."
            one_off_response = await self.one_off(prompt, response)
            if "[end]" in one_off_response.lower():
                log("aivetting", "aicorrection", f"AI {id(self)} forgot to include a resolution code. Message: {response} Prompting it to try again. (User: {log_user(self.user)}")
                self.messages.append({"role": "system", "content": "Now end the interview, remember to include a resolution code in your message."})
                return await self.generate_response()

        self.messages.append({"role": "assistant", "content": response})
        log("aivetting", "betaairesponse", f"Beta AI {id(self)} Generated response: {response}")
        return response