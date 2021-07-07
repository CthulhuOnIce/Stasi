from discord.ext import commands
import kevdb as db
import discord
import simplejson as json
from disputils import BotEmbedPaginator
from cyberkevsecurity import authorize, authorize_sudoer

C = {}
LOGCHANNEL = None

def message_to_embed(message):
	embed=discord.Embed(title=f"\u200b", description=message.content)
	embed.set_author(name=f"{message.author.name}#{message.author.discriminator}", icon_url=message.author.avatar_url_as())
	return embed

def message_to_list(message):
	ret = []
	ret.append(message_to_embed(message))
	for embed in message.embeds:
		ret.append(embed)
	return ret

def message_to_json(message):
	attachments = []
	for attachment in message.attachments:
		attachments.append({
			"content_type": attachment.content_type,
			"filename": attachment.filename,
			"size": attachment.size,
			"id": attachment.id,
			"height": attachment.height,
			"width": attachment.width
		})

	embeds = []
	for embed in message.embeds:
		embeds.append(embed.to_dict())

	j = {
		"content": {
			"clean_content": message.clean_content,
			"content": message.content,
			"attachments": attachments,
			"embeds": embeds
		},
		"author": {
			"name": message.author.name,
			"discriminator": message.author.discriminator,
			"id": message.author.id,
			"bot": message.author.bot
		},
		"created_at": message.created_at,
		"edited_at": message.edited_at
	}
	return j

def jsql(d):
	return json.dumps(d, default=str)

def messages_to_json(messages):
	m = []
	for message in messages:
		m.append(message_to_json(message))
	return m

def list_subtract(l1, l2):  # return items that are in l1 but not l2
	diff = []
	for item in l1:
		if not item in l2:
			diff.append(item)
	return diff

def longform_username(user):
	return f"{user.name}#{user.discriminator} ({user.id})"

class Moderation(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	def logchannel(self):
		global LOGCHANNEL
		if not LOGCHANNEL:
			LOGCHANNEL = self.bot.get_channel(C['logchannel'])
		return LOGCHANNEL

	def __init__(self, bot):
		self.bot = bot
	
	@commands.Cog.listener()
	async def on_message_delete(self, message):
		entry = await message.guild.audit_logs(limit=1, action=discord.AuditLogAction.message_delete).flatten()
		entry = entry[0]
		user = entry.user if entry.target == message.author else message.author
		db.audit_log("MESSAGE_DELETE", f"{user.name}#{user.discriminator}", user.id, f"{longform_username(user)} Deleted a message from {longform_username(message.author)}", jsql(message_to_json(message)))
		await self.logchannel().send(f"Message deleted by `{longform_username(user)}`.")
		for embed in message_to_list(message):
			await self.logchannel().send(embed=embed)

	@commands.Cog.listener()
	async def on_bulk_message_delete(self, messages):
		messages.sort(key=lambda r: r.created_at)
		entry = await messages[0].guild.audit_logs(limit=1, action=discord.AuditLogAction.message_bulk_delete).flatten()
		entry = entry[0]
		user = entry.user
		db.audit_log("MESSAGE_BULK_DELETE", f"{user.name}#{user.discriminator}", user.id, f"{longform_username(user)} Deleted {len(messages)} messages.", jsql(messages_to_json(messages)))
		await self.logchannel().send(f"{len(messages)} messages deleted by `{longform_username(user)})`.")
		for message in messages:
			for embed in message_to_list(message):
				await self.logchannel().send(embed=embed)

	@commands.Cog.listener()
	async def on_member_unban(self, guild, user):
		entry = await guild.audit_logs(limit=1, action=discord.AuditLogAction.unban).flatten()
		entry = entry[0]
		reason = ""
		if entry.reason:
			reason = f"\nReason: `{entry.reason}`"
		await self.logchannel().send(f"{longform_username(entry.user)} unbanned: {longform_username(entry.target)}{reason}")
		db.audit_log("UNBAN", f"{entry.user.name}#{entry.user.discriminator}", user.id, f"{entry.user.name}#{entry.user.discriminator} ({entry.user.id}) unbanned: {entry.target.name}#{entry.target.discriminator} ({entry.target.id}){reason}", jsql({"user": entry.user.id, "target":entry.target.id, "reason": entry.reason}))
		db.expunge_ban(user.id)

	@commands.Cog.listener()
	async def on_member_ban(self, guild, user):
		entry = await guild.audit_logs(limit=1, action=discord.AuditLogAction.ban).flatten()
		entry = entry[0]
		reason = ""
		if entry.reason:
			reason = f"\nReason: `{entry.reason}`"
		await self.logchannel().send(f"{longform_username(entry.user)} banned: {longform_username(entry.target)}){reason}")
		db.audit_log("BAN", f"{entry.user.name}#{entry.user.discriminator}", entry.user.id, f"{longform_username(entry.user)} unbanned: {longform_username(entry.target)}{reason}", jsql({"user": entry.user.id, "target":entry.target.id, "reason":entry.reason}))
		db.record_ban(entry.user.id, entry.target.id, entry.reason)
	
	@commands.Cog.listener()
	async def on_member_update(self, before, after):
		if before.roles != after.roles:  # role update
			removed = list_subtract(before.roles, after.roles)
			added = list_subtract(after.roles, before.roles)
			removed_text = f"\nRemoved: {[i.name for i in removed]}" if len(removed) else ""
			added_text = f"\nAdded: {[i.name for i in added]}" if len(added) else ""
			entry = await after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update).flatten()
			entry = entry[0]
			reason = ""
			if entry.reason:
				reason = f"\nReason: `{entry.reason}`"
			db.audit_log("ROLEUPDATE", f"{entry.user.name}#{entry.user.discriminator}", entry.user.id, f"{longform_username(entry.user)} updated roles for {longform_username(entry.target)}{added_text}{removed_text}{reason}", jsql({"added": [role.id for role in added], "removed": [role.id for role in removed], "reason": reason, "target": entry.target.id}))
			await self.logchannel().send(f"{longform_username(entry.user)} updated roles for {longform_username(entry.target)}{added_text}{removed_text}{reason}")
		if before.display_name != after.display_name:  # nickname update
			entry = await after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update).flatten()
			entry = entry[0]
			db.audit_log("NICKNAMEUPDATE", f"{entry.user.name}#{entry.user.discriminator}", entry.user.id, f"{longform_username(entry.user)} changed {longform_username(entry.target)}'s name from `{before.display_name}` to `{after.display_name}`", jsql({"target": entry.target.id, "before": before.display_name, "after":after.display_name}))
			await self.logchannel().send(f"{longform_username(entry.user)} changed {longform_username(entry.target)}'s name from `{before.display_name}` to `{after.display_name}`")

	@commands.Command
	async def fetchban(self, ctx, userid:int):
		user = await self.bot.fetch_user(userid)
		if not authorize(ctx.author, C):
			await ctx.send("You are not authorized to use this command.")
			return
		banEntryDb = db.get_ban(userid)
		if not banEntryDb:
			await ctx.send("Didn't see them get banned, pulling from audit log...")
			banEntry = await ctx.guild.fetch_ban(user)
			if banEntry:
				await ctx.send(banEntry.reason if banEntry.reason else "No reason recorded for ban.")
			else:
				await ctx.send("Could not fetch their ban record.")
			return
		else:
			user = await self.bot.fetch_user(banEntryDb[0])
			admin = await self.bot.fetch_user(banEntryDb[1])
			reason = banEntryDb[2]
			date = banEntryDb[3]
			await ctx.send(f"User: `{longform_username(user)}`\nAdmin: `{longform_username(admin)}`\nTimestamp: `{date}`\nReason: `{reason}`")

	@commands.Command
	async def sql(self, ctx, *, statement:str):
		if not authorize_sudoer(ctx.author, C):
			await ctx.send("Not authorized to use this command!")
			return
		try:
			results = db.sql_raw(statement)[::-1]
			for result in results:
				print("----")
				print(result)
			embeds = []
			embed=discord.Embed(title="SQL Query", description=statement)
			embed.set_author(name=longform_username(ctx.author), icon_url=ctx.author.avatar_url_as(format="png"))
			embeds.append(embed)
			i = 1
			for result in results:
				embed=discord.Embed(title=f"Row {i}", description=str(result)[0:4000])
				embed.set_author(name=longform_username(ctx.author), icon_url=ctx.author.avatar_url_as(format="png"))
				embeds.append(embed)
				i += 1
			paginator = BotEmbedPaginator(ctx, embeds)
			await paginator.run()
		except Exception as e:
			await ctx.send(f"Error: {e}")
			

def setup(bot, config):
	global C
	C = config
	bot.add_cog(Moderation(bot))