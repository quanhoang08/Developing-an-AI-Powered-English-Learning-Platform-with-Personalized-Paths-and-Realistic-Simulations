// Offscreen document (MV3 không cho service worker dùng Web Audio): nhận streamId của tabCapture, thu âm thanh tab,
// đổi sang PCM16 16kHz và gửi lên backend (/api/extension/captions) theo giao thức của caption_service.
// Phụ đề nhận về được chuyển cho background.js, nơi chuyển tiếp cho content script của tab.
const INPUT_RATE = 16000;
const SYSTEM_SOURCE = 1; // byte đầu mỗi frame: 0 = mic, 1 = âm thanh hệ thống/tab (xem caption_service)

let session = null;

function report(message) {
  chrome.runtime.sendMessage(message).catch(() => {});
}

// Trung bình theo cửa sổ: đủ cho nhận dạng giọng nói, rẻ hơn lọc FIR.
function downsample(samples, inputRate) {
  if (inputRate === INPUT_RATE) return samples;
  const ratio = inputRate / INPUT_RATE;
  const out = new Float32Array(Math.floor(samples.length / ratio));
  for (let index = 0; index < out.length; index++) {
    const start = Math.floor(index * ratio);
    const end = Math.min(samples.length, Math.floor((index + 1) * ratio));
    let sum = 0;
    for (let i = start; i < end; i++) sum += samples[i];
    out[index] = sum / Math.max(1, end - start);
  }
  return out;
}

function toTaggedPcm16(samples) {
  const out = new Uint8Array(1 + samples.length * 2);
  out[0] = SYSTEM_SOURCE;
  const view = new DataView(out.buffer);
  for (let index = 0; index < samples.length; index++) {
    const clamped = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(1 + index * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  }
  return out.buffer;
}

function stop() {
  if (!session) return;
  const { socket, stream, context, processor } = session;
  session = null;
  processor.onaudioprocess = null;
  processor.disconnect();
  stream.getTracks().forEach((track) => track.stop());
  void context.close();
  if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "end" }));
  socket.close();
}

async function start({ streamId, wsUrl, token }) {
  stop();
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: streamId } },
  });
  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  // tabCapture làm tab câm tiếng: phát lại ra loa để người dùng vẫn nghe video như bình thường.
  source.connect(context.destination);
  const processor = context.createScriptProcessor(4096, 1, 1);
  const socket = new WebSocket(wsUrl);
  socket.binaryType = "arraybuffer";
  session = { socket, stream, context, processor, ready: false };
  const mine = session;

  processor.onaudioprocess = (event) => {
    if (!mine.ready || socket.readyState !== WebSocket.OPEN) return;
    socket.send(toTaggedPcm16(downsample(event.inputBuffer.getChannelData(0), context.sampleRate)));
  };
  source.connect(processor);
  processor.connect(context.destination); // ScriptProcessor chỉ chạy khi nối vào đích; đầu ra của nó im lặng.

  socket.onopen = () => socket.send(JSON.stringify({ token, provider: "auto" }));
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "ready") {
      mine.ready = true;
      report({ type: "TAB_STATUS", state: "ready", engine: message.engine });
    } else if (message.type === "caption") {
      report({ type: "TAB_CAPTION", caption: message });
    } else if (message.type === "engine") {
      report({ type: "TAB_STATUS", state: "ready", engine: message.name, fellBack: true });
    } else if (message.type === "error") {
      report({ type: "TAB_STATUS", state: "error", code: message.code });
    }
  };
  socket.onerror = () => report({ type: "TAB_STATUS", state: "error", code: "unreachable" });
  socket.onclose = () => {
    if (session === mine) {
      stop();
      report({ type: "TAB_STATUS", state: "closed" });
    }
  };
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.target !== "offscreen") return;
  if (message.type === "OFFSCREEN_START") {
    start(message).catch((error) => report({ type: "TAB_STATUS", state: "error", code: "capture_failed", detail: error.message }));
  } else if (message.type === "OFFSCREEN_STOP") {
    stop();
  }
});
