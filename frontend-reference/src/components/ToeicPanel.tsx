// Luyện TOEIC-style: Part 5/6/7 (đọc) và Part 2/3/4 (nghe, đọc bài bằng giọng trình duyệt). Đề là câu hỏi gốc do AI sinh,
// KHÔNG phải đề ETS; có đồng hồ theo số câu (hết giờ tự nộp), giải thích tiếng Việt, và ước lượng điểm thô /990.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Volume2 } from "lucide-react";
import {
  ToeicPart,
  ToeicPractice,
  fetchToeicImage,
  startToeicMock,
  ToeicSubmitResult,
  ToeicSummary,
  getToeicSummary,
  startToeicPractice,
  submitToeicPractice,
} from "../api";
import { ErrorNotice } from "./ErrorNotice";
import { formatClock } from "./CountdownTimer";

const PARTS: { id: ToeicPart; label: string }[] = [
  { id: 1, label: "Part 1 · Photographs" },
  { id: 5, label: "Part 5 · Incomplete sentences" },
  { id: 6, label: "Part 6 · Text completion" },
  { id: 7, label: "Part 7 · Reading" },
  { id: 2, label: "Part 2 · Question–response" },
  { id: 3, label: "Part 3 · Conversations" },
  { id: 4, label: "Part 4 · Talks" },
];

// Part 1: ảnh cần token nên tải thành blob; chú thích tác giả/giấy phép luôn hiển thị.
const ToeicImage: React.FC<{ name: string; credit: string | null }> = ({ name, credit }) => {
  const [src, setSrc] = useState("");
  useEffect(() => {
    let url = "";
    let alive = true;
    fetchToeicImage(name).then((u) => { url = u; if (alive) setSrc(u); }).catch(() => undefined);
    return () => { alive = false; if (url) URL.revokeObjectURL(url); };
  }, [name]);
  return (
    <figure className="space-y-1">
      {src ? <img src={src} alt="Photograph to describe" className="max-h-72 rounded-2xl object-contain bg-slate-100" /> : <div className="h-40 rounded-2xl bg-slate-100 animate-pulse" />}
      {credit && <figcaption className="text-[11px] text-slate-400">{credit}</figcaption>}
    </figure>
  );
};

export const ToeicPanel: React.FC = () => {
  const [practice, setPractice] = useState<ToeicPractice | null>(null);
  const [picks, setPicks] = useState<Array<number | null>>([]);
  const [result, setResult] = useState<ToeicSubmitResult | null>(null);
  const [left, setLeft] = useState(0);
  const [quick, setQuick] = useState(false);
  const [busy, setBusy] = useState<"start" | "submit" | null>(null);
  const [summary, setSummary] = useState<ToeicSummary | null>(null);
  const [error, setError] = useState<{ cause: unknown; retry: () => void } | null>(null);
  const startedAt = useRef(0);
  const picksRef = useRef(picks);
  picksRef.current = picks;

  const loadSummary = useCallback(() => getToeicSummary().then(setSummary).catch(() => setSummary(null)), []);
  useEffect(() => void loadSummary(), [loadSummary]);

  const run = async (kind: "start" | "submit", action: () => Promise<void>) => {
    setBusy(kind);
    setError(null);
    try {
      await action();
    } catch (cause) {
      setError({ cause, retry: () => run(kind, action) });
    } finally {
      setBusy(null);
    }
  };

  const begin = (next: ToeicPractice) => {
    setPicks(next.questions.map(() => null));
    setLeft(next.time_limit_seconds);
    startedAt.current = Date.now();
    setPractice(next);
  };

  const start = (part: ToeicPart) =>
    run("start", async () => {
      setResult(null);
      // Bộ nhanh ~2 phút (Part 5: 4 câu x 30s, Part 2: 6 câu x 20s); Part 3/4/6/7 luôn là 1 bài + 3 câu.
      begin(await startToeicPractice(part, quick ? (part === 2 ? 6 : 4) : 8));
    });

  const startMock = () =>
    run("start", async () => {
      setResult(null);
      begin(await startToeicMock());
    });

  const submit = useCallback(
    (attemptId: string) =>
      run("submit", async () => {
        setResult(await submitToeicPractice(attemptId, picksRef.current, Math.round((Date.now() - startedAt.current) / 1000)));
        void loadSummary();
      }),
    [loadSummary],
  );

  // Đếm ngược theo mốc kết thúc (không trôi khi tab nền bị throttle); hết giờ tự nộp bài.
  useEffect(() => {
    if (!practice || result) return;
    const endAt = startedAt.current + practice.time_limit_seconds * 1000;
    const id = window.setInterval(() => {
      const remaining = Math.max(0, Math.ceil((endAt - Date.now()) / 1000));
      setLeft(remaining);
      if (remaining === 0) {
        window.clearInterval(id);
        void submit(practice.attempt_id);
      }
    }, 250);
    return () => window.clearInterval(id);
  }, [practice, result, submit]);

  const speak = (text: string) => {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    window.speechSynthesis.speak(utterance);
  };

  // Part 3/4: bài nghe là văn bản đọc to bằng giọng trình duyệt; hội thoại ("Man: ...") đổi giọng/cao độ theo người nói.
  const playPassage = (text: string) => {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const voices = window.speechSynthesis.getVoices().filter((v) => v.lang.startsWith("en"));
    const speakers: string[] = [];
    for (const line of text.split("\n").filter((l) => l.trim())) {
      const match = line.match(/^\s*([A-Z][A-Za-z .]{0,20}):\s+(.*)$/);
      if (match && !speakers.includes(match[1])) speakers.push(match[1]);
      const who = match ? speakers.indexOf(match[1]) : 0;
      const utterance = new SpeechSynthesisUtterance(match ? match[2] : line);
      utterance.lang = "en-US";
      if (voices.length) utterance.voice = voices[who % voices.length];
      utterance.pitch = who % 2 ? 1.25 : 0.85; // phân biệt người nói kể cả khi máy chỉ có 1 giọng
      window.speechSynthesis.speak(utterance);
    }
  };

  // Mỗi câu tự biết Part của nó (đề thi thử trộn nhiều Part); lượt luyện 1 Part thì dùng practice.part.
  const partOf = (q: ToeicPractice["questions"][number]) => q.part ?? practice?.part ?? 0;
  const isMock = practice?.part === 0;

  return (
    <div className="surface p-7 space-y-5 mt-6">
      <div>
        <h3 className="font-display text-2xl font-bold text-slate-900">TOEIC-style practice</h3>
        <p className="text-xs text-slate-500">Original practice questions written by AI in the TOEIC format — not official ETS material.</p>
      </div>

      {!practice && (
        <label className="flex items-center gap-2 text-xs text-slate-600">
          <input type="checkbox" checked={quick} onChange={(e) => setQuick(e.target.checked)} />
          Quick set (about 2 minutes for Part 5 and Part 2; 4 photos for Part 1)
        </label>
      )}

      {!practice && (
        <div className="flex flex-wrap gap-2">
          {PARTS.map((part) => (
            <button
              key={part.id}
              onClick={() => void start(part.id)}
              disabled={busy !== null}
              className="px-4 py-2 bg-indigo-700 hover:bg-indigo-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl flex items-center gap-2 cursor-pointer"
            >
              {busy === "start" && <Loader2 className="w-3.5 h-3.5 animate-spin" />} {part.label}
            </button>
          ))}
          <button
            onClick={() => void startMock()}
            disabled={busy !== null}
            className="px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl cursor-pointer"
          >
            Full mock test (Part 1–7, one timer)
          </button>
        </div>
      )}
      {!practice && busy === "start" && (
        <p role="status" className="text-xs text-slate-500">Preparing your set — if the question bank is empty for this part, AI writes it live and this can take 1–3 minutes.</p>
      )}

      {practice && (
        <div className="space-y-4">
          {!result && (
            <p className="num text-sm font-bold text-slate-700" role="timer">
              {left === 0 ? "Time's up" : `Time left ${formatClock(left)}`}
            </p>
          )}
          {practice.questions.map((question, qi) => {
            const part = partOf(question);
            const photo = part === 1;
            const listening = part === 1 || part === 2; // Part 1/2: chữ của lựa chọn ẩn tới khi nộp, nghe bằng TTS
            const audioPassage = part === 3 || part === 4;
            const previous = practice.questions[qi - 1];
            const showPassage = !!question.passage && (qi === 0 || previous?.passage !== question.passage);
            return (
            <div key={qi} className="space-y-2">
              {isMock && (!previous || partOf(previous) !== part) && <h4 className="pt-3 font-bold text-slate-900 border-t border-slate-200">Part {part}</h4>}
              {showPassage && audioPassage && !result && (
                <div className="flex items-center gap-3">
                  <button onClick={() => playPassage(question.passage!)} className="px-3 py-1.5 rounded-full bg-slate-100 text-indigo-700 text-xs font-bold flex items-center gap-1.5 cursor-pointer">
                    <Volume2 className="w-3.5 h-3.5" /> Play audio
                  </button>
                  <button onClick={() => window.speechSynthesis?.cancel()} className="text-xs text-slate-500 cursor-pointer">Stop</button>
                  <span className="text-xs text-slate-500">You can replay as often as you like; the script appears after you submit.</span>
                </div>
              )}
              {showPassage && !(audioPassage && !result) && <p className="whitespace-pre-wrap rounded-2xl bg-slate-50 p-4 font-serif text-[15px] leading-7 text-slate-800">{question.passage}</p>}
              {question.image && <ToeicImage name={question.image} credit={question.credit} />}
              <div className="flex items-start gap-2">
                <span className="num font-bold text-slate-500">{qi + 1}.</span>
                {listening && !photo ? (
                  <>
                    <button onClick={() => speak(question.prompt)} className="px-3 py-1.5 rounded-full bg-slate-100 text-indigo-700 text-xs font-bold flex items-center gap-1.5 cursor-pointer">
                      <Volume2 className="w-3.5 h-3.5" /> Play
                    </button>
                    {result && <span className="font-serif text-slate-700">{question.prompt}</span>}
                  </>
                ) : (
                  <p className="font-serif text-slate-900">{question.prompt}</p>
                )}
              </div>
              <ul className="grid gap-1.5 ml-6">
                {question.options.map((option, oi) => {
                  const graded = result?.results[qi];
                  const right = graded && oi === graded.correct_index;
                  const wrong = graded && picks[qi] === oi && !right;
                  return (
                    <li key={oi}>
                      <button
                        disabled={!!result || busy !== null}
                        aria-pressed={picks[qi] === oi}
                        onClick={() => setPicks((current) => current.map((p, i) => (i === qi ? oi : p)))}
                        className={`w-full text-left px-3 py-2 rounded-xl border text-sm cursor-pointer ${
                          right ? "border-emerald-400 bg-emerald-50" : wrong ? "border-rose-400 bg-rose-50" : picks[qi] === oi ? "border-indigo-500 bg-indigo-50" : "border-slate-200 bg-white hover:bg-slate-50"
                        }`}
                      >
                        <b className="mr-2">{String.fromCharCode(65 + oi)}</b>
                        {listening && !result ? "" : option}
                        {listening && !result && (
                          <span
                            role="button"
                            tabIndex={0}
                            onClick={(e) => { e.stopPropagation(); speak(option); }}
                            onKeyDown={(e) => { if (e.key === "Enter") { e.stopPropagation(); speak(option); } }}
                            className="inline-flex items-center gap-1 text-indigo-700"
                          >
                            <Volume2 className="w-3.5 h-3.5" /> Play
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
              {result && (
                <div className="ml-6 text-xs text-slate-600 space-y-0.5">
                  <p>{result.results[qi].explanation_vi}</p>
                  {result.results[qi].contrast_vi && <p className="text-indigo-700">Tiếng Việt vs English: {result.results[qi].contrast_vi}</p>}
                </div>
              )}
            </div>
            );
          })}

          {result ? (
            <div className="space-y-2">
              <p className="text-sm font-bold text-slate-900" role="status">
                {result.correct_count}/{result.total} correct ({Math.round(result.score)}%)
              </p>
              {result.by_part && (
                <ul className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                  {result.by_part.map((b) => <li key={b.part}>Part {b.part}: <b className="num">{b.correct}/{b.total}</b></li>)}
                </ul>
              )}
              {result.estimate && (
                <p className="text-sm text-slate-700">
                  Rough score from this mock test:{" "}
                  <b className="num">{result.estimate.total !== null ? `${result.estimate.total} / 990` : `Listening ${result.estimate.listening ?? "–"} · Reading ${result.estimate.reading ?? "–"}`}</b>
                </p>
              )}
              <button onClick={() => setPractice(null)} className="text-sm font-bold text-indigo-700 cursor-pointer">Practise another set</button>
            </div>
          ) : (
            <button
              onClick={() => void submit(practice.attempt_id)}
              disabled={busy !== null}
              className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl flex items-center gap-2 cursor-pointer"
            >
              {busy === "submit" && <Loader2 className="w-4 h-4 animate-spin" />} Submit
            </button>
          )}
        </div>
      )}

      {summary && summary.parts.length > 0 && (
        <div className="rounded-2xl bg-slate-50 p-4 space-y-2 text-sm">
          <ul className="flex flex-wrap gap-x-6 gap-y-1">
            {summary.parts.map((p) => (
              <li key={p.part}>
                Part {p.part}: <b className="num">{p.accuracy}%</b> <span className="text-xs text-slate-500">({p.questions} questions)</span>
              </li>
            ))}
          </ul>
          <p className="text-slate-700">
            Rough score estimate:{" "}
            <b className="num">
              {summary.estimate.total !== null
                ? `${summary.estimate.total} / 990`
                : `${summary.estimate.listening !== null ? `Listening ${summary.estimate.listening}/495` : ""}${summary.estimate.listening !== null && summary.estimate.reading !== null ? " · " : ""}${summary.estimate.reading !== null ? `Reading ${summary.estimate.reading}/495` : ""}`}
            </b>
          </p>
          <p className="text-[11px] text-slate-400">{summary.estimate.note}</p>
        </div>
      )}

      {error && <ErrorNotice error={error.cause} onRetry={error.retry} retryLabel="Try again" />}
    </div>
  );
};
