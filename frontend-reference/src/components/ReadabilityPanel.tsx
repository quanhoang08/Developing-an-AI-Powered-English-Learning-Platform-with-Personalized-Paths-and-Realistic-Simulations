// Hemingway-style readability + CEFR ước lượng (POST /api/writing/readability): câu dài, bị động, trạng từ, từ khó.
import React, { useState } from "react";
import { ReadabilityResult, checkReadability } from "../api";

const LEVEL_STYLE = { ok: "", long: "bg-amber-100", very_long: "bg-rose-200" } as const;

export const ReadabilityPanel: React.FC = () => {
  const [text, setText] = useState("");
  const [result, setResult] = useState<ReadabilityResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const run = async () => {
    setBusy(true);
    setErr("");
    try {
      setResult(await checkReadability(text));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="pop-in surface p-6 space-y-4" aria-label="Readability checker">
      <h3 className="font-display text-xl font-bold text-slate-900">Readability checker</h3>
      <p className="text-sm text-slate-600">Paste your writing. Long sentences, passive voice and adverbs are highlighted, and words are rated by estimated CEFR level.</p>
      <textarea
        name="readability_text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={5}
        maxLength={6000}
        aria-label="Text to check"
        className="field w-full"
        placeholder="Paste or type English text here…"
      />
      <button onClick={run} disabled={busy || !text.trim()} className="btn-primary">{busy ? "Checking…" : "Check readability"}</button>
      {err && <p className="text-sm text-rose-700" role="alert">{err}</p>}
      {result && (
        <div className="space-y-3" role="region" aria-label="Readability results">
          <p className="text-sm">
            <b>{result.word_count}</b> words · <b>{result.sentence_count}</b> sentences · grade level <b>{result.grade_level}</b> ·{" "}
            <b>{result.long_sentences}</b> long · <b>{result.passive_count}</b> passive · <b>{result.adverbs.length}</b> adverbs
          </p>
          <p className="leading-relaxed text-sm">
            {result.sentences.map((s, i) => (
              <span key={i} className={`${LEVEL_STYLE[s.level]} rounded px-0.5`} title={s.level === "ok" ? undefined : `${s.words} words - consider splitting`}>
                {s.text}{" "}
              </span>
            ))}
          </p>
          <div className="flex flex-wrap gap-1.5" aria-label="CEFR word levels">
            {Object.entries(result.cefr_counts).map(([level, count]) => (
              <span key={level} className="tag bg-slate-100 text-slate-700">{level}: {count}</span>
            ))}
          </div>
          {result.adverbs.length > 0 && <p className="text-sm">Adverbs to reconsider: {result.adverbs.join(", ")}</p>}
          {result.hard_words.length > 0 && <p className="text-sm">Advanced words (C1-C2): {result.hard_words.join(", ")}</p>}
          <p className="text-xs text-slate-500">CEFR levels are estimated from word frequency, not an official word list.</p>
        </div>
      )}
    </section>
  );
};
