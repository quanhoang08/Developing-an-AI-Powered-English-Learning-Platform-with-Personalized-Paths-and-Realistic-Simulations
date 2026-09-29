# Nạp 1 video THẬT + file phụ đề .srt vào kho Movie Context: nén 480p (tuỳ chọn cắt đoạn), gộp cue thành
# câu, ghi video_sources + video_subtitle_index, rồi in các idiom phổ biến có trong đoạn đó để chọn cụm demo.
# Cần: `pip install imageio-ffmpeg` (chỉ để nén/cắt video, không nằm trong requirements).
# Video được tải nguyên file về trình duyệt khi xem (video nằm sau JWT) nên NÊN cắt đoạn ≤ ~15 phút.
# Chạy (từ thư mục backend):
#   PYTHONUTF8=1 python scripts/ingest_video.py --video "D:/films/tears.mkv" --srt "D:/films/tears.en.srt" \
#       --title "Tears of Steel" [--start 00:02:00 --end 00:14:00] [--platform film]
# Chạy lại với cùng --title/--platform thì thay bản cũ. Phụ đề PHẢI đúng bản phim đã tải (cùng phiên bản/
# fps), nếu lệch giờ thì cảnh phát ra sẽ sai — sau khi nạp, xem thử 1-2 cảnh bằng giao diện để kiểm tra.
import argparse
import asyncio
import re
import selectors
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_session_factory  # noqa: E402
from app.services.movie_context_service import replace_video_source, video_dir  # noqa: E402
from app.utils.subtitles import clip_cues, merge_cues, parse_srt, read_text  # noqa: E402

# Idiom phổ biến, chỉ để gợi ý cụm demo (không dùng để lọc phụ đề đã nạp).
COMMON_IDIOMS = [
	"piece of cake", "break the ice", "under the weather", "spill the beans", "bite the bullet",
	"hit the nail on the head", "let the cat out of the bag", "once in a blue moon", "cost an arm and a leg",
	"call it a day", "get out of hand", "on the fence", "beat around the bush", "cut corners",
	"the last straw", "hang in there", "speak of the devil", "kill two birds", "in the same boat",
	"back to square one", "a blessing in disguise", "burn the midnight oil", "cross that bridge",
	"the ball is in your court", "get cold feet", "pull someone's leg", "sit tight", "long shot",
	"make up your mind", "take it easy", "no big deal", "give me a break", "keep an eye on",
	"look on the bright side", "get the hang of", "in the nick of time", "on the same page",
	"out of the blue", "rain check", "so far so good", "step up", "figure out", "hang out",
]


def parse_time(value: str) -> int:
	"""'90' (giây), 'MM:SS' hoặc 'HH:MM:SS' -> mili giây."""
	seconds = 0.0
	for part in value.split(":"):
		seconds = seconds * 60 + float(part)
	return round(seconds * 1000)


def slugify(title: str) -> str:
	return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "video"


def transcode(source: str, dest: Path, start_ms: int, end_ms: int | None) -> None:
	import imageio_ffmpeg

	cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error"]
	if start_ms:
		cmd += ["-ss", f"{start_ms / 1000:.3f}"]  # đặt trước -i: tua nhanh, đủ chính xác cho demo
	cmd += ["-i", source]  # đường dẫn file hoặc URL http(s): ffmpeg tua qua HTTP, không cần tải nguyên phim
	if end_ms is not None:
		cmd += ["-t", f"{(end_ms - start_ms) / 1000:.3f}"]
	cmd += [
		"-vf", "scale=-2:480", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
		"-c:a", "aac", "-b:a", "96k", "-ac", "2", "-sn", "-map", "0:v:0", "-map", "0:a:0",
		"-movflags", "+faststart", str(dest),
	]
	subprocess.run(cmd, check=True)
	# ffmpeg thoát 0 dù không mã hoá được khung hình nào (vd tua qua HTTP vào file không có index) — bắt lỗi ở đây.
	if dest.stat().st_size < 100_000:
		sys.exit("ffmpeg không tạo được video (file rỗng). Tải phim về máy rồi truyền đường dẫn file cục bộ cho --video.")


def stamp(ms: int) -> str:
	total = ms // 1000
	return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


async def ingest(args: argparse.Namespace) -> None:
	start_ms = parse_time(args.start) if args.start else 0
	end_ms = parse_time(args.end) if args.end else None
	cues = parse_srt(read_text(args.srt))
	if not cues:
		sys.exit("Không đọc được cue nào từ file .srt — kiểm tra lại định dạng/đường dẫn.")
	sentences = merge_cues(clip_cues(cues, start_ms, end_ms))
	if not sentences:
		sys.exit("Không có lời thoại nào trong khoảng --start/--end đã chọn.")

	filename = f"{slugify(args.title)}.mp4"
	dest = video_dir() / filename
	print(f"nén video -> {dest.name} ...", flush=True)
	await asyncio.to_thread(transcode, args.video, dest, start_ms, end_ms)

	async with get_session_factory()() as session:
		await replace_video_source(
			session, args.title, args.platform, filename, [(text, s, e) for s, e, text in sentences]
		)
		await session.commit()
	print(f"xong: {dest.stat().st_size / 1024 / 1024:.1f} MB, {len(cues)} cue -> {len(sentences)} câu đã đánh chỉ mục")

	found = [
		(idiom, s, text)
		for idiom in COMMON_IDIOMS
		for s, _e, text in sentences
		if re.search(rf"\b{re.escape(idiom)}\b", text, re.IGNORECASE)
	]
	print("\nIdiom có trong đoạn này (gợi ý cụm để demo):" if found else "\nKhông thấy idiom phổ biến nào trong đoạn này.")
	for idiom, s, text in found[:30]:
		print(f'  "{idiom}" @ {stamp(s)}  {text[:100]}')


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("--video", required=True)
	parser.add_argument("--srt", required=True)
	parser.add_argument("--title", required=True)
	parser.add_argument("--start", help="đầu đoạn cắt: giây, MM:SS hoặc HH:MM:SS (mặc định: từ đầu)")
	parser.add_argument("--end", help="cuối đoạn cắt (mặc định: hết phim)")
	parser.add_argument("--platform", default="film")
	# psycopg async không chạy được trên ProactorEventLoop mặc định của Windows.
	asyncio.run(ingest(parser.parse_args()), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
