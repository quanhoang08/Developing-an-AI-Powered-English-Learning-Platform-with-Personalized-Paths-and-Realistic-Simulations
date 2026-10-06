// Dán bài báo/đoạn văn tiếng Anh → bản viết lại theo level CEFR, bật/tắt phụ đề tiếng Việt từng câu.
import React, { useState } from "react";
import { AdaptedText, adaptText } from "../api";

const LEVELS = ["A2", "B1", "B2", "C1"] as const;

export const AdaptTextPanel: React.FC = () => {
  const [text, setText] = useState("");
  const [level, setLevel] = useState<(typeof LEVELS)[number]>("B1");
  const [result, setResult] = useState<AdaptedText | null>(null);
  const [showVi, setShowVi] = useState(true);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const run = async () => {
    setLoading(true);
    setMessage("");
    try {
      setResult(await adaptText(text.trim(), level));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-900/10 space-y-3 text-sm">
      <h3 className="font-bold text-slate-900">Adapt an article to your level</h3>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={1500}
        rows={5}
        placeholder="Paste an English article or paragraph (up to 1500 characters)…"
        className="w-full px-3 py-2 rounded-xl ring-1 ring-slate-900/10"
      />
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={level}
          onChange={(e) => setLevel(e.target.value as (typeof LEVELS)[number])}
          aria-label="Target level"
          className="px-3 py-2 rounded-xl ring-1 ring-slate-900/10"
        >
          {LEVELS.map((l) => (
            <option key={l}>{l}</option>
          ))}
        </select>
        <button
          onClick={() => void run()}
          disabled={loading || text.trim().length < 20}
          className="px-4 py-2 bg-indigo-700 hover:bg-indigo-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl cursor-pointer"
        >
          {loading ? "Rewriting…" : "Rewrite"}
        </button>
        {result && (
          <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
            <input type="checkbox" checked={showVi} onChange={(e) => setShowVi(e.target.checked)} /> Vietnamese subtitles
          </label>
        )}
        <span role="alert" className="text-xs text-rose-700">{message}</span>
      </div>
      {result && (
        <ol className="space-y-2">
          {result.sentences.map((s, i) => (
            <li key={i} className="rounded-xl bg-slate-50 p-3">
              <p className="font-serif text-slate-900">{s.en}</p>
              {showVi && <p className="text-slate-500 mt-1">{s.vi}</p>}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
};
