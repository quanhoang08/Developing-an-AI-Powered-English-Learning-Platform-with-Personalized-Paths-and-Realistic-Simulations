// Phụ đề trực tiếp + dịch tiếng Việt: thu âm thanh tab/cửa sổ đang phát (video, podcast, họp) và/hoặc micro,
// gửi lên backend (/api/speaking/captions) và hiện câu tiếng Anh kèm bản dịch. Backend tự lọc tiếng vọng
// của loa vào mic (echo_gate), nên mở cả hai nguồn khi không đeo tai nghe vẫn không bị lặp phụ đề.
import React, { useEffect, useRef, useState } from "react";
import { AlertCircle, Captions, Loader2, Square } from "lucide-react";
import { captionSocketUrl, getAccessToken } from "../api";
import { LiveMic, startLiveMic, startSystemAudio, tagSource } from "../liveAudio";

type Status = "idle" | "connecting" | "live";

interface CaptionLine {
  key: string;
  source: "mic" | "system";
  text: string;
  translation: string | null;
  final: boolean;
}

const MAX_LINES = 200;

const ERROR_MESSAGES: Record<string, string> = {
  invalid_token: "Your sign-in expired. Please sign in again.",
  captions_not_configured: "Cloud captions aren't configured on this server.",
  captions_unavailable: "Live captions are unavailable right now. Please try again in a moment.",
  local_models_unavailable:
    "Couldn't load the offline speech model (the first run downloads it). Check your connection and try again.",
};

export const LiveCaptionsPanel: React.FC = () => {
  const [useSystem, setUseSystem] = useState(true);
  const [useMic, setUseMic] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const [lines, setLines] = useState<CaptionLine[]>([]);
  const [engine, setEngine] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const capturesRef = useRef<LiveMic[]>([]);
  const readyRef = useRef(false);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [lines]);

  const release = () => {
    readyRef.current = false;
    capturesRef.current.forEach((capture) => capture.stop());
    capturesRef.current = [];
  };

  const stop = () => {
    const socket = socketRef.current;
    // Bỏ socket cũ ngay: sự kiện đóng/tin nhắn muộn của nó (server mất vài trăm ms để dọn) không được đụng vào phiên bật lại ngay sau đó.
    socketRef.current = null;
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "end" }));
    socket?.close();
    release();
    setStatus("idle");
  };

  useEffect(
    () => () => {
      socketRef.current?.close();
      release();
    },
    [],
  );

  const upsert = (line: CaptionLine) =>
    setLines((current) => {
      const index = current.findIndex((item) => item.key === line.key);
      if (index === -1) return [...current, line].slice(-MAX_LINES);
      const next = [...current];
      next[index] = line;
      return next;
    });

  const start = async () => {
    if (!useSystem && !useMic) {
      setError("Pick at least one audio source.");
      return;
    }
    setError(null);
    setNotice(null);
    setEngine(null);
    setLines([]);
    setStatus("connecting");
    readyRef.current = false;
    // Chia sẻ màn hình/mic phải xin ngay trong thao tác click (trình duyệt hết hiệu lực "user activation" sau vài giây),
    // nên thu trước; chunk chỉ được gửi đi sau khi server báo ready (lần đầu tải model local có thể mất cả chục giây).
    // Socket chỉ được mở SAU khi thu xong: người dùng có thể mất vài giây chọn tab trong hộp chia sẻ, và nếu socket đã mở
    // trước đó thì sự kiện open trôi qua trước khi gán onopen, tin chào không bao giờ được gửi và server đóng sau 10 giây.
    let socket: WebSocket | null = null;
    const send = (source: 0 | 1) => (pcm: ArrayBuffer) => {
      if (readyRef.current && socket?.readyState === WebSocket.OPEN) socket.send(tagSource(source, pcm));
    };
    try {
      if (useSystem) capturesRef.current.push(await startSystemAudio(send(1), stop));
      if (useMic) capturesRef.current.push(await startLiveMic(send(0), false));
    } catch (failure) {
      release();
      setStatus("idle");
      setError(
        failure instanceof Error && failure.message === "no_system_audio"
          ? "No audio was shared. Choose a browser tab and tick “Share tab audio”."
          : "Couldn't start the audio capture. Allow access in your browser and try again.",
      );
      return;
    }
    const ws = new WebSocket(captionSocketUrl());
    socket = ws;
    ws.binaryType = "arraybuffer";
    socketRef.current = ws;
    ws.onopen = () => ws.send(JSON.stringify({ token: getAccessToken(), provider: "auto" }));
    ws.onmessage = (event) => {
      if (socketRef.current !== ws) return; // socket cũ đã bị thay thế
      const message = JSON.parse(event.data as string);
      if (message.type === "ready") {
        readyRef.current = true;
        setEngine(message.engine);
        setStatus("live");
      } else if (message.type === "caption") {
        upsert({
          key: `${message.source}-${message.id}`,
          source: message.source,
          text: message.text,
          translation: message.translation,
          final: message.final,
        });
      } else if (message.type === "engine") {
        setEngine(message.name);
        setNotice("Cloud captions dropped, so we switched to offline mode (slower, shows finished sentences only).");
      } else if (message.type === "error") {
        setError(ERROR_MESSAGES[message.code] ?? ERROR_MESSAGES.captions_unavailable);
      }
    };
    ws.onerror = () => {
      if (socketRef.current === ws) setError("Can't reach the Lumina server.");
    };
    ws.onclose = () => {
      if (socketRef.current !== ws) return;
      socketRef.current = null;
      release();
      setStatus("idle");
    };
  };

  return (
    <div className="space-y-4">
      <div className="rounded-3xl bg-paper-deep p-5 space-y-4">
        <div className="flex flex-wrap items-center gap-4 text-sm font-bold text-slate-700">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={useSystem} disabled={status !== "idle"} onChange={(e) => setUseSystem(e.target.checked)} />
            Video / tab audio
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={useMic} disabled={status !== "idle"} onChange={(e) => setUseMic(e.target.checked)} />
            Microphone
          </label>
          {engine && (
            <span className="rounded-full bg-white px-3 py-1 text-xs text-slate-600">
              {engine === "soniox" ? "Cloud captions" : "Offline captions"}
            </span>
          )}
          <button
            onClick={status === "idle" ? start : stop}
            disabled={status === "connecting"}
            className="ml-auto flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2 text-white disabled:opacity-60"
          >
            {status === "connecting" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : status === "live" ? (
              <Square className="h-4 w-4" />
            ) : (
              <Captions className="h-4 w-4" />
            )}
            {status === "idle" ? "Start captions" : status === "connecting" ? "Connecting…" : "Stop"}
          </button>
        </div>
        <p className="text-xs text-slate-500">
          Play an English video in another tab, then choose that tab and tick “Share tab audio”. With both sources on and no
          headphones, speaker echo in the microphone is filtered out automatically.
        </p>
      </div>

      {error && (
        <p role="alert" className="flex items-center gap-2 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </p>
      )}
      {notice && <p className="rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-800">{notice}</p>}

      <div className="max-h-[28rem] min-h-[10rem] space-y-3 overflow-y-auto rounded-3xl bg-white p-5">
        {lines.length === 0 && (
          <p className="text-sm italic text-slate-400">Captions and their Vietnamese translation appear here.</p>
        )}
        {lines.map((line) => (
          <div key={line.key} className={line.final ? "" : "opacity-60"}>
            <p className="text-base font-semibold text-slate-900">
              {line.source === "mic" && <span className="mr-2 text-xs font-bold text-indigo-600">YOU</span>}
              {line.text}
            </p>
            {line.translation && <p className="text-sm text-indigo-700">{line.translation}</p>}
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
};
