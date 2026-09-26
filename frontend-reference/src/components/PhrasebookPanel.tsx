// Thư viện slang/cụm thoại có nguồn tham chiếu + Sổ tay cá nhân (feature-speaking.md mục 2, 4).
import React, { useCallback, useEffect, useState } from "react";
import { BookMarked, Bookmark, BookOpen, Check, Loader2 } from "lucide-react";
import { listPhrasebook, listSlang, PhrasebookEntry, savePhrase, SlangPhrase } from "../api";

const FORMALITY_FILTERS = ["all", "casual", "neutral", "formal"] as const;

const FORMALITY_STYLE: Record<string, string> = {
  casual: "bg-amber-50 text-amber-700",
  neutral: "bg-sky-50 text-sky-700",
  formal: "bg-violet-50 text-violet-700",
};

interface PhrasebookPanelProps {
  // Tăng lên khi nơi khác (Speaking) vừa lưu cụm, để sổ tay tự tải lại.
  refreshKey?: number;
}

export const PhrasebookPanel: React.FC<PhrasebookPanelProps> = ({ refreshKey = 0 }) => {
  const [tab, setTab] = useState<"library" | "saved">("library");
  const [formality, setFormality] = useState<(typeof FORMALITY_FILTERS)[number]>("all");
  const [library, setLibrary] = useState<SlangPhrase[]>([]);
  const [saved, setSaved] = useState<PhrasebookEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [slang, entries] = await Promise.all([
        listSlang(formality === "all" ? undefined : formality),
        listPhrasebook(),
      ]);
      setLibrary(slang);
      setSaved(entries);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load phrases.");
    } finally {
      setIsLoading(false);
    }
  }, [formality]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const savedSlangIds = new Set(saved.map((entry) => entry.slang_phrase_id).filter(Boolean));

  const handleSave = async (phrase: SlangPhrase) => {
    setSavingId(phrase.id);
    try {
      const entry = await savePhrase({ slangPhraseId: phrase.id });
      setSaved((current) => (current.some((item) => item.id === entry.id) ? current : [entry, ...current]));
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save phrase.");
    } finally {
      setSavingId(null);
    }
  };

  const visibleSaved =
    formality === "all" ? saved : saved.filter((entry) => entry.formality_level === formality);

  return (
    <div className="surface p-6 space-y-4">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="inline-flex p-1 bg-paper-deep rounded-full">
          <button
            onClick={() => setTab("library")}
            className={`px-3.5 py-1.5 rounded-full text-xs font-bold transition-colors ${tab === "library" ? "bg-indigo-700 text-white" : "text-slate-600 hover:text-slate-900"}`}
          >
            <BookOpen className="w-3.5 h-3.5 inline mr-1" /> Slang library
          </button>
          <button
            onClick={() => setTab("saved")}
            className={`px-3.5 py-1.5 rounded-full text-xs font-bold transition-colors ${tab === "saved" ? "bg-indigo-700 text-white" : "text-slate-600 hover:text-slate-900"}`}
          >
            <BookMarked className="w-3.5 h-3.5 inline mr-1" /> My phrasebook ({saved.length})
          </button>
        </div>
        <select
          value={formality}
          onChange={(event) => setFormality(event.target.value as (typeof FORMALITY_FILTERS)[number])}
          aria-label="Formality filter"
          className="px-3 py-1.5 text-xs bg-white ring-1 ring-slate-900/10 rounded-full focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
        >
          {FORMALITY_FILTERS.map((level) => (
            <option key={level} value={level}>
              {level === "all" ? "All levels" : level}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="text-[11px] text-red-600">{error}</p>}
      {isLoading && (
        <p className="text-xs text-slate-500 flex items-center gap-1.5">
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading...
        </p>
      )}

      <div className="max-h-[420px] overflow-y-auto space-y-2 pr-1">
        {tab === "library" &&
          library.map((phrase) => {
            const isSaved = savedSlangIds.has(phrase.id);
            return (
              <div key={phrase.id} className="p-4 rounded-2xl bg-paper-deep/60 hover:bg-paper-deep transition-colors">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="font-display text-lg font-bold text-slate-900">{phrase.phrase_text}</span>
                    <span className={`tag ml-2 ${FORMALITY_STYLE[phrase.formality_level] ?? ""}`}>
                      {phrase.formality_level}
                    </span>
                  </div>
                  <button
                    onClick={() => handleSave(phrase)}
                    disabled={isSaved || savingId === phrase.id}
                    aria-label={isSaved ? "Saved" : "Save phrase"}
                    className="p-2 rounded-full text-indigo-700 hover:bg-indigo-100 disabled:text-emerald-600 transition-colors active:scale-90"
                  >
                    {isSaved ? <Check className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-xs text-slate-600 mt-1">{phrase.meaning}</p>
                {phrase.example_sentence && (
                  <p className="text-xs text-slate-500 italic mt-1">“{phrase.example_sentence}”</p>
                )}
                <p className="text-[10px] text-slate-400 mt-1">Source: {phrase.source_reference}</p>
              </div>
            );
          })}

        {tab === "saved" &&
          (visibleSaved.length === 0 ? (
            <p className="text-xs text-slate-500 py-6 text-center">
              Nothing saved yet. Save phrases from the library or from the cat’s suggestions.
            </p>
          ) : (
            visibleSaved.map((entry) => (
              <div key={entry.id} className="p-4 rounded-2xl bg-paper-deep/60 hover:bg-paper-deep transition-colors">
                <span className="font-display text-lg font-bold text-slate-900">{entry.phrase_text}</span>
                {entry.formality_level && (
                  <span className={`tag ml-2 ${FORMALITY_STYLE[entry.formality_level] ?? ""}`}>
                    {entry.formality_level}
                  </span>
                )}
                {entry.meaning && <p className="text-xs text-slate-600 mt-1">{entry.meaning}</p>}
                {entry.example_sentence && (
                  <p className="text-xs text-slate-500 italic mt-1">“{entry.example_sentence}”</p>
                )}
                {entry.source_reference && (
                  <p className="text-[10px] text-slate-400 mt-1">Source: {entry.source_reference}</p>
                )}
              </div>
            ))
          ))}
      </div>
    </div>
  );
};
