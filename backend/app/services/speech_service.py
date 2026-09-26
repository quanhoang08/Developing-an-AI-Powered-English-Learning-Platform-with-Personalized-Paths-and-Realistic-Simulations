# Điểm gom duy nhất cho STT/TTS (feature-listening.md mục 4) — router/feature service
# Listening/Speaking không được gọi thẳng Azure/ElevenLabs SDK, luôn đi qua module này, cùng
# nguyên tắc "1 điểm gọi duy nhất" đã áp dụng cho Gemini ở llm_service._call_gemini.
import base64
import io
import json
import shutil
import subprocess
import tempfile
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.core.config import get_settings

# Gọi Azure Speech qua REST (httpx) thay vì azure-cognitiveservices-speech: SDK native đó
# segfault trên Python 3.14 (môi trường dev), còn REST không phụ thuộc thư viện native và
# Fast Transcription nhận trực tiếp mp3/wav/ogg/webm nên không cần ffmpeg cho STT.
_AZURE_TIMEOUT_SECONDS = 120
_AZURE_STT_RETRIES = 1


class SpeechServiceError(Exception):
	"""Azure Speech/ElevenLabs lỗi HOẶC chưa cấu hình key — router bắt để trả 503 rõ ràng,
	cùng pattern với AIServiceError của llm_service.py."""


def slice_wav_segment(source_path: str, start_ms: int, end_ms: int, dest_path: str) -> None:
	"""Cắt 1 đoạn PCM WAV theo mốc thời gian mili giây, ghi ra file mới tại dest_path — dùng
	cho Dictation (feature-listening.md mục 3.3 bước 2: "trả về audio đoạn đó cho client").

	Chỉ hỗ trợ WAV (PCM), không cần ffmpeg — khớp chuẩn hoá bắt buộc "PCM WAV 16kHz mono"
	trước khi vào Azure Speech SDK (mục 4). Khi Podcast TTS thật (ElevenLabs, thường trả MP3)
	được nối vào, bước chuẩn hoá sang WAV phải chạy trước khi audio tới được hàm này.
	"""
	source_path = ensure_wav(source_path)
	with wave.open(source_path, "rb") as source:
		params = source.getparams()
		frame_rate = params.framerate
		start_frame = min(int(start_ms / 1000 * frame_rate), params.nframes)
		end_frame = min(int(end_ms / 1000 * frame_rate), params.nframes)
		source.setpos(start_frame)
		frames = source.readframes(max(0, end_frame - start_frame))

	Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
	with wave.open(dest_path, "wb") as dest:
		dest.setparams(params)
		dest.writeframes(frames)


def _pcm_to_wav_bytes(pcm: bytes, sample_rate: int = 16000) -> bytes:
	buffer = io.BytesIO()
	with wave.open(buffer, "wb") as wav:
		wav.setnchannels(1)
		wav.setsampwidth(2)
		wav.setframerate(sample_rate)
		wav.writeframes(pcm)
	return buffer.getvalue()


def synthesize_speech(text: str, voice_id: str) -> bytes:
	"""TTS qua ElevenLabs cho podcast nguồn .docx (feature-listening.md mục 1.3 bước 2).

	Xin thẳng PCM 16kHz rồi đóng gói WAV — không cần ffmpeg và khớp chuẩn PCM WAV 16kHz mono
	của mục 4.
	"""
	settings = get_settings()
	if not settings.elevenlabs_api_key:
		raise SpeechServiceError("elevenlabs_not_configured")
	try:
		response = httpx.post(
			f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
			params={"output_format": "pcm_16000"},
			headers={"xi-api-key": settings.elevenlabs_api_key},
			json={"text": text, "model_id": "eleven_multilingual_v2"},
			timeout=_AZURE_TIMEOUT_SECONDS,
		)
	except httpx.HTTPError as error:
		raise SpeechServiceError("elevenlabs_unreachable") from error
	if response.status_code in (401, 403):
		raise SpeechServiceError("elevenlabs_auth_failed")
	if response.status_code != 200:
		raise SpeechServiceError("elevenlabs_tts_failed")
	return _pcm_to_wav_bytes(response.content)


@dataclass
class TranscriptWord:
	text: str
	start_ms: int
	end_ms: int


@dataclass
class TranscriptResult:
	text: str
	duration_ms: int
	words: list[TranscriptWord] = field(default_factory=list)


def _azure_region_and_key() -> tuple[str, str]:
	settings = get_settings()
	if not settings.azure_speech_key:
		raise SpeechServiceError("azure_speech_not_configured")
	return settings.azure_speech_region, settings.azure_speech_key


def ensure_wav(source_path: str) -> str:
	"""Trả về đường dẫn WAV PCM tương ứng — file .wav giữ nguyên, định dạng khác (mp3/m4a/
	webm/ogg) được ffmpeg chuẩn hoá sang PCM WAV 16kHz mono (feature-listening.md mục 4)."""
	if Path(source_path).suffix.lower() == ".wav":
		return source_path
	ffmpeg = shutil.which("ffmpeg")
	if ffmpeg is None:
		raise SpeechServiceError("ffmpeg_not_available")
	dest = Path(tempfile.gettempdir()) / f"{Path(source_path).stem}_16k.wav"
	result = subprocess.run(
		[ffmpeg, "-y", "-i", source_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(dest)],
		capture_output=True,
	)
	if result.returncode != 0:
		raise SpeechServiceError("audio_conversion_failed")
	return str(dest)


def _parse_fast_transcription(payload: dict) -> TranscriptResult:
	words: list[TranscriptWord] = []
	for phrase in payload.get("phrases", []):
		for word in phrase.get("words", []):
			words.append(
				TranscriptWord(
					text=word["text"],
					start_ms=int(word["offsetMilliseconds"]),
					end_ms=int(word["offsetMilliseconds"]) + int(word["durationMilliseconds"]),
				)
			)
	combined = " ".join(item.get("text", "") for item in payload.get("combinedPhrases", []))
	return TranscriptResult(
		text=combined.strip(), duration_ms=int(payload.get("durationMilliseconds", 0)), words=words
	)


def transcribe_audio(audio_path: str, locale: str = "en-US") -> TranscriptResult:
	"""STT qua Azure Fast Transcription (feature-listening.md mục 1.3 bước 3): nhận cả file
	(≤ 2 giờ/300MB) một lần, trả text + timestamp cấp TỪ — đúng đơn vị transcript_segments.

	Đồng bộ (httpx) — caller async phải bọc run_in_threadpool. Lỗi mạng/5xx retry 1 lần
	(feature-speaking.md mục 1.4a), vẫn lỗi thì SpeechServiceError.
	"""
	region, key = _azure_region_and_key()
	audio_bytes = Path(audio_path).read_bytes()
	url = f"https://{region}.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe"
	definition = json.dumps({"locales": [locale]})

	last_error = "azure_stt_failed"
	for attempt in range(_AZURE_STT_RETRIES + 1):
		try:
			response = httpx.post(
				url,
				params={"api-version": "2024-11-15"},
				headers={"Ocp-Apim-Subscription-Key": key},
				files={
					"audio": (Path(audio_path).name, audio_bytes),
					"definition": (None, definition, "application/json"),
				},
				timeout=_AZURE_TIMEOUT_SECONDS,
			)
		except httpx.HTTPError:
			last_error = "azure_stt_unreachable"
		else:
			if response.status_code == 200:
				return _parse_fast_transcription(response.json())
			if response.status_code in (401, 403):
				raise SpeechServiceError("azure_speech_auth_failed")
			if response.status_code < 500 and response.status_code != 429:
				raise SpeechServiceError("azure_stt_rejected_audio")
			last_error = "azure_stt_failed"
		if attempt < _AZURE_STT_RETRIES:
			time.sleep(1)
	raise SpeechServiceError(last_error)


def transcribe_with_fallback(audio_path: str, locale: str = "en-US") -> tuple[str, str]:
	"""STT Azure ưu tiên (đã retry 1 lần trong transcribe_audio), lỗi thì dự phòng Gemini
	(feature-speaking.md mục 1.4a, thay Whisper vì không có OpenAI key). Trả (text, provider);
	cả hai đều lỗi -> SpeechServiceError. Audio im lặng KHÔNG phải lỗi, không kích hoạt fallback."""
	try:
		return transcribe_audio(audio_path, locale).text, "azure"
	except SpeechServiceError as azure_error:
		# Import muộn: llm_service kéo SDK Google, chỉ cần khi thật sự phải fallback.
		from app.services import llm_service

		try:
			extension = Path(audio_path).suffix.lower()
			text = llm_service.transcribe_audio_with_gemini(Path(audio_path).read_bytes(), extension)
		except Exception as gemini_error:
			raise SpeechServiceError("stt_all_providers_failed") from gemini_error
		return text, "gemini"


@dataclass
class PronunciationResult:
	score: float
	accuracy: float
	fluency: float
	completeness: float
	weak_words: list[str] = field(default_factory=list)


def assess_pronunciation(audio_path: str, locale: str = "en-US") -> PronunciationResult:
	"""Azure Pronunciation Assessment trên CHÍNH audio gốc (feature-speaking.md mục 1.3 nhánh B).

	Chấm không kịch bản (ReferenceText rỗng) nên chạy song song được với STT. Không có
	fallback provider (mục 1.4b) — lỗi thì raise SpeechServiceError, caller ghi cờ lỗi.
	"""
	region, key = _azure_region_and_key()
	wav_path = ensure_wav(audio_path)
	assessment = {
		"ReferenceText": "",
		"GradingSystem": "HundredMark",
		"Granularity": "Word",
		"Dimension": "Comprehensive",
	}
	try:
		response = httpx.post(
			f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1",
			params={"language": locale, "format": "detailed"},
			headers={
				"Ocp-Apim-Subscription-Key": key,
				"Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
				"Pronunciation-Assessment": base64.b64encode(json.dumps(assessment).encode()).decode(),
			},
			content=Path(wav_path).read_bytes(),
			timeout=_AZURE_TIMEOUT_SECONDS,
		)
	except httpx.HTTPError as error:
		raise SpeechServiceError("azure_pronunciation_unreachable") from error
	if response.status_code in (401, 403):
		raise SpeechServiceError("azure_speech_auth_failed")
	if response.status_code != 200:
		raise SpeechServiceError("azure_pronunciation_failed")
	payload = response.json()
	if payload.get("RecognitionStatus") != "Success" or not payload.get("NBest"):
		raise SpeechServiceError("azure_pronunciation_no_speech")
	best = payload["NBest"][0]
	weak_words = [
		word["Word"] for word in best.get("Words", []) if word.get("AccuracyScore", 100) < 70
	]
	return PronunciationResult(
		score=float(best["PronScore"]),
		accuracy=float(best["AccuracyScore"]),
		fluency=float(best["FluencyScore"]),
		completeness=float(best["CompletenessScore"]),
		weak_words=weak_words,
	)


def synthesize_azure_speech(text: str, voice: str | None = None) -> bytes:
	"""TTS qua Azure Speech, trả PCM WAV 16kHz mono. Dùng cho audio phản hồi Speaking và làm
	nguồn audio thật khi test STT; ElevenLabs (synthesize_speech) vẫn là TTS Podcast theo spec."""
	region, key = _azure_region_and_key()
	settings = get_settings()
	voice = voice or settings.azure_speech_default_voice
	locale = "-".join(voice.split("-")[:2])
	escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
	ssml = (
		f"<speak version='1.0' xml:lang='{locale}'><voice name='{voice}'>{escaped}</voice></speak>"
	)
	try:
		response = httpx.post(
			f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
			headers={
				"Ocp-Apim-Subscription-Key": key,
				"Content-Type": "application/ssml+xml",
				"X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm",
			},
			content=ssml.encode("utf-8"),
			timeout=_AZURE_TIMEOUT_SECONDS,
		)
	except httpx.HTTPError as error:
		raise SpeechServiceError("azure_tts_unreachable") from error
	if response.status_code in (401, 403):
		raise SpeechServiceError("azure_speech_auth_failed")
	if response.status_code != 200:
		raise SpeechServiceError("azure_tts_failed")
	return response.content
