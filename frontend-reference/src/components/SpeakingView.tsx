// Speaking Studio: hội thoại theo lượt với AI qua backend FastAPI thật (Azure STT + chấm phát
// âm, LLM chấm ý định/lịch sự, Azure TTS phản hồi). Mèo mascot nhóp nhép theo biên độ audio
// phản hồi (Web Audio AnalyserNode), không dùng hoạt ảnh giả.
import React, { useEffect, useRef, useState } from "react";
import { AlertCircle, Bookmark, Check, Loader2, Mic, Play, Square } from "lucide-react";
import {
  ChatProvider,
  createSpeakingSession,
  fetchAudioObjectUrl,
  listScenarios,
  Scenario,
  savePhrase,
  SpeakingTurn,
  sendSpeakingTurn,
} from "../api";
import { startWavRecording, WavRecording } from "../wavRecorder";
import { useStudyTimer } from "../useStudyTimer";
import { CatMascot, CatMood } from "./CatMascot";
import { CountdownTimer } from "./CountdownTimer";
import { PhrasebookPanel } from "./PhrasebookPanel";

type Phase = "idle" | "recording" | "processing" | "speaking";

const scoreColor = (value: number) =>
  value >= 80 ? "bg-emerald-500" : value >= 60 ? "bg-amber-500" : "bg-rose-500";

const ScoreBar: React.FC<{ label: string; value: number | null; note?: string | null }> = ({ label, value, note }) => (
  <div>
    <div className="flex items-baseline justify-between">
      <span className="text-sm font-semibold text-slate-700">{label}</span>
      <span className="num text-2xl font-bold text-slate-900">{value === null ? "—" : Math.round(value)}</span>
    </div>
    <div className="h-2.5 bg-slate-200/70 rounded-full overflow-hidden mt-1">
      {value !== null && (
        <div
          className={`h-full rounded-full transition-[width] duration-700 ease-out ${scoreColor(value)}`}
          style={{ width: `${value}%` }}
        />
      )}
    </div>
    {note && <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{note}</p>}
  </div>
);

export const SpeakingView: React.FC = () => {
  const studyTimer = useStudyTimer();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useState("");
  const [provider, setProvider] = useState<ChatProvider>(() => {
    try {
      return localStorage.getItem("chatProvider") === "ollama" ? "ollama" : "gemini";
    } catch {
      return "gemini";
    }
  });
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<SpeakingTurn[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [mouthOpen, setMouthOpen] = useState(0);
  const [bubble, setBubble] = useState("Hi! Pick a scene and start a session, then tap the mic and talk to me.");
  const [error, setError] = useState<string | null>(null);
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set());
  const [phrasebookRefresh, setPhrasebookRefresh] = useState(0);

  const recordingRef = useRef<WavRecording | null>(null);
  const rafRef = useRef<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const pendingReplyRef = useRef<SpeakingTurn | null>(null);

  useEffect(() => {
    listScenarios()
      .then((items) => {
        setScenarios(items);
        setScenarioId((current) => current || items[0]?.id || "");
      })
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "Could not load scenarios."));
  }, []);

  const stopSpeaking = () => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    audioRef.current?.pause();
    audioRef.current = null;
    void audioContextRef.current?.close();
    audioContextRef.current = null;
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = null;
    setMouthOpen(0);
  };

  useEffect(
    () => () => {
      recordingRef.current?.cancel();
      stopSpeaking();
    },
    [],
  );

  // Không phát được audio (bị chặn autoplay/thiếu file): vẫn nhép miệng theo độ dài câu.
  const simulateMouth = (text: string) => {
    const duration = Math.min(12000, Math.max(1500, text.length * 65));
    const start = performance.now();
    const tick = (now: number) => {
      const elapsed = now - start;
      if (elapsed >= duration) {
        setMouthOpen(0);
        setPhase("idle");
        rafRef.current = null;
        return;
      }
      setMouthOpen(0.25 + 0.6 * Math.abs(Math.sin(elapsed / 90)));
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  };

  const speakReply = async (turn: SpeakingTurn) => {
    stopSpeaking();
    pendingReplyRef.current = turn;
    setPhase("speaking");
    const text = turn.response_text ?? "";
    if (!turn.response_audio_url) {
      simulateMouth(text);
      return;
    }
    try {
      const url = await fetchAudioObjectUrl(`/api/speaking/turns/${turn.turn_id}/audio`);
      objectUrlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      const context = new AudioContext();
      audioContextRef.current = context;
      const analyser = context.createAnalyser();
      analyser.fftSize = 512;
      context.createMediaElementSource(audio).connect(analyser);
      analyser.connect(context.destination);
      const samples = new Uint8Array(analyser.fftSize);
      let smoothed = 0;

      const loop = () => {
        analyser.getByteTimeDomainData(samples);
        let sum = 0;
        for (let index = 0; index < samples.length; index++) {
          const centered = (samples[index] - 128) / 128;
          sum += centered * centered;
        }
        const level = Math.min(1, Math.sqrt(sum / samples.length) * 6);
        smoothed = smoothed * 0.5 + level * 0.5;
        setMouthOpen(smoothed);
        rafRef.current = requestAnimationFrame(loop);
      };
      audio.onended = () => {
        stopSpeaking();
        setPhase("idle");
      };
      // Trình duyệt có thể tạo AudioContext ở trạng thái suspended (chính sách autoplay): khi đó
      // audio đi qua context sẽ không chạy và không bao giờ "ended".
      if (context.state === "suspended") await context.resume().catch(() => undefined);
      await audio.play();
      rafRef.current = requestAnimationFrame(loop);
      // Watchdog: sau 2s mà audio vẫn chưa tiến thì bỏ phân tích biên độ, nhép miệng theo câu chữ
      // để mèo không bị kẹt ở trạng thái "đang trả lời".
      window.setTimeout(() => {
        if (audioRef.current === audio && audio.currentTime === 0 && !audio.ended) {
          stopSpeaking();
          simulateMouth(text);
        }
      }, 2000);
    } catch {
      stopSpeaking();
      simulateMouth(text);
    }
  };

  const handleStartSession = async () => {
    if (!scenarioId) return;
    setError(null);
    stopSpeaking();
    try {
      const session = await createSpeakingSession(scenarioId);
      studyTimer.start();
      setSessionId(session.session_id);
      setTurns([]);
      const scenario = scenarios.find((item) => item.id === scenarioId);
      setBubble(`Scene: ${scenario?.title ?? ""}. Tap the mic and say hello!`);
    } catch (sessionError) {
      setError(sessionError instanceof Error ? sessionError.message : "Could not start session.");
    }
  };

  const handleMicClick = async () => {
    if (phase === "recording") {
      const recording = recordingRef.current;
      recordingRef.current = null;
      if (!recording || !sessionId) return;
      const blob = await recording.stop();
      if (!blob || blob.size < 4000) {
        setPhase("idle");
        setError("I couldn't hear anything. Try speaking a little longer.");
        return;
      }
      setPhase("processing");
      setBubble("Hmm, let me think...");
      try {
        const turn = await sendSpeakingTurn(sessionId, blob, provider, studyTimer.lap());
        setTurns((current) => [...current, turn]);
        setBubble(turn.response_text ?? "");
        await speakReply(turn);
      } catch (turnError) {
        setPhase("idle");
        const code = turnError instanceof Error ? turnError.message : "";
        setError(
          code === "empty_transcription"
            ? "I couldn't make out any words. Please record again."
            : code === "session_expired"
              ? "This session expired after 30 minutes idle. Start a new session."
              : code || "Something went wrong.",
        );
        setBubble("Could you say that again?");
      }
      return;
    }
    if (phase !== "idle" || !sessionId) return;
    setError(null);
    stopSpeaking();
    try {
      recordingRef.current = await startWavRecording();
      setPhase("recording");
      setBubble("I'm listening...");
    } catch {
      setError("Microphone unavailable. Allow microphone access in your browser and try again.");
    }
  };

  const handleSavePhrase = async (turn: SpeakingTurn, phrase: { phrase: string; meaning: string }) => {
    const key = `${turn.turn_id}:${phrase.phrase}`;
    try {
      await savePhrase({ phraseText: phrase.phrase, meaning: phrase.meaning, conversationTurnId: turn.turn_id });
      setSavedKeys((current) => new Set(current).add(key));
      setPhrasebookRefresh((value) => value + 1);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save phrase.");
    }
  };

  const mood: CatMood =
    phase === "recording" ? "listening" : phase === "processing" ? "thinking" : phase === "speaking" ? "speaking" : "idle";
  const latest = turns[turns.length - 1];
  const activeScenario = scenarios.find((item) => item.id === scenarioId);

  return (
    <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-sm italic text-slate-500 mb-1">Live conversation practice</p>
          <h1 className="font-display text-4xl font-bold text-slate-900">Speaking Studio</h1>
          <p className="text-sm text-slate-500 mt-2 max-w-xl">
            Chat with the cat in a real-life scene. It scores your pronunciation, intent and politeness on every turn.
          </p>
        </div>
        <CountdownTimer skill="speaking" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Sân khấu con mèo */}
        <div className="lg:col-span-5 space-y-4">
          <div className="relative overflow-hidden bg-[radial-gradient(ellipse_at_50%_35%,var(--color-purple-100),var(--color-indigo-100)_70%)] rounded-[2rem] p-6 shadow-[0_30px_50px_-30px_rgba(31,87,73,0.6)]">
            <div className="relative bg-[#fffdf8] rounded-3xl px-5 py-4 text-sm text-slate-700 min-h-[64px] shadow-[0_12px_24px_-14px_rgba(95,70,30,0.5)] font-medium">
              {phase === "processing" && <Loader2 className="w-4 h-4 animate-spin inline mr-2 text-indigo-500" />}
              {bubble}
              <span className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-4 h-4 bg-[#fffdf8] rotate-45 rounded-sm" />
            </div>
            <CatMascot mouthOpen={mouthOpen} mood={mood} className="w-64 h-80 mx-auto mt-3" />

            <div className="flex flex-col items-center gap-2">
              <button
                onClick={handleMicClick}
                disabled={!sessionId || phase === "processing" || phase === "speaking"}
                aria-label={phase === "recording" ? "Stop recording" : "Start recording"}
                className={`w-[72px] h-[72px] rounded-full flex items-center justify-center text-white transition-all active:scale-95 disabled:opacity-40 ${
                  phase === "recording"
                    ? "bg-rose-500 shadow-[0_0_0_10px_rgba(244,63,94,0.2),0_0_0_22px_rgba(244,63,94,0.1)] animate-pulse"
                    : "bg-indigo-700 hover:bg-indigo-800 hover:-translate-y-0.5 shadow-[0_18px_28px_-12px_rgba(31,87,73,0.9)]"
                }`}
              >
                {phase === "recording" ? <Square className="w-6 h-6" /> : <Mic className="w-7 h-7" />}
              </button>
              <p className="text-xs text-slate-600 mt-1">
                {!sessionId
                  ? "Start a session first"
                  : phase === "recording"
                    ? "Recording — tap to send"
                    : phase === "processing"
                      ? "Scoring your turn..."
                      : phase === "speaking"
                        ? "The cat is answering"
                        : "Tap the mic and speak"}
              </p>
              {phase === "speaking" && pendingReplyRef.current && (
                <button
                  onClick={() => pendingReplyRef.current && void speakReply(pendingReplyRef.current)}
                  className="text-[11px] text-indigo-600 font-bold flex items-center gap-1"
                >
                  <Play className="w-3 h-3" /> Replay
                </button>
              )}
            </div>
          </div>

          <div className="surface p-5 space-y-3">
            <select
              value={scenarioId}
              onChange={(event) => setScenarioId(event.target.value)}
              aria-label="Scenario"
              className="w-full px-3 py-2.5 text-sm bg-white ring-1 ring-slate-900/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
            >
              {scenarios.map((scenario) => (
                <option key={scenario.id} value={scenario.id}>
                  {scenario.title} · {scenario.formality_level}
                </option>
              ))}
            </select>
            {activeScenario?.goal && (
              <p className="text-[11px] text-slate-500">
                <span className="font-bold">Goal:</span> {activeScenario.goal}
              </p>
            )}
            <div className="flex gap-2">
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
                aria-label="AI model"
                className="px-2 py-2 text-xs bg-white ring-1 ring-slate-900/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
              >
                <option value="gemini">Gemini</option>
                <option value="ollama">Ollama (local, slower)</option>
              </select>
              <button
                onClick={handleStartSession}
                disabled={!scenarioId || phase === "recording" || phase === "processing"}
                className="flex-1 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl disabled:opacity-50 active:scale-[0.98] transition-all"
              >
                {sessionId ? "New session" : "Start session"}
              </button>
            </div>
            {error && (
              <p className="text-[11px] text-red-600 flex items-start gap-1">
                <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {error}
              </p>
            )}
          </div>
        </div>

        {/* Phản hồi + sổ tay */}
        <div className="lg:col-span-7 space-y-4">
          <div className="surface p-7 space-y-5">
            <h3 className="font-display text-2xl font-bold text-slate-900">Latest turn feedback</h3>
            {!latest ? (
              <p className="text-sm text-slate-500">Your scores will appear here after your first turn.</p>
            ) : (
              <>
                <p className="text-base text-slate-700 font-serif leading-relaxed">
                  <span className="text-sm italic text-slate-400 mr-2 font-sans">You said</span>“{latest.user_transcript}”
                  {latest.stt_provider_used && latest.stt_provider_used !== "azure" && (
                    <span className="tag ml-2 bg-amber-100 text-amber-800 font-sans">
                      transcribed by {latest.stt_provider_used}
                    </span>
                  )}
                </p>
                {latest.pronunciation_assessment_failed ? (
                  <p className="text-xs text-amber-700 bg-amber-50 rounded-xl px-3 py-2">
                    Pronunciation scoring was unavailable for this turn.
                  </p>
                ) : (
                  <ScoreBar label="Pronunciation" value={latest.pronunciation_score} note={latest.pronunciation_advice} />
                )}
                <ScoreBar label="Intent" value={latest.intent_score} note={latest.intent_feedback} />
                <ScoreBar label="Politeness" value={latest.politeness_score} note={latest.politeness_feedback} />

                {latest.natural_rephrase && (
                  <div className="p-4 rounded-2xl bg-emerald-50">
                    <p className="text-sm italic text-emerald-700">Say it more naturally</p>
                    <p className="text-base text-slate-800 font-serif mt-1">“{latest.natural_rephrase}”</p>
                  </div>
                )}

                {latest.literal_translation.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-sm italic text-slate-400">Literal translation from Vietnamese</p>
                    {latest.literal_translation.map((note) => (
                      <div key={note.original} className="p-4 rounded-2xl bg-amber-50 text-sm">
                        <p className="text-slate-700">
                          <span className="line-through text-rose-600">{note.original}</span>
                          {" → "}
                          <span className="font-bold text-emerald-700">{note.natural}</span>
                        </p>
                        {note.explanation && <p className="text-xs text-slate-600 mt-1">{note.explanation}</p>}
                      </div>
                    ))}
                  </div>
                )}

                {latest.suggested_phrases.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-sm italic text-slate-400">Useful phrases</p>
                    {latest.suggested_phrases.map((phrase) => {
                      const saved = savedKeys.has(`${latest.turn_id}:${phrase.phrase}`);
                      return (
                        <div key={phrase.phrase} className="flex items-start justify-between gap-2 p-4 rounded-2xl bg-indigo-50 hover:bg-indigo-100/70 transition-colors">
                          <div>
                            <p className="text-sm font-bold text-slate-900">{phrase.phrase}</p>
                            <p className="text-xs text-slate-600">{phrase.meaning}</p>
                            {phrase.source_note && <p className="text-[10px] text-slate-400 mt-0.5">{phrase.source_note}</p>}
                          </div>
                          <button
                            onClick={() => handleSavePhrase(latest, phrase)}
                            disabled={saved}
                            aria-label={saved ? "Saved" : "Save phrase"}
                            className="p-1.5 rounded-lg text-indigo-600 hover:bg-indigo-50 disabled:text-emerald-600"
                          >
                            {saved ? <Check className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </div>

          {turns.length > 0 && (
            <div className="surface p-7 space-y-4 max-h-72 overflow-y-auto">
              <h3 className="font-display text-xl font-bold text-slate-900">Conversation</h3>
              {turns.map((turn) => (
                <div key={turn.turn_id} className="space-y-2 text-sm">
                  <p className="ml-auto max-w-[85%] w-fit rounded-2xl rounded-br-md bg-indigo-700 text-white px-4 py-2">{turn.user_transcript}</p>
                  <p className="max-w-[85%] w-fit rounded-2xl rounded-bl-md bg-purple-100 text-purple-950 px-4 py-2">{turn.response_text}</p>
                </div>
              ))}
            </div>
          )}

          <PhrasebookPanel refreshKey={phrasebookRefresh} />
        </div>
      </div>
    </div>
  );
};
