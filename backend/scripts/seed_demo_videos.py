# Dựng 3 cảnh hội thoại MÔ PHỎNG (giọng Azure TTS 2 người + khung hình có phụ đề) để demo Movie Context,
# rồi ghi video_sources + video_subtitle_index (mỗi lời thoại = 1 dòng phụ đề kèm mốc thời gian thật).
# Đây KHÔNG phải cảnh phim thật: UI và khung hình đều ghi rõ "SIMULATED DEMO SCENE".
# Cần: AZURE_SPEECH_KEY trong .env, `pip install imageio-ffmpeg` (chỉ để dựng video, không nằm trong
# requirements), Pillow. Chạy lại an toàn: bỏ qua cảnh đã có; --force dựng lại (xóa các lượt tìm đã trỏ
# tới cảnh demo cũ).
# Chạy (từ thư mục backend):  python scripts/seed_demo_videos.py [--force]
import asyncio
import io
import selectors
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.database import get_session_factory  # noqa: E402
from app.models.movie_context import (  # noqa: E402
	MovieContextMatch,
	VideoSource,
	VideoSubtitleIndex,
)
from app.services import speech_service  # noqa: E402
from app.services.movie_context_service import video_dir  # noqa: E402

PLATFORM = "demo"
WIDTH, HEIGHT = 854, 480
LEAD_S, GAP_S, TAIL_S = 0.4, 0.5, 0.8
SPEAKERS = [("Mark", "en-US-GuyNeural", (56, 116, 203)), ("Emma", "en-US-JennyNeural", (214, 96, 118))]

SCENES = [
	{
		"title": "The Startup Pitch",
		"file": "demo_piece_of_cake.mp4",
		"bg": (24, 32, 56),
		"lines": [
			(0, "I'm not sure I'm ready for tomorrow's presentation."),
			(1, "Don't worry. For you, pitching to investors is a piece of cake."),
			(0, "Easy for you to say. My hands are shaking already."),
			(1, "Just take a deep breath and tell them your story."),
		],
	},
	{
		"title": "The Office Party",
		"file": "demo_break_the_ice.mp4",
		"bg": (38, 28, 52),
		"lines": [
			(1, "I never know what to say to new people at these events."),
			(0, "Just tell a joke to break the ice."),
			(1, "Like what?"),
			(0, "Ask them about their favorite movie. It works every time."),
			(1, "Okay, I will give it a try."),
		],
	},
	{
		"title": "The Sick Day",
		"file": "demo_under_the_weather.mp4",
		"bg": (22, 44, 44),
		"lines": [
			(0, "You look pale. Are you okay?"),
			(1, "I have been feeling a little under the weather since yesterday."),
			(0, "You should go home and rest."),
			(1, "Yes, I think I will call in sick tomorrow."),
		],
	},
]


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
	for name in ("segoeuib.ttf" if bold else "segoeui.ttf", "arial.ttf"):
		try:
			return ImageFont.truetype(name, size)
		except OSError:
			continue
	return ImageFont.load_default(size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
	lines, current = [], ""
	for word in text.split():
		trial = f"{current} {word}".strip()
		if draw.textlength(trial, font=font) <= max_width:
			current = trial
		else:
			lines.append(current)
			current = word
	return lines + [current]


def _frame(scene: dict, speaker: int, text: str, path: Path) -> None:
	image = Image.new("RGB", (WIDTH, HEIGHT), scene["bg"])
	draw = ImageDraw.Draw(image)
	draw.text((28, 22), scene["title"], font=_font(30, True), fill=(240, 240, 240))
	draw.rounded_rectangle((28, 68, 246, 96), radius=12, fill=(255, 196, 0))
	draw.text((40, 71), "SIMULATED DEMO SCENE", font=_font(15, True), fill=(30, 30, 30))
	# Avatar 2 người, người đang nói sáng, người kia mờ.
	for index, (name, _voice, color) in enumerate(SPEAKERS):
		cx = 150 if index == 0 else WIDTH - 150
		active = index == speaker
		fill = color if active else tuple(int(c * 0.35 + 30) for c in color)
		draw.ellipse((cx - 44, 132, cx + 44, 220), fill=fill)
		draw.text((cx, 176), name[0], font=_font(44, True), fill="white", anchor="mm")
		draw.text((cx, 240), name, font=_font(22, active), fill="white" if active else (150, 150, 150), anchor="mm")
	caption_font = _font(34, True)
	rows = _wrap(draw, text, caption_font, WIDTH - 120)
	top = 300 + (150 - len(rows) * 44) // 2
	for i, row in enumerate(rows):
		draw.text((WIDTH / 2, top + i * 44), row, font=caption_font, fill="white", anchor="mt")
	image.save(path)


def _pcm(wav_bytes: bytes) -> tuple[bytes, int]:
	with wave.open(io.BytesIO(wav_bytes)) as reader:
		return reader.readframes(reader.getnframes()), reader.getframerate()


def build_scene(scene: dict, out_path: Path) -> list[tuple[str, int, int]]:
	"""Dựng mp4, trả về [(lời thoại, start_ms, end_ms)] của từng dòng."""
	import imageio_ffmpeg

	rate = 16000
	silence = lambda seconds: b"\x00\x00" * int(rate * seconds)  # noqa: E731
	audio, subtitles, segments = bytearray(), [], []
	cursor = 0.0
	for order, (speaker, text) in enumerate(scene["lines"]):
		pcm, wav_rate = _pcm(speech_service.synthesize_azure_speech(text, SPEAKERS[speaker][1]))
		assert wav_rate == rate, wav_rate
		lead = LEAD_S if order == 0 else 0.0
		last = order == len(scene["lines"]) - 1
		speech_s = len(pcm) / 2 / rate
		start = cursor + lead
		end = start + speech_s
		gap = TAIL_S if last else GAP_S
		audio += silence(lead) + pcm + silence(gap)
		subtitles.append((text, round(start * 1000), round(end * 1000)))
		segments.append((speaker, text, lead + speech_s + gap))
		cursor = end + gap

	with tempfile.TemporaryDirectory() as tmp:
		tmp_dir = Path(tmp)
		with wave.open(str(tmp_dir / "audio.wav"), "wb") as writer:
			writer.setnchannels(1)
			writer.setsampwidth(2)
			writer.setframerate(rate)
			writer.writeframes(bytes(audio))
		listing = []
		for order, (speaker, text, seconds) in enumerate(segments):
			frame = tmp_dir / f"f{order}.png"
			_frame(scene, speaker, text, frame)
			listing.append(f"file '{frame.as_posix()}'\nduration {seconds:.3f}")
		listing.append(f"file '{(tmp_dir / f'f{len(segments) - 1}.png').as_posix()}'")  # concat cần lặp khung cuối
		(tmp_dir / "frames.txt").write_text("\n".join(listing), encoding="utf-8")
		subprocess.run(
			[
				imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
				"-f", "concat", "-safe", "0", "-i", str(tmp_dir / "frames.txt"),
				"-i", str(tmp_dir / "audio.wav"),
				"-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
				"-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", str(out_path),
			],
			check=True,
		)
	return subtitles


async def seed(force: bool) -> None:
	async with get_session_factory()() as session:
		existing = {
			source.title: source
			for source in (await session.scalars(select(VideoSource).where(VideoSource.platform == PLATFORM))).all()
		}
		for scene in SCENES:
			out_path = video_dir() / scene["file"]
			source = existing.get(scene["title"])
			if source is not None and out_path.exists() and not force:
				print(f"bỏ qua (đã có): {scene['title']}", flush=True)
				continue
			if source is not None:
				index_ids = select(VideoSubtitleIndex.id).where(VideoSubtitleIndex.video_source_id == source.id)
				await session.execute(delete(MovieContextMatch).where(MovieContextMatch.video_subtitle_index_id.in_(index_ids)))
				await session.delete(source)
				await session.flush()
			print(f"dựng: {scene['title']} ...", flush=True)
			subtitles = await asyncio.to_thread(build_scene, scene, out_path)
			source = VideoSource(title=scene["title"], platform=PLATFORM, video_url=scene["file"], subtitle_language="en")
			session.add(source)
			await session.flush()
			for text, start_ms, end_ms in subtitles:
				session.add(
					VideoSubtitleIndex(video_source_id=source.id, phrase_text=text, start_time_ms=start_ms, end_time_ms=end_ms)
				)
			print(f"  {out_path.name}: {out_path.stat().st_size // 1024} KB, {len(subtitles)} dòng phụ đề", flush=True)
		await session.commit()


if __name__ == "__main__":
	# psycopg async không chạy được trên ProactorEventLoop mặc định của Windows.
	asyncio.run(seed("--force" in sys.argv), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
	print("xong")
