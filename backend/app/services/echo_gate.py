# Chống tiếng vọng cho phụ đề trực tiếp: không đeo tai nghe thì mic thu lại âm thanh từ loa, nên cùng một câu
# bị nhận dạng 2 lần (mic + âm thanh hệ thống). Dạng sóng thô lệch pha/méo qua phòng, còn đường bao độ to (RMS mỗi
# 20 ms) thì giữ được hình dạng: nếu đường bao mic bám theo đường bao hệ thống (trễ vài chục ms) thì đoạn mic là
# vọng và bị thay bằng im lặng. Giọng của chính người học không tương quan với âm thanh hệ thống nên đi qua.
# ponytail: giả định hai luồng bắt đầu cùng lúc và chạy liên tục (đúng với 2 AudioContext mở cùng lượt bấm);
# không có look-ahead nên 1-2 âm tiết đầu của vọng có thể lọt trước khi tương quan đủ cao.
from collections import deque

import numpy as np

RATE = 16000
FRAME = RATE // 50  # 20 ms
WINDOW_FRAMES = 100  # cửa sổ tương quan 2 giây (1 giây thì đường bao độc lập hay trùng ngẫu nhiên)
LAGS = range(-3, 11)  # mic trễ so với hệ thống từ -60 ms đến +200 ms
SYSTEM_ACTIVE_RMS = 0.004
ECHO_CORRELATION = 0.6
HOLD_FRAMES = 30  # giữ trạng thái "vọng" thêm 0.6 s sau lần phát hiện cuối
_HISTORY_FRAMES = WINDOW_FRAMES + max(LAGS) + 2


class _Envelope:
	def __init__(self) -> None:
		self.rest = np.zeros(0, dtype=np.float32)
		self.rms: deque[float] = deque(maxlen=_HISTORY_FRAMES)
		self.count = 0  # tổng số frame đã nhận; frame cuối có chỉ số count - 1

	def push(self, pcm: bytes) -> None:
		samples = np.concatenate([self.rest, np.frombuffer(pcm[: len(pcm) // 2 * 2], dtype=np.int16) / 32768.0])
		whole = len(samples) // FRAME * FRAME
		for offset in range(0, whole, FRAME):
			self.rms.append(float(np.sqrt(np.mean(samples[offset : offset + FRAME] ** 2))))
			self.count += 1
		self.rest = samples[whole:].astype(np.float32)

	def window(self, end: int, length: int) -> np.ndarray | None:
		"""RMS của frame [end - length + 1, end]; None nếu chưa đủ dữ liệu."""
		start = end - length + 1
		oldest = self.count - len(self.rms)
		if start < oldest or end >= self.count:
			return None
		return np.array([self.rms[i - oldest] for i in range(start, end + 1)])


class EchoGate:
	def __init__(self) -> None:
		self.system = _Envelope()
		self.mic = _Envelope()
		self.hold = 0

	def push_system(self, pcm: bytes) -> None:
		self.system.push(pcm)

	def filter_mic(self, pcm: bytes) -> bytes:
		"""Trả lại chính đoạn mic, hoặc im lặng cùng độ dài nếu nó là vọng của âm thanh hệ thống."""
		before = self.mic.count
		self.mic.push(pcm)
		frames = self.mic.count - before
		if frames and self._is_echo():
			self.hold = HOLD_FRAMES
		else:
			self.hold = max(0, self.hold - frames)
		return bytes(len(pcm)) if self.hold > 0 else pcm

	def _is_echo(self) -> bool:
		end = self.mic.count - 1
		mic = self.mic.window(end, WINDOW_FRAMES)
		if mic is None or mic.std() < 1e-6:
			return False
		best = 0.0
		for lag in LAGS:
			system = self.system.window(end - lag, WINDOW_FRAMES)
			# Hệ thống phải đang phát tiếng thì mới có thể là nguồn của vọng.
			if system is None or system.mean() < SYSTEM_ACTIVE_RMS or system.std() < 1e-6:
				continue
			best = max(best, float(np.corrcoef(np.log10(mic + 1e-4), np.log10(system + 1e-4))[0, 1]))
		return best >= ECHO_CORRELATION
