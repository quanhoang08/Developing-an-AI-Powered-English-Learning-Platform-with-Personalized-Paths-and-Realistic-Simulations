// Phòng luyện phát âm cho người Việt (backlog 4.1-4.5): câu mẫu theo lỗi hay gặp + shadowing có so sóng âm,
// game cặp âm dễ nhầm (browser TTS), và chế độ "nói thầm" (gõ thay nói để giữ streak).
import React, { useEffect, useRef, useState } from "react";
import { Loader2, Mic, Square, Volume2 } from "lucide-react";
import {
  PairQuestion,
  PairsResult,
  PronAssessment,
  PronSentence,
  DiaryEntry,
  addDiaryEntry,
  deleteDiaryEntry,
  diaryAudioUrl,
  getDiary,
  assessPronSentence,
  checkPairs,
  fetchPronSentenceAudio,
  getPairsQuiz,
  getPronSentences,
  getSilentPrompt,
  sendSilentAnswer,
} from "../api";
import { startWavRecording, WavRecording } from "../wavRecorder";

const FOCUS_LABEL: Record<string, string> = {
  final: "Final sounds",
  cluster: "Consonant clusters",
  th: "/θ/ /ð/",
  stress: "Word stress",
  ed: "-ed endings",
};

// Đường bao biên độ (peak theo cột) của một đoạn audio, chuẩn hóa 0..1.
function envelope(data: Float32Array, bars: number): number[] {
  const size = Math.max(1, Math.floor(data.length / bars));
  const out: number[] = [];
  for (let i = 0; i < bars; i++) {
    let peak = 0;
    for (let j = i * size; j < Math.min((i + 1) * size, data.length); j++) peak = Math.max(peak, Math.abs(data[j]));
    out.push(peak);
  }
  const max = Math.max(...out, 0.001);
  return out.map((v) => v / max);
}

async function blobEnvelope(blob: Blob, bars = 80): Promise<number[]> {
  const ctx = new AudioContext();
  try {
    const buffer = await ctx.decodeAudioData(await blob.arrayBuffer());
    return envelope(buffer.getChannelData(0), bars);
  } finally {
    void ctx.close();
  }
}

const Wave: React.FC<{ ref_: number[]; user: number[] }> = ({ ref_, user }) => (
  <svg viewBox="0 0 160 60" className="w-full h-16" role="img" aria-label="Waveform comparison: model in grey, you in indigo">
    {ref_.map((v, i) => <rect key={`r${i}`} x={i * 2} y={30 - v * 28} width="1.4" height={v * 56} fill="#cbd5e1" />)}
    {user.map((v, i) => <rect key={`u${i}`} x={i * 2} y={30 - v * 28} width="1.4" height={v * 56} fill="#4338ca" opacity="0.7" />)}
  </svg>
);

const SentenceLab: React.FC = () => {
  const [sentences, setSentences] = useState<PronSentence[]>([]);
  const [current, setCurrent] = useState<PronSentence | null>(null);
  const [result, setResult] = useState<PronAssessment | null>(null);
  const [waves, setWaves] = useState<{ ref: number[]; user: number[] } | null>(null);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const recorder = useRef<WavRecording | null>(null);
  const refBlob = useRef<{ id: string; blob: Blob } | null>(null);

  useEffect(() => {
    getPronSentences().then((list) => { setSentences(list); setCurrent(list[0] ?? null); }).catch((e) => setMessage(e.message));
  }, []);

  const fail = (e: unknown) => setMessage(e instanceof Error ? e.message : "Something went wrong.");

  const loadRef = async (id: string): Promise<Blob> => {
    if (refBlob.current?.id === id) return refBlob.current.blob;
    const url = await fetchPronSentenceAudio(id);
    const blob = await (await fetch(url)).blob();
    refBlob.current = { id, blob };
    return blob;
  };

  const listen = async () => {
    if (!current) return;
    setBusy(true);
    setMessage("");
    try {
      const url = URL.createObjectURL(await loadRef(current.id));
      await new Audio(url).play();
    } catch (e) { fail(e); } finally { setBusy(false); }
  };

  const toggle = async () => {
    if (!current) return;
    setMessage("");
    if (!recording) {
      try { recorder.current = await startWavRecording(); setRecording(true); } catch { setMessage("Could not access the microphone."); }
      return;
    }
    setRecording(false);
    setBusy(true);
    try {
      const blob = await recorder.current?.stop();
      if (!blob) { setMessage("Nothing was recorded."); return; }
      const [res, refWave, userWave] = await Promise.all([
        assessPronSentence(current.id, blob),
        loadRef(current.id).then((b) => blobEnvelope(b)).catch(() => []),
        blobEnvelope(blob),
      ]);
      setResult(res);
      setWaves({ ref: refWave, user: userWave });
    } catch (e) { fail(e); } finally { setBusy(false); }
  };

  const pick = (id: string) => {
    setCurrent(sentences.find((s) => s.id === id) ?? null);
    setResult(null);
    setWaves(null);
    setMessage("");
  };

  return (
    <div className="space-y-4">
      <h4 className="font-display text-xl font-bold text-slate-900">Shadowing for Vietnamese speakers</h4>
      <div className="flex flex-wrap gap-2">
        {sentences.map((s, i) => (
          <button key={s.id} onClick={() => pick(s.id)} title={FOCUS_LABEL[s.focus]}
            className={`px-3 py-1.5 rounded-full text-xs font-bold cursor-pointer ${current?.id === s.id ? "bg-indigo-700 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>
            {FOCUS_LABEL[s.focus]} {(i % 3) + 1}
          </button>
        ))}
      </div>
      {current && (
        <>
          <p className="text-lg font-semibold text-slate-900">{current.text}</p>
          <p className="text-xs text-slate-600">{current.tip_vi}</p>
          <div className="flex gap-2">
            <button onClick={() => void listen()} disabled={busy || recording}
              className="px-4 py-2 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 text-slate-800 font-bold text-xs rounded-2xl flex items-center gap-2 cursor-pointer">
              <Volume2 className="w-4 h-4" /> Listen
            </button>
            <button onClick={() => void toggle()} disabled={busy}
              className="px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl flex items-center gap-2 cursor-pointer">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : recording ? <Square className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              {recording ? "Stop & score" : "Repeat after the model"}
            </button>
          </div>
        </>
      )}
      {result && (
        <div className="space-y-3" role="status">
          <p className="text-sm text-slate-700">
            Score <b className="num">{result.score}</b> · accuracy <span className="num">{result.accuracy}</span> · fluency <span className="num">{result.fluency}</span> · completeness <span className="num">{result.completeness}</span>
          </p>
          <p className="flex flex-wrap gap-1.5">
            {result.words.map((w, i) => (
              <span key={i} className={`px-2 py-0.5 rounded text-sm ${w.score >= 75 ? "bg-emerald-100 text-emerald-900" : w.score >= 50 ? "bg-amber-100 text-amber-900" : "bg-rose-100 text-rose-900"}`}>{w.word}</span>
            ))}
          </p>
          {waves && waves.ref.length > 0 && <Wave ref_={waves.ref} user={waves.user} />}
          {result.weak_words.map((w) => (
            <div key={w.word} className="text-sm text-slate-700">
              <b>{w.word}</b> ({w.score}): {w.tips_vi.join(" ")}
            </div>
          ))}
          {result.weak_words.length === 0 && <p className="text-sm text-emerald-700">Clear pronunciation on every word.</p>}
        </div>
      )}
      <p role="alert" className="text-xs text-rose-700">{message}</p>
    </div>
  );
};

const PairsGame: React.FC = () => {
  const [questions, setQuestions] = useState<PairQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<PairsResult | null>(null);
  const [message, setMessage] = useState("");

  const start = () => {
    setResult(null);
    setAnswers({});
    setMessage("");
    getPairsQuiz(8).then(setQuestions).catch((e) => setMessage(e.message));
  };
  useEffect(start, []);

  const speak = (word: string) => {
    const u = new SpeechSynthesisUtterance(word);
    u.lang = "en-US";
    u.rate = 0.8;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  };

  return (
    <div className="space-y-4">
      <h4 className="font-display text-xl font-bold text-slate-900">Which word did you hear?</h4>
      <p className="text-xs text-slate-500">Press play, then pick the word you heard (voice comes from your browser).</p>
      {questions.map((q, i) => {
        const r = result?.results.find((x) => x.id === q.id);
        return (
          <div key={q.id} className="flex flex-wrap items-center gap-2">
            <button onClick={() => speak(q.speak)} aria-label={`Play word ${i + 1}`} className="p-2 rounded-full bg-slate-100 hover:bg-slate-200 cursor-pointer">
              <Volume2 className="w-4 h-4" />
            </button>
            {q.options.map((o) => (
              <button key={o} disabled={!!result} onClick={() => setAnswers((prev) => ({ ...prev, [q.id]: o }))}
                className={`px-3 py-1.5 rounded-full text-sm font-bold cursor-pointer ${answers[q.id] === o ? "bg-indigo-700 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>
                {o}
              </button>
            ))}
            {r && (
              <span className={`text-xs ${r.is_correct ? "text-emerald-700" : "text-rose-700"}`}>
                {r.is_correct ? "Correct" : `It was “${r.correct_word}”`} — {r.note_vi}
              </span>
            )}
          </div>
        );
      })}
      {result ? (
        <div className="flex items-center gap-3">
          <p className="text-sm text-slate-700" role="status"><b className="num">{result.correct}</b> / <span className="num">{result.total}</span> correct</p>
          <button onClick={start} className="px-4 py-2 bg-slate-900 text-white font-bold text-xs rounded-2xl cursor-pointer">New round</button>
        </div>
      ) : (
        <button
          disabled={questions.length === 0 || Object.keys(answers).length < questions.length}
          onClick={() => checkPairs(questions.map((q) => ({ id: q.id, choice: answers[q.id] }))).then(setResult).catch((e) => setMessage(e.message))}
          className="px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl cursor-pointer"
        >
          Check answers
        </button>
      )}
      <p role="alert" className="text-xs text-rose-700">{message}</p>
    </div>
  );
};

const SilentMode: React.FC = () => {
  const [prompt, setPrompt] = useState<{ id: number; prompt: string } | null>(null);
  const [text, setText] = useState("");
  const [message, setMessage] = useState("");
  const [ok, setOk] = useState(false);

  const next = () => { setText(""); setOk(false); setMessage(""); getSilentPrompt().then(setPrompt).catch((e) => setMessage(e.message)); };
  useEffect(next, []);

  return (
    <div className="space-y-3">
      <h4 className="font-display text-xl font-bold text-slate-900">Silent mode</h4>
      <p className="text-xs text-slate-500">Can't speak right now? Type your answer (at least 8 words) to keep your streak.</p>
      {prompt && <p className="text-sm font-semibold text-slate-900">{prompt.prompt}</p>}
      <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} rows={3} disabled={ok}
        className="w-full px-4 py-2.5 rounded-xl ring-1 ring-slate-900/10 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/60" />
      <div className="flex gap-2">
        <button disabled={ok || !prompt || !text.trim()}
          onClick={() => prompt && sendSilentAnswer(prompt.id, text).then((r) => { setOk(true); setMessage(r.xp > 0 ? `Saved: +${r.xp} XP and your streak is safe.` : "Saved and your streak is safe. You've used today's XP for silent mode (max 5 a day)."); }).catch((e) => setMessage(
            e.message === "answer_too_short" ? "Write at least 8 words, with a few different ones."
            : e.message === "answer_off_topic" ? "That doesn't look like an English answer to the question. Try again in your own words."
            : e.message))}
          className="px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl cursor-pointer">
          Submit
        </button>
        {ok && <button onClick={next} className="px-4 py-2 bg-slate-100 text-slate-800 font-bold text-xs rounded-2xl cursor-pointer">Another prompt</button>}
      </div>
      <p role="status" className="text-xs text-slate-700">{message}</p>
    </div>
  );
};


const MAX_DIARY_SECONDS = 60;

const VoiceDiary: React.FC = () => {
  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const recorder = useRef<WavRecording | null>(null);
  const timer = useRef<number | null>(null);
  const startedAt = useRef(0);

  const load = () => getDiary().then(setEntries).catch((e) => setMessage(e.message));
  useEffect(() => { void load(); return () => { if (timer.current) window.clearInterval(timer.current); }; }, []);

  const finish = async () => {
    if (timer.current) window.clearInterval(timer.current);
    setRecording(false);
    setBusy(true);
    try {
      const blob = await recorder.current?.stop();
      const length = Math.max(1, Math.min(MAX_DIARY_SECONDS, Math.round((Date.now() - startedAt.current) / 1000)));
      if (!blob) { setMessage("Nothing was recorded."); return; }
      await addDiaryEntry(blob, length);
      await load();
    } catch (e) { setMessage(e instanceof Error ? e.message : "Could not save."); } finally { setBusy(false); }
  };

  const toggle = async () => {
    setMessage("");
    if (recording) { await finish(); return; }
    try {
      recorder.current = await startWavRecording();
    } catch { setMessage("Could not access the microphone."); return; }
    startedAt.current = Date.now();
    setSeconds(0);
    setRecording(true);
    timer.current = window.setInterval(() => {
      const elapsed = Math.round((Date.now() - startedAt.current) / 1000);
      setSeconds(elapsed);
      if (elapsed >= MAX_DIARY_SECONDS) void finish();
    }, 500);
  };

  const play = async (id: string) => { try { await new Audio(await diaryAudioUrl(id)).play(); } catch (e) { setMessage(e instanceof Error ? e.message : "Could not play."); } };

  return (
    <div className="space-y-3">
      <h4 className="font-display text-xl font-bold text-slate-900">60-second voice diary</h4>
      <p className="text-xs text-slate-500">Talk about your day (up to 60 seconds). Listen back later to hear how you improve.</p>
      <button onClick={() => void toggle()} disabled={busy}
        className="px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl flex items-center gap-2 cursor-pointer">
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : recording ? <Square className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
        {recording ? `Stop (${seconds}s / ${MAX_DIARY_SECONDS}s)` : "Record today's entry"}
      </button>
      {entries.map((e) => (
        <div key={e.id} className="text-sm border-t border-slate-100 pt-2">
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500 num">{new Date(e.created_at).toLocaleString()} · {e.duration_seconds}s{e.words_per_minute ? ` · ${e.words_per_minute} wpm` : ""}</span>
            <button onClick={() => void play(e.id)} aria-label="Play entry" className="p-1.5 rounded-full bg-slate-100 hover:bg-slate-200 cursor-pointer"><Volume2 className="w-4 h-4" /></button>
            <button onClick={() => void deleteDiaryEntry(e.id).then(load).catch((err) => setMessage(err.message))} className="text-xs text-rose-700 cursor-pointer">Delete</button>
          </div>
          {e.transcript && <p className="text-slate-700">{e.transcript}</p>}
        </div>
      ))}
      <p role="alert" className="text-xs text-rose-700">{message}</p>
    </div>
  );
};

export const PronunciationPanel: React.FC = () => (
  <div className="stagger-in surface p-7 space-y-8">
    <SentenceLab />
    <div className="border-t border-dashed border-slate-200 pt-6"><PairsGame /></div>
    <div className="border-t border-dashed border-slate-200 pt-6"><SilentMode /></div>
    <div className="border-t border-dashed border-slate-200 pt-6"><VoiceDiary /></div>
  </div>
);
