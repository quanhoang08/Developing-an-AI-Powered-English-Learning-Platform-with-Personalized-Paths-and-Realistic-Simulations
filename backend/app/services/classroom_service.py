# Chế độ lớp học (backlog nhóm 5): người tạo lớp là giáo viên, học sinh vào bằng mã, giáo viên giao bài
# (mô tả + kỹ năng + hạn) và xem tiến độ học sinh trong lớp. Bài có kỹ năng tự tính hoàn thành (xem _done_ids).
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adaptive import UserError
from app.models.gamification import ActivityLog, Streak, StudyTimeLog
from app.models.grammar import GrammarAttempt
from app.models.social import ClassAssignment, ClassMember, Classroom
from app.models.user import User
from app.models.vocab import VocabItem
from app.services.gamification_service import study_today, visible_streak
from app.services.social_service import display_name

_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # bỏ ký tự dễ nhầm (0/O, 1/I/L)


async def weekly_stats(db: AsyncSession, user: User) -> dict:
	"""Số liệu 7 ngày của 1 học sinh cho bảng tiến độ giáo viên: chuỗi, XP, phút học, lỗi, số từ."""
	since = datetime.now(timezone.utc) - timedelta(days=7)
	streak = await db.scalar(select(Streak).where(Streak.user_id == user.id))
	seconds = await db.scalar(
		select(func.coalesce(func.sum(StudyTimeLog.duration_seconds), 0)).where(
			StudyTimeLog.user_id == user.id, StudyTimeLog.created_at >= since
		)
	)
	errors = await db.scalar(select(func.count()).select_from(UserError).where(UserError.user_id == user.id, UserError.created_at >= since))
	words = await db.scalar(select(func.count()).select_from(VocabItem).where(VocabItem.user_id == user.id, VocabItem.created_at >= since))
	current = (
		visible_streak(streak.current_streak or 0, streak.last_active_date, study_today(), streak.freezes_available or 0)
		if streak
		else 0
	)
	return {
		"streak": current,
		"total_xp": streak.total_xp if streak else 0,
		"minutes": round((seconds or 0) / 60),
		"mistakes_logged": errors or 0,
		"words_saved": words or 0,
	}


async def create_class(db: AsyncSession, teacher: User, name: str) -> Classroom:
	for _ in range(5):
		code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
		if await db.scalar(select(Classroom.id).where(Classroom.join_code == code)) is None:
			break
	else:
		raise ValueError("code_generation_failed")
	room = Classroom(teacher_id=teacher.id, name=name.strip(), join_code=code)
	db.add(room)
	await db.commit()
	await db.refresh(room)
	return room


async def join_class(db: AsyncSession, user: User, code: str) -> Classroom:
	room = await db.scalar(select(Classroom).where(Classroom.join_code == code.strip().upper()))
	if room is None:
		raise ValueError("class_not_found")
	if room.teacher_id != user.id and await db.get(ClassMember, (room.id, user.id)) is None:
		db.add(ClassMember(class_id=room.id, user_id=user.id))
		await db.commit()
	return room


async def my_classes(db: AsyncSession, user_id: uuid.UUID) -> dict:
	teaching = list(await db.scalars(select(Classroom).where(Classroom.teacher_id == user_id).order_by(Classroom.created_at.desc())))
	joined = list(
		await db.scalars(
			select(Classroom)
			.join(ClassMember, ClassMember.class_id == Classroom.id)
			.where(ClassMember.user_id == user_id)
			.order_by(Classroom.created_at.desc())
		)
	)
	counts = {}
	if teaching:
		rows = await db.execute(
			select(ClassMember.class_id, func.count()).where(ClassMember.class_id.in_([c.id for c in teaching])).group_by(ClassMember.class_id)
		)
		counts = dict(rows.all())
	return {
		"teaching": [{"id": str(c.id), "name": c.name, "join_code": c.join_code, "members": counts.get(c.id, 0)} for c in teaching],
		"joined": [{"id": str(c.id), "name": c.name} for c in joined],
	}


async def _get_room(db: AsyncSession, user_id: uuid.UUID, class_id: uuid.UUID) -> tuple[Classroom, bool]:
	"""(lớp, là giáo viên). Chỉ giáo viên hoặc thành viên được xem; người ngoài gặp 404."""
	room = await db.get(Classroom, class_id)
	if room is None:
		raise ValueError("class_not_found")
	if room.teacher_id == user_id:
		return room, True
	if await db.get(ClassMember, (class_id, user_id)) is None:
		raise ValueError("class_not_found")
	return room, False


# Bài giao có `skill` tự tính hoàn thành khi học sinh có >= 1 hoạt động thuộc kỹ năng đó SAU lúc giao bài
# (không xét hạn nộp, không xét điểm). Bài không gắn kỹ năng thì không tự chấm được.
_ACTIVITIES_BY_SKILL = {
	"reading": ("reading_completed", "toeic_reading_completed"),
	"listening": ("dictation_completed", "listening_quiz_completed", "toeic_listening_completed"),
	"writing": ("writing_submitted",),
	"speaking": ("speaking_turn", "pronunciation_practice", "speaking_silent"),
	"vocab": ("vocab_review",),
}


async def _done_ids(db: AsyncSession, assignment: ClassAssignment, user_ids: list[uuid.UUID]) -> set[uuid.UUID]:
	"""Trong `user_ids`, ai đã làm bài giao này; skill rỗng/không hỗ trợ thì không ai (chưa tự chấm được)."""
	if not user_ids or not assignment.skill:
		return set()
	if assignment.skill == "grammar":  # ngữ pháp không cộng XP nên đọc thẳng lịch sử làm bài
		query = select(GrammarAttempt.user_id).where(GrammarAttempt.created_at >= assignment.created_at, GrammarAttempt.user_id.in_(user_ids))
	else:
		query = select(ActivityLog.user_id).where(
			ActivityLog.activity.in_(_ACTIVITIES_BY_SKILL[assignment.skill]),
			ActivityLog.created_at >= assignment.created_at,
			ActivityLog.user_id.in_(user_ids),
		)
	return set(await db.scalars(query.distinct()))


async def class_detail(db: AsyncSession, user_id: uuid.UUID, class_id: uuid.UUID) -> dict:
	room, is_teacher = await _get_room(db, user_id, class_id)
	assignments = list(
		await db.scalars(select(ClassAssignment).where(ClassAssignment.class_id == class_id).order_by(ClassAssignment.created_at.desc()))
	)
	members = (
		list(await db.scalars(select(User).join(ClassMember, ClassMember.user_id == User.id).where(ClassMember.class_id == class_id)))
		if is_teacher
		else []
	)
	done = {a.id: await _done_ids(db, a, [m.id for m in members] if is_teacher else [user_id]) for a in assignments}
	detail = {
		"id": str(room.id),
		"name": room.name,
		"is_teacher": is_teacher,
		"join_code": room.join_code if is_teacher else None,
		"assignments": [
			{
				"id": str(a.id),
				"title": a.title,
				"description": a.description,
				"skill": a.skill,
				"due_date": a.due_date.isoformat() if a.due_date else None,
				"auto_graded": a.skill is not None,
				# Học sinh: mình đã làm chưa. Giáo viên: bao nhiêu học sinh đã làm / tổng.
				**({"done_count": len(done[a.id]), "total_students": len(members)} if is_teacher else {"done": user_id in done[a.id]}),
			}
			for a in assignments
		],
		"students": [],
	}
	if is_teacher:
		for member in members:
			stats = await weekly_stats(db, member)
			finished = sum(member.id in done[a.id] for a in assignments)
			detail["students"].append(
				{"user_id": str(member.id), "name": display_name(member), **stats, "assignments_done": finished, "assignments_total": len(assignments)}
			)
		detail["students"].sort(key=lambda s: -s["total_xp"])
	return detail


async def add_assignment(
	db: AsyncSession, user_id: uuid.UUID, class_id: uuid.UUID, title: str, description: str | None, skill: str | None, due: date | None
) -> ClassAssignment:
	_, is_teacher = await _get_room(db, user_id, class_id)
	if not is_teacher:
		raise ValueError("not_teacher")
	item = ClassAssignment(class_id=class_id, title=title.strip(), description=description, skill=skill, due_date=due)
	db.add(item)
	await db.commit()
	await db.refresh(item)
	return item


async def delete_assignment(db: AsyncSession, user_id: uuid.UUID, class_id: uuid.UUID, assignment_id: uuid.UUID) -> None:
	_, is_teacher = await _get_room(db, user_id, class_id)
	item = await db.get(ClassAssignment, assignment_id)
	if not is_teacher or item is None or item.class_id != class_id:
		raise ValueError("not_teacher" if not is_teacher else "assignment_not_found")
	await db.delete(item)
	await db.commit()


async def remove_member(db: AsyncSession, user_id: uuid.UUID, class_id: uuid.UUID, member_id: uuid.UUID) -> None:
	"""Giáo viên xoá học sinh, hoặc học sinh tự rời lớp."""
	_, is_teacher = await _get_room(db, user_id, class_id)
	if not is_teacher and member_id != user_id:
		raise ValueError("not_teacher")
	member = await db.get(ClassMember, (class_id, member_id))
	if member is None:
		raise ValueError("member_not_found")
	await db.delete(member)
	await db.commit()


async def delete_class(db: AsyncSession, user_id: uuid.UUID, class_id: uuid.UUID) -> None:
	room, is_teacher = await _get_room(db, user_id, class_id)
	if not is_teacher:
		raise ValueError("not_teacher")
	await db.delete(room)
	await db.commit()
