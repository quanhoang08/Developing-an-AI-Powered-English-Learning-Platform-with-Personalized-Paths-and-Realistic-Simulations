"""Study Clan / Guild (tài liệu tính năng mục VIII): nhóm tối đa 5 người, đua XP tuần với các bang khác."""

import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.economy import Guild, GuildMember
from app.models.user import User
from app.services.gamification_service import weekly_xp
from app.services.social_service import display_name

MAX_MEMBERS = 5
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


async def _membership(db: AsyncSession, user_id: uuid.UUID) -> GuildMember | None:
	return await db.scalar(select(GuildMember).where(GuildMember.user_id == user_id))


async def create(db: AsyncSession, user: User, name: str) -> Guild:
	name = name.strip()
	if not 3 <= len(name) <= 40:
		raise ValueError("invalid_name")
	if await _membership(db, user.id):
		raise ValueError("already_in_guild")
	for _ in range(5):
		code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
		if await db.scalar(select(Guild.id).where(Guild.join_code == code)) is None:
			break
	else:
		raise ValueError("code_generation_failed")
	guild = Guild(name=name, join_code=code, owner_id=user.id)
	db.add(guild)
	await db.flush()
	db.add(GuildMember(guild_id=guild.id, user_id=user.id))
	await db.commit()
	return guild


async def join(db: AsyncSession, user: User, code: str) -> Guild:
	guild = await db.scalar(select(Guild).where(Guild.join_code == code.strip().upper()).with_for_update())
	if guild is None:
		raise LookupError("guild_not_found")
	if await _membership(db, user.id):
		raise ValueError("already_in_guild")
	size = len(list(await db.scalars(select(GuildMember.user_id).where(GuildMember.guild_id == guild.id))))
	if size >= MAX_MEMBERS:
		raise ValueError("guild_full")
	db.add(GuildMember(guild_id=guild.id, user_id=user.id))
	await db.commit()
	return guild


async def leave(db: AsyncSession, user_id: uuid.UUID) -> None:
	member = await _membership(db, user_id)
	if member is None:
		raise LookupError("not_in_guild")
	guild = await db.get(Guild, member.guild_id)
	await db.delete(member)
	await db.flush()
	rest = list(await db.scalars(select(GuildMember).where(GuildMember.guild_id == guild.id).order_by(GuildMember.joined_at)))
	if not rest:
		await db.delete(guild)
	elif guild.owner_id == user_id:
		guild.owner_id = rest[0].user_id
	await db.commit()


async def _summary(db: AsyncSession, guild: Guild, viewer_id: uuid.UUID | None) -> dict:
	member_ids = list(await db.scalars(select(GuildMember.user_id).where(GuildMember.guild_id == guild.id)))
	users = {u.id: u for u in await db.scalars(select(User).where(User.id.in_(member_ids)))}
	xp = await weekly_xp(db, member_ids)
	members = sorted(
		(
			{"user_id": str(uid), "name": display_name(users[uid]), "weekly_xp": xp.get(uid, 0), "is_owner": uid == guild.owner_id}
			for uid in member_ids
		),
		key=lambda m: -m["weekly_xp"],
	)
	return {
		"id": str(guild.id),
		"name": guild.name,
		"join_code": guild.join_code if viewer_id in member_ids else None,
		"weekly_xp": sum(m["weekly_xp"] for m in members),
		"members": members,
		"max_members": MAX_MEMBERS,
	}


async def mine(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
	member = await _membership(db, user_id)
	if member is None:
		return None
	return await _summary(db, await db.get(Guild, member.guild_id), user_id)


async def leaderboard(db: AsyncSession, user_id: uuid.UUID, limit: int = 10) -> list[dict]:
	# ponytail: tính từng bang (N truy vấn) — đủ cho vài chục bang; gộp 1 SQL khi số bang lớn.
	rows = [await _summary(db, g, user_id) for g in await db.scalars(select(Guild))]
	rows.sort(key=lambda g: -g["weekly_xp"])
	return [
		{"name": g["name"], "weekly_xp": g["weekly_xp"], "members": len(g["members"]), "is_mine": g["join_code"] is not None}
		for g in rows[:limit]
	]
