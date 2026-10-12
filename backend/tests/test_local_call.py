# Gọi thoại local (F22, nhánh Ollama): các phần logic thuần, không cần model/GPU/mạng.
import numpy as np

from app.services.local_call_service import (
	EnergyVad,
	clean_for_speech,
	resample_pcm16,
	split_sentences,
	trim_history,
)

FRAME = 2048  # mẫu/frame mic (~128ms ở 16kHz)


def _frame(amplitude: int) -> bytes:
	t = np.arange(FRAME)
	return (amplitude * np.sin(2 * np.pi * 220 * t / 16000)).astype(np.int16).tobytes()


def _run(vad: EnergyVad, frames: list[bytes], strict: bool = False) -> list[tuple]:
	return [event for frame in frames for event in vad.feed(frame, strict)]


def test_vad_cuts_one_utterance_after_trailing_silence():
	vad = EnergyVad()
	events = _run(vad, [_frame(0)] * 5 + [_frame(6000)] * 8 + [_frame(0)] * 8)
	assert [e[0] for e in events] == ["start", "utterance"]
	# Có preroll (không mất âm đầu) nhưng không kéo dài quá nhiều im lặng.
	assert 8 * FRAME * 2 <= len(events[1][1]) <= (8 + 2 + 6) * FRAME * 2


def test_vad_ignores_short_click_and_silence():
	vad = EnergyVad()
	assert _run(vad, [_frame(0)] * 10) == []
	# 2 frame lớn rồi im: vẫn là "start" nhưng quá ngắn (< min_speech) nên bị bỏ chứ không đưa đi nhận dạng.
	events = _run(vad, [_frame(6000)] * 2 + [_frame(0)] * 8)
	assert [e[0] for e in events] == ["start", "discard"]
	assert _run(EnergyVad(), [_frame(6000)]) == []  # 1 frame không đủ để bắt đầu


def test_vad_strict_mode_ignores_echo_but_hears_real_barge_in():
	echo, speech = _frame(600), _frame(9000)  # tiếng vọng nhỏ so với người thật nói chen
	assert _run(EnergyVad(), [echo] * 6, strict=True) == []
	assert [e[0] for e in _run(EnergyVad(), [speech] * 4, strict=True)] == ["start"]


def test_split_sentences_streams_complete_sentences_only():
	assert split_sentences("Hi! How are you") == (["Hi!"], "How are you")
	assert split_sentences("One. Two? Thr") == (["One.", "Two?"], "Thr")
	assert split_sentences("No end yet") == ([], "No end yet")


def test_clean_for_speech_drops_markdown():
	assert clean_for_speech("**Great** job! `ok`") == "Great job! ok"


def test_resample_changes_length_by_rate_ratio():
	pcm = np.zeros(22050, dtype=np.int16).tobytes()
	assert len(resample_pcm16(pcm, 22050, 24000)) // 2 == 24000
	assert resample_pcm16(pcm, 24000, 24000) == pcm


def test_trim_history_keeps_system_prompt():
	history = [{"role": "system", "content": "S"}] + [{"role": "user", "content": str(i)} for i in range(50)]
	trimmed = trim_history(history)
	assert trimmed[0]["content"] == "S" and len(trimmed) == 21 and trimmed[-1]["content"] == "49"
