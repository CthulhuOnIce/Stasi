from discord.ext import commands
import kevdb as db
import discord
import simplejson as json
from disputils import BotEmbedPaginator
from cyberkevsecurity import authorize, authorize_sudoer
from tqdm import tqdm

C = {}
LOGCHANNEL = None

def message_to_embed(message):
	embed = discord.Embed(title='\u200b', description=message.content)
	embed.set_author(name=f"{message.author.name}#{message.author.discriminator}", icon_url=message.author.avatar_url_as())
	return embed

def message_to_list(message):
	ret = [message_to_embed(message)]
	for embed in message.embeds:
		ret.append(embed)
	return ret

def message_to_json(message):
	attachments = [{
			"content_type": attachment.content_type,
			"filename": attachment.filename,
			"size": attachment.size,
			"id": attachment.id,
			"height": attachment.height,
			"width": attachment.width
		} for attachment in message.attachments]
	embeds = [embed.to_dict() for embed in message.embeds]
	return {
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

def jsql(d):
	return json.dumps(d, default=str)

def messages_to_json(messages):
	return [message_to_json(message) for message in messages]

def list_subtract(l1, l2):  # return items that are in l1 but not l2
	return [item for item in l1 if item not in l2]

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
		db.audit_log("MESSAGEDELETE", f"{user.name}#{user.discriminator}", user.id, f"{longform_username(user)} Deleted a message from {longform_username(message.author)}", jsql(message_to_json(message)))
		await self.logchannel().send(f"Message deleted by `{longform_username(user)}`.")
		for embed in message_to_list(message):
			await self.logchannel().send(embed=embed)

	@commands.Cog.listener()
	async def on_bulk_message_delete(self, messages):
		messages.sort(key=lambda r: r.created_at)
		entry = await messages[0].guild.audit_logs(limit=1, action=discord.AuditLogAction.message_bulk_delete).flatten()
		entry = entry[0]
		user = entry.user
		db.audit_log("MESSAGEBULKDELETE", f"{user.name}#{user.discriminator}", user.id, f"{longform_username(user)} Deleted {len(messages)} messages.", jsql(messages_to_json(messages)))
		await self.logchannel().send(f"{len(messages)} messages deleted by `{longform_username(user)})`.")
		for message in messages:
			for embed in message_to_list(message):
				await self.logchannel().send(embed=embed)

	@commands.Cog.listener()
	async def on_member_unban(self, guild, user):
		entry = await guild.audit_logs(limit=1, action=discord.AuditLogAction.unban).flatten()
		entry = entry[0]
		reason = f"\nReason: `{entry.reason}`" if entry.reason else ""
		db.audit_log("UNBAN", f"{entry.user.name}#{entry.user.discriminator}", user.id, f"{entry.user.name}#{entry.user.discriminator} ({entry.user.id}) unbanned: {entry.target.name}#{entry.target.discriminator} ({entry.target.id}){reason}", jsql({"user": entry.user.id, "target":entry.target.id, "reason": entry.reason}))
		db.expunge_ban(user.id)

		embed = discord.Embed(
		    title='Member Unbanned',
		    description=
		    f"{longform_username(entry.user)} unbanned {longform_username(entry.target)}",
		)
		embed.set_author(name=longform_username(entry.user), icon_url=entry.user.avatar_url_as(format="png"))
		if entry.reason:	embed.add_field(name="Reason", value=entry.reason, inline=False)
		await self.logchannel().send(embed=embed)

	@commands.Cog.listener()
	async def on_member_ban(self, guild, user):
		entry = await guild.audit_logs(limit=1, action=discord.AuditLogAction.ban).flatten()
		entry = entry[0]
		reason = f"\nReason: `{entry.reason}`" if entry.reason else ""
		db.audit_log("BAN", f"{entry.user.name}#{entry.user.discriminator}", entry.user.id, f"{longform_username(entry.user)} banned: {longform_username(entry.target)}{reason}", jsql({"user": entry.user.id, "target":entry.target.id, "reason":entry.reason}))
		db.record_ban(entry.user.id, entry.target.id, entry.reason)

		embed = discord.Embed(
		    title='Member Banned',
		    description=
		    f"{longform_username(entry.user)} banned {longform_username(entry.target)}",
		)
		embed.set_author(name=longform_username(entry.user), icon_url=entry.user.avatar_url_as(format="png"))
		if entry.reason:	embed.add_field(name="Reason", value=entry.reason)
		await self.logchannel().send(embed=embed)
	
	@commands.Cog.listener()
	async def on_member_kick(self, guild, user):
		entry = await guild.audit_logs(limit=1, action=discord.AuditLogAction.kick).flatten()
		entry = entry[0]
		reason = f"\nReason: `{entry.reason}`" if entry.reason else ""
		db.audit_log("KICK", f"{entry.user.name}#{entry.user.discriminator}", entry.user.id, f"{longform_username(entry.user)} kicked: {longform_username(entry.target)}{reason}", jsql({"user": entry.user.id, "target":entry.target.id, "reason":entry.reason}))

		embed = discord.Embed(
		    title='Member Kicked',
		    description=
		    f"{longform_username(entry.user)} kicked {longform_username(entry.target)}",
		)
		embed.set_author(name=longform_username(entry.user), icon_url=entry.user.avatar_url_as(format="png"))
		if entry.reason:	embed.add_field(name="Reason", value=entry.reason)
		await self.logchannel().send(embed=embed)
	
	@commands.Cog.listener()
	async def on_member_update(self, before, after):
		if before.roles != after.roles:  # role update
			removed = list_subtract(before.roles, after.roles)
			added = list_subtract(after.roles, before.roles)
			removed_text = f"\nRemoved: {[i.name for i in removed]}" if len(removed) else ""
			added_text = f"\nAdded: {[i.name for i in added]}" if len(added) else ""
			entry = await after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update).flatten()
			entry = entry[0]
			reason = f"\nReason: `{entry.reason}`" if entry.reason else ""
			db.audit_log("ROLEUPDATE", f"{entry.user.name}#{entry.user.discriminator}", entry.user.id, f"{longform_username(entry.user)} updated roles for {longform_username(entry.target)}{added_text}{removed_text}{reason}", jsql({"added": [role.id for role in added], "removed": [role.id for role in removed], "reason": reason, "target": entry.target.id}))

			embed = discord.Embed(
			    title='Role Update',
			    description=
			    f"{longform_username(entry.user)} updated roles for {longform_username(entry.target)}",
			)
			embed.set_author(name=longform_username(entry.user), icon_url=entry.user.avatar_url_as(format="png"))
			if len(added):		embed.add_field(name="Added", value=str([i.name for i in added]), inline=False)
			if len(removed):	embed.add_field(name="Removed", value=str([i.name for i in removed]), inline=False)
			if entry.reason:	embed.add_field(name="Reason", value=entry.reason)
			await self.logchannel().send(embed=embed)

		if before.display_name != after.display_name:  # nickname update
			entry = await after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update).flatten()
			entry = entry[0]

			db.audit_log("NICKNAMEUPDATE", f"{entry.user.name}#{entry.user.discriminator}", entry.user.id, f"{longform_username(entry.user)} changed {longform_username(entry.target)}'s name from `{before.display_name}` to `{after.display_name}`", jsql({"target": entry.target.id, "before": before.display_name, "after":after.display_name}))

			embed = discord.Embed(
			    title='Nickname Update',
			    description=
			    f"{longform_username(entry.user)} changed {longform_username(entry.target)}'s nickname",
			)
			embed.set_author(name=longform_username(entry.user), icon_url=entry.user.avatar_url_as(format="png"))
			embed.add_field(name="Before", value=before.display_name, inline=False)
			embed.add_field(name="After", value=after.display_name, inline=False)
			await self.logchannel().send(embed=embed)

	@commands.Cog.listener()
	async def on_message_edit(self, before, after):
		if before.clean_content != after.clean_content:  # changed actual text

			user = after.author

			db.audit_log("MESSAGEEDIT", f"{user.name}#{user.discriminator}", user.id, f"{longform_username(user)} edited a message from `{before.clean_content}` to `{after.clean_content}`", jsql({"target": user.id, "before": before.clean_content, "after":after.clean_content}))

			embed = discord.Embed(
			    title='Message Edit',
			    description=f"{longform_username(user)} edited a message.",
			)
			embed.set_author(name=longform_username(user), icon_url=user.avatar_url_as(format="png"))
			embed.add_field(name="Before", value=before.clean_content, inline=False)
			embed.add_field(name="After", value=after.clean_content, inline=False)
			await self.logchannel().send(embed=embed)

	@commands.command()
	async def fetchban(self, ctx, userid:int):
		if not authorize(ctx.author, C):
			await ctx.send("You are not authorized to use this command.")
			return

		# try to get ban from db
		banEntryDb = db.get_ban(userid)

		# get profile
		getuser = self.bot.get_user(userid)
		user = getuser or await self.bot.fetch_user(userid)
		if not user:
			await ctx.send("❎ User not found!")
			return

		# create embed
		embed = discord.Embed(title='Ban Entry', description=longform_username(user))
		embed.set_author(name=longform_username(user), icon_url=user.avatar_url_as(format="png"))

		if not banEntryDb:
			try:
				banEntry = await ctx.guild.fetch_ban(user)
				if banEntry:
					embed.add_field(
					    name="Reason", value=banEntry.reason or "No reason recorded for ban.")
			except discord.errors.NotFound:
				await ctx.send("❎ Could not fetch their ban record.")
				return
		else:
			getadmin = self.bot.get_user(banEntryDb[1])
			admin = getadmin or await self.bot.fetch_user(banEntryDb[1])
			reason = banEntryDb[2]
			date = banEntryDb[3]
			embed.add_field(name="Admin", value=longform_username(admin) if admin else f"User no longer exists: {banEntryDb[1]}", inline=False)
			embed.add_field(name="Timestamp", value=date, inline=False)
			embed.add_field(
			    name="Reason", value=reason or "No reason recorded.", inline=False)
		await ctx.send(embed=embed)

	@commands.command()
	async def fixledger(self, ctx):
		# if bot goes inactive and people are unbanned or banned for another reason,
		# clear the now obsolete data
		if not authorize(ctx.author, C):
			await ctx.send("Not authorized to use this command!")
			return
		found = 0
		bans = db.get_all_bans()
		for entry in bans:
			banEntry = await ctx.guild.fetch_ban(entry[0])
			if not banEntry or banEntry.reason != entry[2]:
				db.expunge_ban(entry[0])
				found += 1
		await ctx.send(f"Cleared {found} of {len(bans)}.")
	
	@commands.command()
	async def fetchuser(self, ctx, uid:int):
		if not authorize(ctx.author, C):
			await ctx.send("Not authorized to use this command!")
			return
		user = await self.bot.fetch_user(uid)
		embed=discord.Embed(title=f"{user.name}#{user.discriminator}", description="User Info")
		embed.set_author(name=longform_username(user), icon_url=user.avatar_url_as(format="png"))
		await ctx.send(embed=embed)

	@commands.command()
	async def al(self, ctx, *, mod:str=""):
		if not authorize_sudoer(ctx.author, C):
			await ctx.send("Not authorized to use this command!")
			return
		try:
			formatted = f" WHERE {mod}" if mod else ""
			results = db.sql_raw(f"SELECT * FROM 'auditlog'{formatted}")[::-1][0:1000]

			embeds = []

			embed = discord.Embed(
			    title="Auditlog Report", description=mod or "No modifiers")
			embed.add_field(name="SQL Query", value=f"SELECT * FROM 'auditlog'{formatted}", inline=False)
			embed.set_author(name=longform_username(ctx.author), icon_url=ctx.author.avatar_url_as(format="png"))
			embeds.append(embed)

			actorcache = {}  # speeds up processing by not fetching every actor every time

			i = 1
			for result in results:
				action = result[0]
				if result[2] not in actorcache:
					getuser = self.bot.get_user(result[2])
					# speed up processing by trying to get their user profile from mutual servers (faster) before using fetch_user (slower, rate limited)
					actorcache[result[2]] = getuser or await self.bot.fetch_user(result[2])
				actor = actorcache[result[2]]
				desc = result[3]
				desc_raw = json.loads(result[4])
				timestamp = result[5]
				embed=discord.Embed(title=action, description=desc)
				embed.add_field(name="Description (Raw)", value=json.dumps(desc_raw, indent=". ")[0:1000], inline=False)
				embed.add_field(name="Timestamp", value=timestamp, inline=False)
				embed.set_author(name=longform_username(actor), icon_url=actor.avatar_url_as(format="png"))
				embeds.append(embed)

				i += 1
			paginator = BotEmbedPaginator(ctx, embeds)
			await paginator.run()
		except Exception as e:
			await ctx.send(f'Error: {e}')
			
	@commands.command()
	async def sql(self, ctx, *, statement:str):  # this command is incapable of making db changes, but it's still probably not a good idea to not require sudo
		if not authorize_sudoer(ctx.author, C):
			await ctx.send("Not authorized to use this command!")
			return
		try:
			results = db.sql_raw(statement)[::-1]
			embeds = []
			embed=discord.Embed(title="SQL Query", description=statement)
			embed.set_author(name=longform_username(ctx.author), icon_url=ctx.author.avatar_url_as(format="png"))
			embeds.append(embed)
			for i, result in enumerate(results, start=1):
				embed=discord.Embed(title=f"Row {i}", description="\n------\n".join(map(str, result))[0:4000])
				embed.set_author(name=longform_username(ctx.author), icon_url=ctx.author.avatar_url_as(format="png"))
				embeds.append(embed)
			paginator = BotEmbedPaginator(ctx, embeds)
			await paginator.run()
		except Exception as e:
			await ctx.send(f'Error: {e}')

	@commands.command()
	async def wsql(self, ctx, *, statement:str):  # this command ***is capable*** of making db changes
		if not authorize_sudoer(ctx.author, C):
			await ctx.send("Not authorized to use this command!")
			return
		try:
			results = db.sql_wraw(statement)[::-1]
			embeds = []
			embed=discord.Embed(title="SQL Query", description=statement)
			embed.set_author(name=longform_username(ctx.author), icon_url=ctx.author.avatar_url_as(format="png"))
			embeds.append(embed)
			for i, result in enumerate(results, start=1):
				embed=discord.Embed(title=f"Row {i}", description="\n------\n".join(map(str, result))[0:4000])
				embed.set_author(name=longform_username(ctx.author), icon_url=ctx.author.avatar_url_as(format="png"))
				embeds.append(embed)
			paginator = BotEmbedPaginator(ctx, embeds)
			await paginator.run()
		except Exception as e:
			await ctx.send(f'Error: {e}')

	@commands.command(brief="Warns a user.")
	async def warn(self, ctx, user:discord.Member, *, reason:str):
		if not authorize(ctx.author, C):
			await ctx.send("You aren't authorized to use this command.")
			return
		db.create_warn(user.id, ctx.author.id, reason)
		await ctx.send(f"Warned {user.mention}: `{reason}`.")

	@commands.command(brief="Deletes a warn by ID")
	async def delwarn(self, ctx, *, warnid:str):
		warnid = warnid.replace(" ", "-")  # makes it considerably more mobile friendly
		if not authorize(ctx.author, C):
			await ctx.send("You aren't authorized to use this command.")
			return
		if not db.get_warn(warnid):
			await ctx.send("No warn found with this ID.")
			return
		db.delete_warn(warnid)
		await ctx.send(f"Deleted warn {warnid}.")

	@commands.command(brief="Shows warns for a user.")
	async def warns(self, ctx, user:discord.User = None):
		if not user:	user = ctx.author
		if not authorize(ctx.author, C) and ctx.author != user:
			await ctx.send("You aren't authorized to use this command.")
			return
		try:
			warns = db.get_warns(user.id)[::-1]
		except Exception as E:
			await ctx.send(f"ERROR: {E}")
		embeds = []
		embed=discord.Embed(title="Warnings", description=f"{longform_username(user)}'s Warnings")
		embed.set_author(name=longform_username(ctx.author), icon_url=ctx.author.avatar_url_as(format="png"))
		embeds.append(embed)
		for warn in warns:

			# assign values to variables for readability

			admin = self.bot.get_user(warn[1])
			admin = admin or await self.bot.fetch_user(warn[1])
			reason = warn[2]
			timestamp = warn[3]
			warnid = warn[4]

			# create embed
			embed=discord.Embed(title=f"Warning From {longform_username(admin)}", description=reason)
			embed.set_author(name=longform_username(admin), icon_url=admin.avatar_url_as(format="png"))
			embed.add_field(name="Timestamp", value=str(timestamp), inline=False)
			embed.add_field(name="ID", value=warnid, inline=False)

			embeds.append(embed)

		paginator = BotEmbedPaginator(ctx, embeds)
		await paginator.run()

	@commands.command(brief="Alias for warns")
	async def warnings(self, ctx, user:discord.User=None):
		await self.warns(ctx, user)
	
	@commands.command(brief="Bans a user.")
	@commands.has_permissions(manage_roles=True, ban_members=True)
	async def ban(self, ctx, user:discord.User, *, reason:str=None):
		admin = ctx.author
		member = ctx.guild.get_member(user.id) if user in ctx.guild.members else None
		if member:
			if member.top_role > admin.top_role:
				await ctx.send("You can't ban someone with higher permissions than you.")
				return
		if user == admin:
			await ctx.send("You can't ban yourself.")
			return
		await ctx.guild.ban(user, reason=f"Banned by {longform_username(admin)}: {reason if reason else 'No reason specified'}", delete_message_days=0)
		embed=discord.Embed(title=f"Banned", description=f"{longform_username(user)} banned by {longform_username(admin)}: {reason if reason else 'No reason specified'}")
		embed.set_author(name=longform_username(user), icon_url=user.avatar_url_as(format="png"))
		await ctx.send(embed=embed)

	@commands.command(brief="Unbans a user.")
	@commands.has_permissions(manage_roles=True, ban_members=True)
	async def unban(self, ctx, user:discord.User, *, reason:str=None):
		admin = ctx.author
		if user == admin:
			await ctx.send("You can't unban yourself.")
			return
		await ctx.guild.unban(user, reason=f"Unbanned by {longform_username(admin)}: {reason if reason else 'No reason specified'}")
		embed=discord.Embed(title=f"Unbanned", description=f"{longform_username(user)} unbanned by {longform_username(admin)}: {reason if reason else 'No reason specified'}")
		embed.set_author(name=longform_username(user), icon_url=user.avatar_url_as(format="png"))
		await ctx.send(embed=embed)

	@commands.command(brief="Unbans a user.")
	@commands.has_permissions(manage_roles=True, kick_members=True)
	async def kick(self, ctx, user:discord.User, *, reason:str=None):
		admin = ctx.author
		if user == admin:
			await ctx.send("You can't unban yourself.")
			return
		await ctx.guild.kick(user, reason=f"Kicked by {longform_username(admin)}: {reason if reason else 'No reason specified'}")
		embed=discord.Embed(title=f"Kicked", description=f"{longform_username(user)} kicked by {longform_username(admin)}: {reason if reason else 'No reason specified'}")
		embed.set_author(name=longform_username(user), icon_url=user.avatar_url_as(format="png"))
		await ctx.send(embed=embed)

def setup(bot, config):
	global C
	C = config
	bot.add_cog(Moderation(bot))