# Mẹo nhớ tiếng Việt do người học tạo + bình chọn (backlog 3.7). Không LLM; mẹo hiển thị công khai theo từ.
import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vocab import Mnemonic, MnemonicReport, MnemonicVote

REPORT_HIDE_THRESHOLD = 3  # ponytail: chưa có người quản trị duyệt; đủ 3 báo cáo khác nhau thì tự ẩn


def _key(term: str) -> str:
	return " ".join(term.lower().split())


async def list_mnemonics(db: AsyncSession, user_id: uuid.UUID, term: str) -> list[dict]:
	votes = func.count(MnemonicVote.user_id)
	report_counts = select(MnemonicReport.mnemonic_id).group_by(MnemonicReport.mnemonic_id).having(func.count() >= REPORT_HIDE_THRESHOLD)
	i_reported = select(MnemonicReport.mnemonic_id).where(MnemonicReport.user_id == user_id)
	rows = (
		await db.execute(
			select(Mnemonic, votes)
			.outerjoin(MnemonicVote, MnemonicVote.mnemonic_id == Mnemonic.id)
			.where(
				Mnemonic.term_key == _key(term),
				Mnemonic.id.not_in(i_reported),
				# Mẹo bị báo cáo đủ ngưỡng thì ẩn với người khác; chủ mẹo vẫn thấy mẹo của mình.
				or_(Mnemonic.user_id == user_id, Mnemonic.id.not_in(report_counts)),
			)
			.group_by(Mnemonic.id)
			.order_by(votes.desc(), Mnemonic.created_at)
			.limit(20)
		)
	).all()
	mine = set(
		await db.scalars(
			select(MnemonicVote.mnemonic_id).where(
				MnemonicVote.user_id == user_id, MnemonicVote.mnemonic_id.in_([m.id for m, _ in rows])
			)
		)
	)
	return [
		{"id": m.id, "text": m.body, "votes": n, "voted": m.id in mine, "is_mine": m.user_id == user_id}
		for m, n in rows
	]


async def save_mnemonic(db: AsyncSession, user_id: uuid.UUID, term: str, text: str) -> None:
	"""Mỗi user một mẹo cho mỗi từ: gửi lại thì thay nội dung (và giữ phiếu cũ)."""
	key = _key(term)
	existing = await db.scalar(select(Mnemonic).where(Mnemonic.user_id == user_id, Mnemonic.term_key == key))
	if existing:
		existing.body = text
	else:
		db.add(Mnemonic(user_id=user_id, term_key=key, body=text))
	await db.commit()


async def toggle_vote(db: AsyncSession, user_id: uuid.UUID, mnemonic_id: uuid.UUID) -> bool:
	"""Bật/tắt phiếu; trả True nếu sau thao tác là đang bầu. Không được bầu mẹo của chính mình."""
	mnemonic = await db.get(Mnemonic, mnemonic_id)
	if mnemonic is None:
		raise ValueError("resource_not_found")
	if mnemonic.user_id == user_id:
		raise ValueError("cannot_vote_own")
	removed = await db.execute(
		delete(MnemonicVote).where(MnemonicVote.mnemonic_id == mnemonic_id, MnemonicVote.user_id == user_id)
	)
	if not removed.rowcount:
		db.add(MnemonicVote(mnemonic_id=mnemonic_id, user_id=user_id))
	await db.commit()
	return not removed.rowcount


async def report_mnemonic(db: AsyncSession, user_id: uuid.UUID, mnemonic_id: uuid.UUID) -> None:
	"""Báo cáo mẹo không phù hợp (idempotent); người báo cáo không thấy lại mẹo đó, đủ ngưỡng thì ẩn với mọi người."""
	mnemonic = await db.get(Mnemonic, mnemonic_id)
	if mnemonic is None:
		raise ValueError("resource_not_found")
	if mnemonic.user_id == user_id:
		raise ValueError("cannot_report_own")
	await db.execute(pg_insert(MnemonicReport).values(mnemonic_id=mnemonic_id, user_id=user_id).on_conflict_do_nothing())
	await db.commit()


async def delete_mnemonic(db: AsyncSession, user_id: uuid.UUID, mnemonic_id: uuid.UUID) -> None:
	result = await db.execute(delete(Mnemonic).where(Mnemonic.id == mnemonic_id, Mnemonic.user_id == user_id))
	if not result.rowcount:
		raise ValueError("resource_not_found")
	await db.commit()
