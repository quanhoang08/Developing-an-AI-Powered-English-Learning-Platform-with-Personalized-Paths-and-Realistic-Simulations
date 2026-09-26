// Ghi âm micro và xuất thẳng WAV PCM 16-bit 16kHz mono. Backend cần đúng định dạng này cho
// Azure Pronunciation Assessment (MediaRecorder chỉ ra webm/opus, sẽ buộc backend phải có
// ffmpeg để chuyển đổi), nên mã hoá WAV ngay ở trình duyệt.

const TARGET_SAMPLE_RATE = 16000;

export interface WavRecording {
  // Dừng ghi và trả về file WAV; null nếu không thu được mẫu nào.
  stop: () => Promise<Blob | null>;
  // Huỷ, bỏ dữ liệu đã thu.
  cancel: () => void;
}

function downsample(samples: Float32Array, inputRate: number): Float32Array {
  if (inputRate === TARGET_SAMPLE_RATE) return samples;
  const ratio = inputRate / TARGET_SAMPLE_RATE;
  const length = Math.floor(samples.length / ratio);
  const result = new Float32Array(length);
  for (let index = 0; index < length; index++) {
    const position = index * ratio;
    const lower = Math.floor(position);
    const upper = Math.min(lower + 1, samples.length - 1);
    result[index] = samples[lower] + (samples[upper] - samples[lower]) * (position - lower);
  }
  return result;
}

function encodeWav(samples: Float32Array): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeText = (offset: number, text: string) => {
    for (let index = 0; index < text.length; index++) view.setUint8(offset + index, text.charCodeAt(index));
  };
  writeText(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, TARGET_SAMPLE_RATE, true);
  view.setUint32(28, TARGET_SAMPLE_RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let index = 0; index < samples.length; index++) {
    const clamped = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(44 + index * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export async function startWavRecording(): Promise<WavRecording> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  const AudioContextClass: typeof AudioContext =
    window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const context = new AudioContextClass({ sampleRate: TARGET_SAMPLE_RATE });
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(4096, 1, 1);
  const chunks: Float32Array[] = [];

  processor.onaudioprocess = (event) => {
    chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
  };
  source.connect(processor);
  processor.connect(context.destination);

  const release = () => {
    processor.onaudioprocess = null;
    processor.disconnect();
    source.disconnect();
    stream.getTracks().forEach((track) => track.stop());
    void context.close();
  };

  return {
    stop: async () => {
      const inputRate = context.sampleRate;
      release();
      const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
      if (total === 0) return null;
      const merged = new Float32Array(total);
      let offset = 0;
      for (const chunk of chunks) {
        merged.set(chunk, offset);
        offset += chunk.length;
      }
      return encodeWav(downsample(merged, inputRate));
    },
    cancel: release,
  };
}
