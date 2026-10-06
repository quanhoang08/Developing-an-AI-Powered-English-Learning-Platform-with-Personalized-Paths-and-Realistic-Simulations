# Nhật ký giọng nói 60 giây (backlog 4.4) và bạn bè + bảng xếp hạng (4.6). Đấu 1-1 / thử thách nhóm cần
# realtime nên không làm; bảng xếp hạng xếp theo tổng XP vì hệ thống chưa lưu XP theo tuần.
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.gamification import Streak
from app.models.social import Friendship, VoiceDiaryEntry
from app.models.user import User
from app.services import speaking_service, speech_service
from app.services.gamification_service import study_today, visible_streak, weekly_xp

_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".ogg"}
MAX_DIARY_SECONDS = 60
MAX_DIARY_ENTRIES = 50
MAX_DIARY_BYTES = 5 * 1024 * 1024


# --- Nhật ký giọng nói ---
async def add_diary_entry(db: AsyncSession, user_id: uuid.UUID, audio: UploadFile, duration_seconds: int) -> VoiceDiaryEntry:
	if not 1 <= duration_seconds <= MAX_DIARY_SECONDS:
		raise ValueError("invalid_duration")
	extension = Path(audio.filename or "").suffix.lower()
	if extension not in _AUDIO_EXTENSIONS:
		raise ValueError("unsupported_audio_type")
	content = await audio.read()
	if not content:
		raise ValueError("empty_audio")
	if len(content) > MAX_DIARY_BYTES:
		raise ValueError("audio_too_large")
	existing = list(await db.scalars(select(VoiceDiaryEntry.id).where(VoiceDiaryEntry.user_id == user_id)))
	if len(existing) >= MAX_DIARY_ENTRIES:
		raise ValueError("diary_full")
	file_name = f"diary_{uuid.uuid4()}{extension}"
	path = speaking_service._audio_dir() / file_name
	path.write_bytes(content)
	transcript, wpm = None, None
	try:
		transcript, _ = await run_in_threadpool(speech_service.transcribe_with_fallback, str(path))
		transcript = transcript.strip() or None
		if transcript:
			wpm = round(len(transcript.split()) * 60 / duration_seconds)
	except speech_service.SpeechServiceError:
		pass  # vẫn lưu bản ghi, chỉ thiếu chữ chép lại
	entry = VoiceDiaryEntry(
		user_id=user_id, file_name=file_name, duration_seconds=duration_seconds, transcript=transcript, words_per_minute=wpm
	)
	db.add(entry)
	await db.commit()
	await db.refresh(entry)
	return entry


async def list_diary(db: AsyncSession, user_id: uuid.UUID) -> list[VoiceDiaryEntry]:
	return list(
		await db.scalars(
			select(VoiceDiaryEntry).where(VoiceDiaryEntry.user_id == user_id).order_by(VoiceDiaryEntry.created_at.desc())
		)
	)


async def get_diary_entry(db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> VoiceDiaryEntry:
	entry = await db.scalar(select(VoiceDiaryEntry).where(VoiceDiaryEntry.id == entry_id, VoiceDiaryEntry.user_id == user_id))
	if entry is None:
		raise ValueError("diary_entry_not_found")
	return entry


def diary_path(entry: VoiceDiaryEntry) -> Path:
	return speaking_service._audio_dir() / entry.file_name


async def delete_diary_entry(db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> None:
	entry = await get_diary_entry(db, user_id, entry_id)
	diary_path(entry).unlink(missing_ok=True)
	await db.delete(entry)
	await db.commit()


# --- Bạn bè ---
def display_name(user: User) -> str:
	return user.display_name or user.email.split("@")[0]


async def send_request(db: AsyncSession, user: User, email: str) -> None:
	"""Gửi lời mời theo email. Email không tồn tại -> im lặng (không lộ tài khoản nào có thật)."""
	target = await db.scalar(select(User).where(User.email == email.strip().lower()))
	if target is None or target.id == user.id:
		return
	existing = await db.scalar(
		select(Friendship).where(
			or_(
				(Friendship.requester_id == user.id) & (Friendship.addressee_id == target.id),
				(Friendship.requester_id == target.id) & (Friendship.addressee_id == user.id),
			)
		)
	)
	if existing is not None:
		# Người kia đã mời mình trước thì coi như đồng ý.
		if existing.status == "pending" and existing.addressee_id == user.id:
			existing.status = "accepted"
			await db.commit()
		return
	db.add(Friendship(requester_id=user.id, addressee_id=target.id))
	await db.commit()


async def overview(db: AsyncSession, user_id: uuid.UUID) -> dict:
	links = list(
		await db.scalars(select(Friendship).where(or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id)))
	)
	other_ids = {l.addressee_id if l.requester_id == user_id else l.requester_id for l in links}
	users = {u.id: u for u in await db.scalars(select(User).where(User.id.in_(other_ids)))} if other_ids else {}
	friends, incoming, outgoing = [], [], []
	for link in links:
		other = users.get(link.addressee_id if link.requester_id == user_id else link.requester_id)
		if other is None:
			continue
		item = {"friendship_id": str(link.id), "user_id": str(other.id), "name": display_name(other)}
		if link.status == "accepted":
			friends.append(item)
		elif link.addressee_id == user_id:
			incoming.append(item)
		else:
			outgoing.append(item)
	return {"friends": friends, "incoming": incoming, "outgoing": outgoing}


async def accept(db: AsyncSession, user_id: uuid.UUID, friendship_id: uuid.UUID) -> None:
	link = await db.scalar(select(Friendship).where(Friendship.id == friendship_id, Friendship.addressee_id == user_id))
	if link is None or link.status != "pending":
		raise ValueError("request_not_found")
	link.status = "accepted"
	await db.commit()


async def remove(db: AsyncSession, user_id: uuid.UUID, friendship_id: uuid.UUID) -> None:
	"""Huỷ lời mời, từ chối, hoặc bỏ bạn: cả hai phía đều được xoá."""
	link = await db.scalar(
		select(Friendship).where(
			Friendship.id == friendship_id, or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id)
		)
	)
	if link is None:
		raise ValueError("request_not_found")
	await db.delete(link)
	await db.commit()


async def leaderboard(db: AsyncSession, user: User, period: str = "all") -> list[dict]:
	"""Bản thân + bạn đã chấp nhận, xếp theo tổng XP hoặc XP tuần này (period="week"); đồng điểm thì chuỗi dài hơn."""
	data = await overview(db, user.id)
	ids = [user.id] + [uuid.UUID(f["user_id"]) for f in data["friends"]]
	names = {uuid.UUID(f["user_id"]): f["name"] for f in data["friends"]}
	names[user.id] = display_name(user)
	streaks = {s.user_id: s for s in await db.scalars(select(Streak).where(Streak.user_id.in_(ids)))}
	week = await weekly_xp(db, ids)
	today = study_today()
	rows = []
	for uid in ids:
		s = streaks.get(uid)
		rows.append(
			{
				"user_id": str(uid),
				"name": names[uid],
				"total_xp": (s.total_xp or 0) if s else 0,
				"weekly_xp": week.get(uid, 0),
				"streak": visible_streak(s.current_streak or 0, s.last_active_date, today, s.freezes_available or 0) if s else 0,
				"is_me": uid == user.id,
			}
		)
	xp_key = "weekly_xp" if period == "week" else "total_xp"
	rows.sort(key=lambda r: (-r[xp_key], -r["streak"], r["name"].lower()))
	for rank, row in enumerate(rows, 1):
		row["rank"] = rank
	return rows
