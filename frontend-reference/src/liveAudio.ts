// Âm thanh cho gọi thoại 2 chiều (Gemini Live): thu micro liên tục thành PCM16 16kHz gửi theo luồng,
// và phát nối tiếp các mẩu PCM16 24kHz Gemini trả về (dừng ngay được khi người học nói chen).
import { downsample } from "./wavRecorder";

const INPUT_RATE = 16000;
const OUTPUT_RATE = 24000;

type AudioContextCtor = typeof AudioContext;
const AudioContextClass = (): AudioContextCtor =>
  window.AudioContext || (window as unknown as { webkitAudioContext: AudioContextCtor }).webkitAudioContext;

export function floatToPcm16(samples: Float32Array): ArrayBuffer {
  const out = new Int16Array(samples.length);
  for (let index = 0; index < samples.length; index++) {
    const clamped = Math.max(-1, Math.min(1, samples[index]));
    out[index] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  }
  return out.buffer;
}

export function pcm16ToFloat(buffer: ArrayBuffer): Float32Array {
  const input = new Int16Array(buffer);
  const out = new Float32Array(input.length);
  for (let index = 0; index < input.length; index++) out[index] = input[index] / 0x8000;
  return out;
}

export interface LiveMic {
  stop: () => void;
}

// Cùng cách thu với wavRecorder (ScriptProcessor), nhưng đẩy từng mẩu ~128ms đi ngay thay vì gom lại.
export async function startLiveMic(onChunk: (pcm: ArrayBuffer) => void): Promise<LiveMic> {
  // echoCancellation quan trọng: không có nó, giọng AI lọt lại vào mic và Gemini tưởng người học đang nói chen.
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const Ctor = AudioContextClass();
  const context = new Ctor({ sampleRate: INPUT_RATE });
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(2048, 1, 1);
  processor.onaudioprocess = (event) => {
    onChunk(floatToPcm16(downsample(new Float32Array(event.inputBuffer.getChannelData(0)), context.sampleRate)));
  };
  source.connect(processor);
  processor.connect(context.destination);
  if (context.state === "suspended") await context.resume().catch(() => undefined);
  return {
    stop: () => {
      processor.onaudioprocess = null;
      processor.disconnect();
      source.disconnect();
      stream.getTracks().forEach((track) => track.stop());
      void context.close();
    },
  };
}

export class PcmPlayer {
  private context: AudioContext;
  private analyser: AnalyserNode;
  private samples = new Uint8Array(512);
  private nextStart = 0;
  private sources = new Set<AudioBufferSourceNode>();

  constructor() {
    const Ctor = AudioContextClass();
    this.context = new Ctor({ sampleRate: OUTPUT_RATE });
    this.analyser = this.context.createAnalyser();
    this.analyser.fftSize = this.samples.length;
    this.analyser.connect(this.context.destination);
  }

  // Gọi trong thao tác click để trình duyệt cho phép phát âm thanh (chính sách autoplay).
  resume(): Promise<void> {
    return this.context.resume().catch(() => undefined);
  }

  play(pcm: ArrayBuffer): void {
    const data = pcm16ToFloat(pcm);
    if (data.length === 0) return;
    const buffer = this.context.createBuffer(1, data.length, OUTPUT_RATE);
    buffer.copyToChannel(data, 0);
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.analyser);
    // Xếp nối đuôi mẩu trước; đệm 50ms ở mẩu đầu để mạng chập chờn không làm giọng bị vấp.
    const startAt = Math.max(this.context.currentTime + 0.05, this.nextStart);
    source.start(startAt);
    this.nextStart = startAt + buffer.duration;
    this.sources.add(source);
    source.onended = () => this.sources.delete(source);
  }

  // Người học nói chen (Gemini báo "interrupted"): bỏ toàn bộ phần giọng AI đang chờ phát.
  interrupt(): void {
    this.sources.forEach((source) => {
      source.onended = null;
      source.stop();
    });
    this.sources.clear();
    this.nextStart = 0;
  }

  get speaking(): boolean {
    return this.sources.size > 0;
  }

  // Biên độ 0..1 hiện tại cho mèo nhép miệng (giống SpeakingView).
  level(): number {
    this.analyser.getByteTimeDomainData(this.samples);
    let sum = 0;
    for (let index = 0; index < this.samples.length; index++) {
      const centered = (this.samples[index] - 128) / 128;
      sum += centered * centered;
    }
    return Math.min(1, Math.sqrt(sum / this.samples.length) * 6);
  }

  close(): void {
    this.interrupt();
    void this.context.close();
  }
}
