import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_UUID_PK = dict(primary_key=True, server_default=text("uuid_generate_v4()"))


class Wallet(Base):
	"""Xu, tim và 2x XP booster của 1 user (migration 0036); dòng tạo lười khi user có XP đầu tiên hoặc mở ví."""

	__tablename__ = "wallets"

	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
	coins: Mapped[int] = mapped_column(Integer, server_default=text("0"))
	hearts: Mapped[int] = mapped_column(Integer, server_default=text("5"))
	hearts_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
	booster_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class UserItem(Base):
	__tablename__ = "user_items"

	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
	item_id: Mapped[str] = mapped_column(String(40), primary_key=True)
	equipped: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
	acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Guild(Base):
	__tablename__ = "guilds"

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_UUID_PK)
	name: Mapped[str] = mapped_column(String(40))
	join_code: Mapped[str] = mapped_column(String(8), unique=True)
	owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class GuildMember(Base):
	__tablename__ = "guild_members"

	guild_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("guilds.id", ondelete="CASCADE"), primary_key=True)
	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, unique=True)
	joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class PhonemeStat(Base):
	__tablename__ = "phoneme_stats"

	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
	phoneme: Mapped[str] = mapped_column(String(12), primary_key=True)
	attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
	total_score: Mapped[float] = mapped_column(Float, server_default=text("0"))
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
