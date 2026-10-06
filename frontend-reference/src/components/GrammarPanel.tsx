// Bản đồ ngữ pháp (backlog 3.8): test đầu vào trộn mọi chủ điểm hoặc luyện riêng một chủ điểm. Không gọi LLM.
import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { GrammarQuestion, GrammarSubmitResult, getGrammarAttempts, getGrammarDaily, getGrammarQuiz, submitGrammarQuiz } from "../api";
import { ErrorNotice } from "./ErrorNotice";

const TOPICS: Array<{ id: string | null; label: string }> = [
  { id: null, label: "Placement test (all topics)" },
  { id: "tenses", label: "Tenses" },
  { id: "articles", label: "Articles" },
  { id: "prepositions", label: "Prepositions" },
  { id: "agreement", label: "Subject–verb agreement" },
  { id: "word_form", label: "Word forms (noun/verb/adj/adv)" },
  { id: "error_correction", label: "Fix the error" },
];
const LABEL: Record<string, string> = { ...Object.fromEntries(TOPICS.map((t) => [t.id, t.label])), daily: "Daily lesson (mixed)" };

export const GrammarPanel: React.FC = () => {
  const [quiz, setQuiz] = useState<GrammarQuestion[] | null>(null);
  const [picks, setPicks] = useState<Record<string, string>>({});
  const [result, setResult] = useState<GrammarSubmitResult | null>(null);
  const [scope, setScope] = useState<string | null>(null);
  const [history, setHistory] = useState<Awaited<ReturnType<typeof getGrammarAttempts>>>([]);
  const [dailyNote, setDailyNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ cause: unknown; retry: () => void } | null>(null);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (cause) {
      setError({ cause, retry: () => run(action) });
    } finally {
      setBusy(false);
    }
  };

  const loadHistory = () => getGrammarAttempts().then(setHistory).catch(() => undefined);
  useEffect(() => {
    loadHistory();
  }, []);

  const begin = (topic: string | null, questions: GrammarQuestion[]) => {
    setResult(null);
    setPicks({});
    setScope(topic);
    setQuiz(questions);
  };

  const start = (topic: string | null) =>
    run(async () => {
      setDailyNote(null);
      begin(topic, await getGrammarQuiz(topic, topic ? 6 : 12));
    });

  const startDaily = () =>
    run(async () => {
      const daily = await getGrammarDaily();
      setDailyNote(daily.reason_vi);
      begin(daily.topic ?? "daily", daily.questions);
    });

  const verdict = (id: string) => result?.results.find((r) => r.question_id === id);

  return (
    <div className="surface p-7 space-y-4 mt-6">
      <h3 className="font-display text-2xl font-bold text-slate-900">Grammar map</h3>
      <button onClick={startDaily} disabled={busy} className="px-4 py-2 bg-indigo-700 hover:bg-indigo-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl cursor-pointer">
        3-minute daily lesson (6 questions on your weakest topic)
      </button>
      <div className="flex flex-wrap gap-2">
        {TOPICS.map((t) => (
          <button key={t.label} onClick={() => start(t.id)} disabled={busy} className="px-3 py-1.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700 hover:bg-slate-200 disabled:opacity-50 cursor-pointer">
            {t.label}
          </button>
        ))}
      </div>
      {dailyNote && <p className="text-sm text-slate-600">{dailyNote}</p>}
      {quiz && (
        <div className="space-y-4">
          {quiz.map((q, i) => {
            const r = verdict(q.question_id);
            return (
              <div key={q.question_id} className="space-y-2">
                <p className="font-serif text-lg text-slate-800">{i + 1}. {q.sentence}</p>
                <div className="flex flex-wrap gap-2">
                  {q.options.map((o) => (
                    <button
                      key={o}
                      onClick={() => setPicks({ ...picks, [q.question_id]: o })}
                      disabled={!!result}
                      aria-pressed={picks[q.question_id] === o}
                      className={`px-3 py-1.5 rounded-xl text-sm cursor-pointer ring-1 ${r && o === r.correct_answer ? "bg-emerald-100 ring-emerald-500" : picks[q.question_id] === o ? (r ? "bg-rose-100 ring-rose-500" : "bg-indigo-700 text-white ring-indigo-700") : "ring-slate-900/10 hover:bg-slate-50"}`}
                    >
                      {o}
                    </button>
                  ))}
                </div>
                {r && !r.is_correct && (
                  <div className="text-sm text-slate-600 space-y-1">
                    <p>{r.explanation_vi}</p>
                    {r.why_chosen_vi && <p>Your answer: {r.why_chosen_vi}</p>}
                    {r.contrast_vi && <p className="text-indigo-700">Tiếng Việt vs English: {r.contrast_vi}</p>}
                  </div>
                )}
              </div>
            );
          })}
          {!result ? (
            <button
              onClick={() => run(async () => {
                const res = await submitGrammarQuiz(Object.entries<string>(picks).map(([question_id, choice]) => ({ question_id, choice })), scope);
                setResult(res);
                loadHistory();
              })}
              disabled={busy || Object.keys(picks).length === 0}
              className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl flex items-center gap-2 cursor-pointer"
            >
              {busy && <Loader2 className="w-4 h-4 animate-spin" />} Check answers
            </button>
          ) : (
            <div className="rounded-2xl bg-slate-50 p-4 space-y-1 text-sm" role="status">
              <p className="font-bold text-slate-900">{result.score}/{result.total} correct (only answered questions are graded)</p>
              {Object.entries<{ correct: number; total: number }>(result.by_topic).map(([topic, s]) => (
                <p key={topic} className={s.correct / s.total < 0.6 ? "text-rose-700 font-bold" : "text-slate-700"}>
                  {LABEL[topic]}: {s.correct}/{s.total}{s.correct / s.total < 0.6 && " — practise this"}
                  {result.previous_by_topic?.[topic] && ` (last time ${result.previous_by_topic[topic].correct}/${result.previous_by_topic[topic].total})`}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
      {history.length > 0 && (
        <div className="text-xs text-slate-500 space-y-0.5">
          <p className="font-bold">Past attempts</p>
          {history.slice(0, 5).map((h) => (
            <p key={h.created_at}>{new Date(h.created_at).toLocaleString()} — {h.topic ? LABEL[h.topic] : "Placement"}: {h.score}/{h.total}</p>
          ))}
        </div>
      )}
      {error && <ErrorNotice error={error.cause} onRetry={error.retry} retryLabel="Try again" />}
    </div>
  );
};
