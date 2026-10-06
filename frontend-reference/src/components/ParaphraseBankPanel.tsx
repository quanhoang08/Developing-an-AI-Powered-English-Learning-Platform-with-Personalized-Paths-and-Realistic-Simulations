// Ngân hàng paraphrase (backlog 3.4): chọn kỹ thuật → viết lại câu gốc → so với mẫu. Không gọi LLM.
import React, { useState } from "react";
import { Loader2 } from "lucide-react";
import { ParaphraseCheck, ParaphraseItem, checkParaphrase, listParaphraseBank } from "../api";
import { ErrorNotice } from "./ErrorNotice";

const TECHNIQUES: Array<{ id: ParaphraseItem["technique"]; label: string }> = [
  { id: "synonyms", label: "Synonyms" },
  { id: "voice", label: "Active ↔ passive" },
  { id: "structure", label: "Change structure" },
  { id: "nominalisation", label: "Nominalisation" },
];

export const ParaphraseBankPanel: React.FC = () => {
  const [active, setActive] = useState<ParaphraseItem["technique"] | null>(null);
  const [items, setItems] = useState<ParaphraseItem[]>([]);
  const [index, setIndex] = useState(0);
  const [text, setText] = useState("");
  const [result, setResult] = useState<ParaphraseCheck | null>(null);
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

  const pick = (technique: ParaphraseItem["technique"]) =>
    run(async () => {
      setActive(technique);
      setItems(await listParaphraseBank(technique));
      setIndex(0);
      setText("");
      setResult(null);
    });

  const current = items[index];

  return (
    <div className="surface p-7 space-y-4 mt-6">
      <h3 className="font-display text-2xl font-bold text-slate-900">Paraphrase bank</h3>
      <div className="flex flex-wrap gap-2">
        {TECHNIQUES.map((t) => (
          <button key={t.id} onClick={() => pick(t.id)} disabled={busy} aria-pressed={active === t.id} className={`px-3 py-1.5 rounded-full text-xs font-bold disabled:opacity-50 cursor-pointer ${active === t.id ? "bg-indigo-700 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>
            {t.label}
          </button>
        ))}
      </div>
      {current && (
        <div className="space-y-3">
          <p className="font-serif text-lg text-slate-800">{current.original}</p>
          <textarea
            name="paraphrase"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Rewrite it in your own words, keeping the meaning…"
            maxLength={500}
            rows={2}
            className="w-full px-4 py-2.5 rounded-xl ring-1 ring-slate-900/10 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
          />
          <div className="flex gap-2">
            <button
              onClick={() => run(async () => setResult(await checkParaphrase(current.id, text.trim())))}
              disabled={busy || text.trim().length < 3}
              className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl flex items-center gap-2 cursor-pointer"
            >
              {busy && <Loader2 className="w-4 h-4 animate-spin" />} Compare with model answer
            </button>
            {index + 1 < items.length && (
              <button onClick={() => { setIndex(index + 1); setText(""); setResult(null); }} className="px-4 py-2 text-sm font-bold text-indigo-700 cursor-pointer">
                Next sentence
              </button>
            )}
          </div>
          {result && (
            <div className="rounded-2xl bg-slate-50 p-4 space-y-2 text-sm" role="status">
              {result.too_similar && (
                <p className="font-bold text-amber-700">Too close to the original — change more than a word or two.</p>
              )}
              {result.model_paraphrases.map((m) => <p key={m} className="font-serif text-slate-800">Model: {m}</p>)}
              <p className="text-slate-600">{result.note_vi}</p>
              <p className="text-xs text-slate-500">This only checks how different your wording is, not whether the meaning is kept.</p>
            </div>
          )}
        </div>
      )}
      {error && <ErrorNotice error={error.cause} onRetry={error.retry} retryLabel="Try again" />}
    </div>
  );
};
