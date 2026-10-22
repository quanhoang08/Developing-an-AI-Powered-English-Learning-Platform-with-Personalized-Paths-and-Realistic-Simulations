import numpy as np

from app.services.echo_gate import FRAME, EchoGate

CHUNK = 6 * FRAME  # ~120 ms, cỡ frame mic của trình duyệt
FRAMES = 300  # 6 giây


def _speech(seed: int, scale: float = 0.2, delay_frames: int = 0) -> np.ndarray:
	"""Nhiễu có đường bao to/nhỏ ngẫu nhiên theo từng ~200 ms, giống nhịp lên xuống của tiếng nói."""
	rng = np.random.default_rng(seed)
	envelope = np.repeat(rng.uniform(0.02, 1.0, FRAMES // 10 + 1), 10)[:FRAMES]
	envelope = np.roll(envelope, delay_frames)
	carrier = np.random.default_rng(seed + 1000).normal(0, 1, FRAMES * FRAME)
	return carrier * np.repeat(envelope, FRAME) * scale


def _pcm(signal: np.ndarray) -> bytes:
	return (np.clip(signal, -1, 1) * 32767).astype("<i2").tobytes()


def _run(system: np.ndarray, mic: np.ndarray) -> float:
	"""Tỉ lệ mẫu mic còn lại (khác 0) ở nửa sau của phiên, khi cửa sổ tương quan đã đầy."""
	gate = EchoGate()
	system_pcm, mic_pcm = _pcm(system), _pcm(mic)
	kept = []
	for start in range(0, len(mic_pcm), CHUNK * 2):
		gate.push_system(system_pcm[start : start + CHUNK * 2])
		kept.append(gate.filter_mic(mic_pcm[start : start + CHUNK * 2]))
	out = np.frombuffer(b"".join(kept), dtype="<i2")
	return float(np.mean(out[len(out) // 2 :] != 0))


def test_mic_echo_of_system_audio_is_silenced():
	system = _speech(1)
	echo = _speech(1, scale=0.05, delay_frames=3) + np.random.default_rng(5).normal(0, 0.002, FRAMES * FRAME)
	assert _run(system, echo) < 0.1


def test_independent_speech_passes():
	assert _run(_speech(1), _speech(2)) > 0.9


def test_mic_only_session_passes_everything():
	gate = EchoGate()
	mic = _pcm(_speech(4))
	step = CHUNK * 2
	assert b"".join(gate.filter_mic(mic[i : i + step]) for i in range(0, len(mic), step)) == mic


def test_empty_and_odd_length_chunks_keep_their_length():
	gate = EchoGate()
	assert gate.filter_mic(b"") == b""
	assert len(gate.filter_mic(bytes(641))) == 641
	gate.push_system(b"")
	gate.push_system(bytes(7))
	assert len(gate.filter_mic(bytes(641))) == 641


def test_mic_is_heard_again_after_the_echo_stops():
	frames = 500
	rng = np.random.default_rng(8)

	def burst_noise(seed: int) -> np.ndarray:
		envelope = np.repeat(np.random.default_rng(seed).uniform(0.02, 1.0, frames // 10 + 1), 10)[:frames]
		return np.random.default_rng(seed + 50).normal(0, 1, frames * FRAME) * np.repeat(envelope, FRAME) * 0.2

	system = burst_noise(1)
	system[200 * FRAME :] = 0  # video dừng sau 4 giây
	mic = burst_noise(1) * 0.25 + rng.normal(0, 0.002, frames * FRAME)  # vọng của video, nhỏ hơn
	mic[200 * FRAME :] = burst_noise(2)[200 * FRAME :]  # người học nói tiếp
	gate = EchoGate()
	system_pcm, mic_pcm = _pcm(system), _pcm(mic)
	out = bytearray()
	step = CHUNK * 2
	for start in range(0, len(mic_pcm), step):
		gate.push_system(system_pcm[start : start + step])
		out += gate.filter_mic(mic_pcm[start : start + step])
	tail = np.frombuffer(bytes(out), dtype="<i2")[400 * FRAME :]
	assert float(np.mean(tail != 0)) > 0.8


def test_silent_system_never_gates_mic():
	assert _run(np.zeros(FRAMES * FRAME), _speech(3)) > 0.9
