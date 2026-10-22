// Gọi thoại 2 chiều liên tục với AI (F22, Gemini Live): micro luôn mở, không bấm ghi/dừng theo lượt,
// AI trả lời gần như tức thì và người học nói chen được (AI dừng ngay). Backend chỉ làm cầu nối
// WebSocket tới Gemini; transcript lưu lại sau mỗi cuộc gọi để xem lại.
import React, { useEffect, useRef, useState } from "react";
import { AlertCircle, Headphones, Loader2, Phone, PhoneOff } from "lucide-react";
import {
  ChatProvider,
  getAccessToken,
  listLiveCalls,
  listScenarios,
  LiveCall,
  LiveCallLine,
  liveCallSocketUrl,
  Scenario,
} from "../api";
import { LiveMic, PcmPlayer, startLiveMic } from "../liveAudio";
import { CatStage, PersonaChip, StageBackdrop } from "./CatStage";
import { PersonaPicker } from "./PersonaPicker";
import { PERSONAS, usePersona } from "../catPersonas";

type Status = "idle" | "connecting" | "live" | "ending";

const ERROR_MESSAGES: Record<string, string> = {
  invalid_token: "Your sign-in expired. Please sign in again.",
  ai_quota_exceeded: "Gemini's free quota is used up for now. Try again later, or use turn-based practice.",
  live_unavailable: "Live call is unavailable right now. Please try again in a moment.",
  ollama_unreachable: "Can't reach Ollama. Make sure it is running on this computer.",
  ollama_model_missing: "The Ollama model isn't installed yet. Pull it first, then try again.",
  ollama_timeout: "Ollama took too long to answer. Please try again.",
  local_models_unavailable: "Couldn't load the local speech models (the first call downloads ~600 MB). Check your connection and try again.",
};

const readProvider = (): ChatProvider => {
  try {
    return localStorage.getItem("chatProvider") === "ollama" ? "ollama" : "gemini";
  } catch {
    return "gemini";
  }
};

const formatTime = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

// Gemini gửi transcript theo từng mẩu: nối vào câu cuối nếu cùng người nói (giống backend).
const appendLine = (lines: LiveCallLine[], role: LiveCallLine["role"], text: string): LiveCallLine[] => {
  const last = lines[lines.length - 1];
  if (last && last.role === role) return [...lines.slice(0, -1), { role, text: last.text + text }];
  return [...lines, { role, text }];
};

const Transcript: React.FC<{ lines: LiveCallLine[] }> = ({ lines }) => (
  <div className="space-y-2 text-sm">
    {lines.map((line, index) => (
      <p
        key={index}
        className={
          line.role === "user"
            ? "ml-auto max-w-[85%] w-fit rounded-2xl rounded-br-md bg-indigo-700 text-white px-4 py-2"
            : "max-w-[85%] w-fit rounded-2xl rounded-bl-md bg-purple-100 text-purple-950 px-4 py-2"
        }
      >
        {line.text.trim()}
      </p>
    ))}
  </div>
);

export const LiveCallPanel: React.FC = () => {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useState("");
  const [provider, setProvider] = useState<ChatProvider>(readProvider);
  const [persona] = usePersona();
  const theme = PERSONAS[persona].ui;
  const [status, setStatus] = useState<Status>("idle");
  const [lines, setLines] = useState<LiveCallLine[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [mouthOpen, setMouthOpen] = useState(0);
  const [history, setHistory] = useState<LiveCall[]>([]);

  const quotaCutRef = useRef(false);
  const socketRef = useRef<WebSocket | null>(null);
  const micRef = useRef<LiveMic | null>(null);
  const playerRef = useRef<PcmPlayer | null>(null);
  const rafRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  const loadHistory = () => {
    listLiveCalls().then(setHistory).catch(() => undefined);
  };

  useEffect(() => {
    listScenarios().then(setScenarios).catch(() => undefined);
    loadHistory();
  }, []);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ block: "nearest" });
  }, [lines]);

  // Giải phóng mic/loa/đồng hồ; gọi khi socket đóng (dù do người học cúp máy, server hay mất mạng).
  const release = () => {
    micRef.current?.stop();
    micRef.current = null;
    playerRef.current?.close();
    playerRef.current = null;
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    timerRef.current = null;
    setMouthOpen(0);
    setAiSpeaking(false);
  };

  useEffect(
    () => () => {
      socketRef.current?.close();
      release();
    },
    [],
  );

  const animate = () => {
    const player = playerRef.current;
    if (!player) return;
    setMouthOpen(player.level());
    setAiSpeaking(player.speaking);
    rafRef.current = requestAnimationFrame(animate);
  };

  const startCall = async () => {
    setError(null);
    // Gemini vừa hết quota mà người học chuyển sang Ollama: mang transcript cũ theo để nói tiếp.
    const carry = quotaCutRef.current && provider === "ollama" ? lines : [];
    quotaCutRef.current = false;
    setLines(carry);
    setElapsed(0);
    setStatus("connecting");
    const player = new PcmPlayer();
    playerRef.current = player;
    // Phải resume trong chính thao tác click, nếu không trình duyệt chặn phát âm thanh.
    await player.resume();

    const socket = new WebSocket(liveCallSocketUrl());
    socket.binaryType = "arraybuffer";
    socketRef.current = socket;
    socket.onopen = () =>
      socket.send(
        JSON.stringify({
          token: getAccessToken(),
          scenario_id: scenarioId || null,
          provider,
          persona,
          prior_transcript: carry.length ? carry : undefined,
        }),
      );
    socket.onmessage = async (event) => {
      if (typeof event.data !== "string") {
        playerRef.current?.play(event.data as ArrayBuffer);
        return;
      }
      const message = JSON.parse(event.data);
      if (message.type === "ready") {
        try {
          micRef.current = await startLiveMic((chunk) => {
            if (socket.readyState === WebSocket.OPEN) socket.send(chunk);
          });
        } catch {
          setError("Microphone unavailable. Allow microphone access in your browser and try again.");
          socket.close();
          return;
        }
        setStatus("live");
        const startedAt = Date.now();
        const maxSeconds: number = message.max_seconds ?? 600;
        timerRef.current = window.setInterval(() => {
          const seconds = (Date.now() - startedAt) / 1000;
          setElapsed(seconds);
          if (seconds >= maxSeconds) hangUp();
        }, 1000);
        rafRef.current = requestAnimationFrame(animate);
      } else if (message.type === "transcript") {
        setLines((current) => appendLine(current, message.role, message.text));
      } else if (message.type === "interrupted") {
        playerRef.current?.interrupt();
      } else if (message.type === "error") {
        if (message.code === "ai_quota_exceeded") quotaCutRef.current = true;
        setError(ERROR_MESSAGES[message.code] ?? ERROR_MESSAGES.live_unavailable);
      } else if (message.type === "ended" && message.call_id) {
        loadHistory();
        window.dispatchEvent(new Event("lumina-stats-refresh"));
      }
    };
    socket.onerror = () => setError("Can't reach the Lumina server.");
    socket.onclose = () => {
      socketRef.current = null;
      release();
      setStatus("idle");
    };
  };

  // Cúp máy: ngừng gửi mic, báo server lưu transcript; server gửi "ended" rồi tự đóng socket.
  const hangUp = () => {
    micRef.current?.stop();
    micRef.current = null;
    playerRef.current?.interrupt();
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "end" }));
      setStatus("ending");
    } else {
      socket?.close();
    }
  };

  const inCall = status === "live" || status === "connecting" || status === "ending";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <div className="lg:col-span-5 space-y-4">
        <div className={`relative overflow-hidden ${theme.stage} rounded-[2rem] p-6 shadow-[0_30px_50px_-30px_rgba(31,87,73,0.6)] transition-colors duration-500`}>
          <StageBackdrop persona={persona} />
          <PersonaChip persona={persona} />
          <p className={`text-center num text-3xl font-bold ${theme.text}`} aria-live="off">
            {status === "live" ? formatTime(elapsed) : " "}
          </p>
          <CatStage
            persona={persona}
            mouthOpen={mouthOpen}
            mood={status === "connecting" ? "thinking" : aiSpeaking ? "speaking" : status === "live" ? "listening" : "idle"}
            className="w-72 h-[22rem] mx-auto mt-1"
          />
          <div className="flex flex-col items-center gap-2">
            <button
              onClick={inCall ? hangUp : startCall}
              disabled={status === "ending"}
              aria-label={inCall ? "Hang up" : "Start live call"}
              className={`w-[72px] h-[72px] rounded-full flex items-center justify-center text-white transition-all active:scale-95 disabled:opacity-40 ${
                inCall
                  ? "bg-rose-500 hover:bg-rose-600 shadow-[0_18px_28px_-12px_rgba(244,63,94,0.9)]"
                  : `${theme.mic} hover:-translate-y-0.5`
              }`}
            >
              {status === "connecting" || status === "ending" ? (
                <Loader2 className="w-7 h-7 animate-spin" />
              ) : inCall ? (
                <PhoneOff className="w-7 h-7" />
              ) : (
                <Phone className="w-7 h-7" />
              )}
            </button>
            <p className={`text-xs ${theme.muted} mt-1`} aria-live="polite">
              {status === "connecting"
                ? "Connecting..."
                : status === "ending"
                  ? "Saving your call..."
                  : status === "live"
                    ? aiSpeaking
                      ? "The cat is talking. Just speak to interrupt."
                      : "Listening. Talk anytime."
                    : "Tap to call. No need to press record, just talk."}
            </p>
          </div>
        </div>

        <div className="surface p-5 space-y-3">
          <PersonaPicker disabled={inCall} />
          <select
            value={scenarioId}
            onChange={(event) => setScenarioId(event.target.value)}
            disabled={inCall}
            aria-label="Scenario"
            className="w-full px-3 py-2.5 text-sm bg-white ring-1 ring-slate-900/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60 disabled:opacity-60"
          >
            <option value="">Free talk</option>
            {scenarios.map((scenario) => (
              <option key={scenario.id} value={scenario.id}>
                {scenario.title} · {scenario.formality_level}
              </option>
            ))}
          </select>
          <select
            value={provider}
            onChange={(event) => {
              const next = event.target.value as ChatProvider;
              setProvider(next);
              try {
                localStorage.setItem("chatProvider", next);
              } catch {
                // Không có localStorage: lựa chọn chỉ áp dụng cho phiên hiện tại.
              }
            }}
            disabled={inCall}
            aria-label="AI model"
            className="w-full px-3 py-2.5 text-sm bg-white ring-1 ring-slate-900/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60 disabled:opacity-60"
          >
            <option value="gemini">Gemini Live (fast, uses online quota)</option>
            <option value="ollama">Ollama (runs on this computer, ~2s delay)</option>
          </select>
          <p className="text-[11px] text-slate-500 flex items-start gap-1.5">
            <Headphones className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            Headphones work best, so the cat doesn't hear itself. Calls end after 10 minutes.
            {provider === "ollama" && " The first local call loads the models and can take up to a minute."}
          </p>
          {error && (
            <p className="text-[11px] text-red-600 flex items-start gap-1">
              <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {error}
            </p>
          )}
        </div>
      </div>

      <div className="lg:col-span-7 space-y-4">
        <div className="surface p-7 space-y-4">
          <h3 className="font-display text-2xl font-bold text-slate-900">Live transcript</h3>
          {lines.length === 0 ? (
            <p className="text-sm text-slate-500">What you and the cat say will appear here as you talk.</p>
          ) : (
            <div className="max-h-96 overflow-y-auto pr-1">
              <Transcript lines={lines} />
              <div ref={transcriptEndRef} />
            </div>
          )}
        </div>

        <div className="surface p-7 space-y-3">
          <h3 className="font-display text-xl font-bold text-slate-900">Past calls</h3>
          {history.length === 0 ? (
            <p className="text-sm text-slate-500">Your calls are saved here after you hang up.</p>
          ) : (
            history.map((call) => (
              <details key={call.id} className="rounded-2xl bg-paper-deep px-4 py-3">
                <summary className="cursor-pointer text-sm font-semibold text-slate-700">
                  {new Date(call.created_at).toLocaleString()} · {call.scenario_title ?? "Free talk"} ·{" "}
                  <span className="num">{formatTime(call.duration_seconds)}</span>
                </summary>
                <div className="mt-3">
                  <Transcript lines={call.transcript} />
                </div>
              </details>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
