# Movie Delivery Context: tìm cụm từ trong phụ đề video có sẵn (video_subtitle_index); không có video
# khớp thì rơi về nhánh TTS fallback (câu ví dụ từ llm_service + đọc mẫu bằng speech_service).
# Kho video nạp bằng script: scripts/ingest_video.py (video + .srt thật) hoặc scripts/seed_demo_videos.py
# (cảnh mô phỏng). Tìm bằng full-text Postgres; chưa có thu thập/đánh chỉ mục tự động (Định hướng mở rộng).
import re
import uuid
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.models.movie_context import (
	MovieContextMatch,
	MovieContextTtsFallback,
	VideoSource,
	VideoSubtitleIndex,
)
from app.services import llm_service
from app.services.podcast_service import _resolve_persona, _synthesize
from app.services.speaking_service import _audio_dir

MAX_VIDEO_MATCHES = 3


def video_dir() -> Path:
	root = Path(__file__).resolve().parents[2] / get_settings().storage_video_dir
	root.mkdir(parents=True, exist_ok=True)
	return root


async def replace_video_source(
	db: AsyncSession,
	title: str,
	platform: str,
	filename: str,
	subtitles: list[tuple[str, int, int]],
) -> VideoSource:
	"""Ghi 1 video + phụ đề (text, start_ms, end_ms), thay bản cũ cùng title. Dùng cho script nạp/seed.
	Lượt tìm đã trỏ tới dòng phụ đề cũ bị xoá theo (FK không CASCADE) — đây là dữ liệu demo."""
	old = await db.scalar(select(VideoSource).where(VideoSource.title == title, VideoSource.platform == platform))
	if old is not None:
		lines = select(VideoSubtitleIndex.id).where(VideoSubtitleIndex.video_source_id == old.id)
		await db.execute(delete(MovieContextMatch).where(MovieContextMatch.video_subtitle_index_id.in_(lines)))
		await db.delete(old)
		await db.flush()
	source = VideoSource(title=title, platform=platform, video_url=filename, subtitle_language="en")
	db.add(source)
	await db.flush()
	for text, start_ms, end_ms in subtitles:
		db.add(VideoSubtitleIndex(video_source_id=source.id, phrase_text=text, start_time_ms=start_ms, end_time_ms=end_ms))
	await db.flush()
	return source


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


def _view(match: MovieContextMatch, phrase_text: str, **extra) -> dict:
	return {
		"match_id": match.id,
		"source_type": match.source_type,
		"phrase_text": phrase_text,
		"is_saved": bool(match.is_saved),
		**extra,
	}


async def _search_real_video(db: AsyncSession, user_id: uuid.UUID, phrase: str) -> list[dict]:
	# Cấu hình 'simple': giữ MỌI từ (idiom như "hang out", "you can say that again" chứa nhiều
	# stopword — cấu hình 'english' sẽ bỏ chúng và khớp lỏng), các từ phải liền kề đúng thứ tự,
	# không phân biệt hoa/thường/dấu câu. Đổi lại không khớp biến thể ("breaks the ice").
	# ponytail: quét tuần tự (không dùng GIN idx_subtitle_phrase vì index đó là 'english'); vài chục
	# dòng phụ đề demo thì đủ, thêm index 'simple' khi kho video lớn lên.
	rows = (
		await db.execute(
			select(VideoSubtitleIndex, VideoSource)
			.join(VideoSource, VideoSource.id == VideoSubtitleIndex.video_source_id)
			.where(
				func.to_tsvector("simple", VideoSubtitleIndex.phrase_text).op("@@")(
					func.phraseto_tsquery("simple", phrase)
				)
			)
			.order_by(VideoSource.title, VideoSubtitleIndex.start_time_ms)
			.limit(MAX_VIDEO_MATCHES)
		)
	).all()
	found = []
	for line, source in rows:
		match = MovieContextMatch(
			user_id=user_id,
			search_phrase=phrase,
			source_type="real_video",
			video_subtitle_index_id=line.id,
		)
		db.add(match)
		found.append((match, line, source))
	await db.flush()
	return [
		_view(
			m, line.phrase_text, title=source.title, platform=source.platform,
			start_ms=line.start_time_ms, end_ms=line.end_time_ms,
		)
		for m, line, source in found
	]


async def search(
	db: AsyncSession, user_id: uuid.UUID, phrase: str, persona_id: uuid.UUID | None
) -> list[dict]:
	results = await _search_real_video(db, user_id, phrase)
	if results:
		await db.commit()
		return results

	persona = await _resolve_persona(db, persona_id)  # persona sai/không active -> giọng mặc định
	persona_id = persona.id if persona else None
	sentences = await llm_service.generate_movie_example_sentences(phrase)

	matches = []
	for sentence in sentences:
		fallback = await _get_or_create_fallback(db, sentence, persona, persona_id)
		match = MovieContextMatch(
			user_id=user_id,
			search_phrase=phrase,
			source_type="tts_fallback",
			tts_fallback_id=fallback.id,
		)
		db.add(match)
		matches.append((match, fallback))
	await db.flush()
	views = [_view(m, f.phrase_text) for m, f in matches]
	await db.commit()
	return views


async def _get_owned_match(db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID) -> MovieContextMatch:
	match = await db.scalar(
		select(MovieContextMatch).where(MovieContextMatch.id == match_id, MovieContextMatch.user_id == user_id)
	)
	if match is None:
		raise ValueError("movie_match_not_found")
	return match


async def save_match(db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID) -> None:
	match = await _get_owned_match(db, user_id, match_id)
	match.is_saved = True
	await db.commit()


async def get_match_audio_path(db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID) -> str:
	match = await _get_owned_match(db, user_id, match_id)
	fallback = await db.get(MovieContextTtsFallback, match.tts_fallback_id) if match.tts_fallback_id else None
	if fallback is None or not Path(fallback.audio_url).exists():
		raise ValueError("movie_audio_not_found")
	return fallback.audio_url


async def get_match_subtitles(db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID) -> list[dict]:
	"""Toàn bộ dòng phụ đề của video chứa dòng khớp, theo thời gian; `is_match` đánh dấu dòng chứa cụm
	người học tìm (frontend tô màu khác). Mốc thời gian đã tính theo đoạn video đã cắt."""
	match = await _get_owned_match(db, user_id, match_id)
	if match.video_subtitle_index_id is None:
		raise ValueError("movie_video_not_found")
	source_id = await db.scalar(
		select(VideoSubtitleIndex.video_source_id).where(VideoSubtitleIndex.id == match.video_subtitle_index_id)
	)
	lines = (
		await db.scalars(
			select(VideoSubtitleIndex)
			.where(VideoSubtitleIndex.video_source_id == source_id)
			.order_by(VideoSubtitleIndex.start_time_ms)
		)
	).all()
	# Tô mọi dòng chứa cụm (không chỉ dòng của match này): cụm hay lặp ở các dòng liền kề.
	wanted = _words(match.search_phrase)
	return [
		{
			"text": line.phrase_text,
			"start_ms": line.start_time_ms,
			"end_ms": line.end_time_ms,
			"is_match": line.id == match.video_subtitle_index_id or _contains_words(_words(line.phrase_text), wanted),
		}
		for line in lines
	]


def _words(text: str) -> list[str]:
	return re.findall(r"[a-z0-9']+", text.lower())


def _contains_words(words: list[str], wanted: list[str]) -> bool:
	"""`wanted` xuất hiện liền kề, đúng thứ tự trong `words` (cùng quy tắc phraseto_tsquery lúc tìm)."""
	size = len(wanted)
	return size > 0 and any(words[i : i + size] == wanted for i in range(len(words) - size + 1))


async def get_match_video_path(db: AsyncSession, user_id: uuid.UUID, match_id: uuid.UUID) -> str:
	match = await _get_owned_match(db, user_id, match_id)
	if match.video_subtitle_index_id is None:
		raise ValueError("movie_video_not_found")
	source = await db.scalar(
		select(VideoSource)
		.join(VideoSubtitleIndex, VideoSubtitleIndex.video_source_id == VideoSource.id)
		.where(VideoSubtitleIndex.id == match.video_subtitle_index_id)
	)
	if source is None:
		raise ValueError("movie_video_not_found")
	root = video_dir().resolve()
	path = (root / source.video_url).resolve()
	# video_url là tên file; chặn mọi đường dẫn thoát khỏi thư mục video.
	if root not in path.parents or not path.is_file():
		raise ValueError("movie_video_not_found")
	return str(path)
