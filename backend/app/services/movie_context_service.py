# Movie Delivery Context — chỉ nhánh TTS fallback: câu ví dụ (llm_service) + đọc mẫu (speech_service).
# Không có thuật toán tìm video nào ở đây (nhánh real_video là Định hướng mở rộng).
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.movie_context import MovieContextMatch, MovieContextTtsFallback
from app.services import llm_service
from app.services.podcast_service import _resolve_persona, _synthesize
from app.services.speaking_service import _audio_dir


async def _get_or_create_fallback(
	db: AsyncSession, sentence: str, persona, persona_id: uuid.UUID | None
) -> MovieContextTtsFallback:
	# Cache dùng chung giữa user; unique (phrase_text, persona_id) không chặn được persona NULL
	# nên tra trước bằng IS NOT DISTINCT FROM thay vì trông vào constraint.
	existing = await db.scalar(
		select(MovieContextTtsFallback).where(
			MovieContextTtsFallback.phrase_text == sentence,
			MovieContextTtsFallback.persona_id.is_not_distinct_from(persona_id),
		)
	)
	if existing is not None and Path(existing.audio_url).exists():
		return existing
	audio = await run_in_threadpool(_synthesize, sentence, persona)
	dest = _audio_dir() / f"movie_{uuid.uuid4()}.wav"
	dest.write_bytes(audio)
	if existing is not None:
		existing.audio_url = str(dest)  # file cũ đã mất khỏi đĩa -> sinh lại, giữ nguyên dòng cache
		return existing
	row = MovieContextTtsFallback(phrase_text=sentence, persona_id=persona_id, audio_url=str(dest))
	db.add(row)
	await db.flush()
	return row


async def search(
	db: AsyncSession, user_id: uuid.UUID, phrase: str, persona_id: uuid.UUID | None
) -> list[tuple[MovieContextMatch, MovieContextTtsFallback]]:
	persona = await _resolve_persona(db, persona_id)  # persona sai/không active -> giọng mặc định
	persona_id = persona.id if persona else None
	sentences = await llm_service.generate_movie_example_sentences(phrase)

	results = []
	for sentence in sentences:
		fallback = await _get_or_create_fallback(db, sentence, persona, persona_id)
		match = MovieContextMatch(
			user_id=user_id,
			search_phrase=phrase,
			source_type="tts_fallback",
			tts_fallback_id=fallback.id,
		)
		db.add(match)
		results.append((match, fallback))
	await db.commit()
	return results


async def _get_owned_match(
	db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID
) -> tuple[MovieContextMatch, MovieContextTtsFallback]:
	row = (
		await db.execute(
			select(MovieContextMatch, MovieContextTtsFallback)
			.join(MovieContextTtsFallback, MovieContextTtsFallback.id == MovieContextMatch.tts_fallback_id)
			.where(MovieContextMatch.id == match_id, MovieContextMatch.user_id == user_id)
		)
	).first()
	if row is None:
		raise ValueError("movie_match_not_found")
	return row[0], row[1]


async def save_match(db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID) -> None:
	match, _ = await _get_owned_match(db, user_id, match_id)
	match.is_saved = True
	await db.commit()


async def get_match_audio_path(db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID) -> str:
	_, fallback = await _get_owned_match(db, user_id, match_id)
	if not Path(fallback.audio_url).exists():
		raise ValueError("movie_audio_not_found")
	return fallback.audio_url
