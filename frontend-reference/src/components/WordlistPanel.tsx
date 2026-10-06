// Từ vựng theo chủ đề thi: độ phủ NAWL (IELTS) / TSL (TOEIC) của từ đã lưu, gợi ý thêm từ, và đo độ phủ của một đoạn văn.
// Dữ liệu danh sách: Browne et al., newgeneralservicelist.com, CC BY-SA 4.0.
import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { UnitImportResult, VocabTopic, WordlistCoverage, WordlistName, addVocabTopic, addWordlistWords, listVocabTopics, getWordlistCoverage, getVocabUnitWords, getVocabUnits, getWordlistTextCoverage, importVocabUnit } from "../api";

const TABS: { id: WordlistName; label: string }[] = [
  { id: "nawl", label: "IELTS academic (NAWL)" },
  { id: "tsl", label: "TOEIC (TSL)" },
];

// Từ vựng theo chủ đề (kinh tế, y tế...): danh sách tự soạn có sẵn nghĩa tiếng Việt, thêm cả chủ đề vào lịch ôn bằng 1 nút.
const TopicWords: React.FC = () => {
  const [topics, setTopics] = useState<VocabTopic[]>([]);
  const [openId, setOpenId] = useState("");
  const [note, setNote] = useState("");
  const load = () => listVocabTopics().then(setTopics).catch((e) => setNote(e instanceof Error ? e.message : "Could not load topics."));
  useEffect(() => { void load(); }, []);
  const open = topics.find((t) => t.id === openId);
  const missing = open ? open.words.filter((w) => !w.saved).length : 0;
  return (
    <div className="rounded-2xl bg-slate-50 p-4 space-y-3 text-sm">
      <h4 className="font-bold text-slate-900">Words by topic</h4>
      <div className="flex flex-wrap gap-2">
        {topics.map((t) => (
          <button key={t.id} aria-pressed={t.id === openId} onClick={() => { setOpenId(t.id); setNote(""); }}
            className={`px-3 py-1.5 rounded-full text-xs font-bold cursor-pointer ${t.id === openId ? "bg-slate-900 text-white" : "bg-white ring-1 ring-slate-900/10 text-slate-700"}`}>
            {t.title} ({t.words.filter((w) => w.saved).length}/{t.words.length})
          </button>
        ))}
      </div>
      {open && (
        <>
          <ul className="grid sm:grid-cols-2 gap-x-6 gap-y-1">
            {open.words.map((w) => (
              <li key={w.term} className={w.saved ? "text-slate-400" : "text-slate-800"}>
                <b>{w.term}</b> — {w.meaning_vi}{w.saved && " ✓"}
              </li>
            ))}
          </ul>
          <button disabled={missing === 0}
            onClick={() => void addVocabTopic(open.id).then((added) => { setNote(`Added ${added.length} word(s) to your review.`); return load(); }).catch((e) => setNote(e instanceof Error ? e.message : "Could not add."))}
            className="px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl cursor-pointer">
            {missing === 0 ? "All words saved" : `Add ${missing} missing word(s)`}
          </button>
        </>
      )}
      {note && <p className="text-xs text-slate-600" role="status">{note}</p>}
    </div>
  );
};

export const WordlistPanel: React.FC = () => {
  const [list, setList] = useState<WordlistName>("nawl");
  const [cov, setCov] = useState<WordlistCoverage | null>(null);
  const [text, setText] = useState("");
  const [textCov, setTextCov] = useState<{ tokens: number; percent: number; words_found: string[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [unitText, setUnitText] = useState("");
  const [unitResult, setUnitResult] = useState<UnitImportResult | null>(null);
  const [unitName, setUnitName] = useState("");
  const [units, setUnits] = useState<Array<{ unit: string; count: number }>>([]);
  const [unitWords, setUnitWords] = useState<{ unit: string; terms: string[] } | null>(null);
  const loadUnits = () => getVocabUnits().then(setUnits).catch(() => undefined);
  useEffect(() => { void loadUnits(); }, []);

  const load = () => getWordlistCoverage(list).then(setCov).catch((e) => setMessage(e instanceof Error ? e.message : "Could not load."));
  useEffect(() => {
    setCov(null);
    setTextCov(null);
    setMessage("");
    void load();
  }, [list]);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setMessage("");
    try {
      await action();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-4 border-t border-dashed border-slate-200 pt-6">
      <h3 className="font-display text-2xl font-bold text-slate-900">Exam word lists</h3>
      <div role="tablist" className="flex gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={list === tab.id}
            onClick={() => setList(tab.id)}
            className={`px-3 py-1.5 rounded-full text-xs font-bold cursor-pointer ${list === tab.id ? "bg-indigo-700 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {cov && (
        <div className="space-y-3">
          <p className="text-sm text-slate-700">
            You have saved <b className="num">{cov.known}</b> of <b className="num">{cov.total}</b> words ({cov.percent}%).
          </p>
          <div className="h-2 rounded-full bg-slate-100 overflow-hidden" role="progressbar" aria-valuenow={cov.percent} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full bg-indigo-600" style={{ width: `${cov.percent}%` }} />
          </div>
          {cov.suggestions.length > 0 && (
            <div className="flex flex-wrap gap-2 items-center">
              <span className="text-xs text-slate-500">Words to learn next:</span>
              {cov.suggestions.map((word) => (
                <button
                  key={word}
                  disabled={busy}
                  onClick={() => void run(async () => { await addWordlistWords(list, [word]); await load(); })}
                  title="Add to my vocabulary"
                  className="px-3 py-1.5 rounded-full bg-slate-100 hover:bg-indigo-100 text-xs font-bold text-slate-700 disabled:opacity-50 cursor-pointer"
                >
                  + {word}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={20000}
        rows={3}
        placeholder="Paste a passage to see how much of this list it uses…"
        className="w-full px-4 py-2.5 rounded-xl ring-1 ring-slate-900/10 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
      />
      <button
        onClick={() => void run(async () => setTextCov(await getWordlistTextCoverage(list, text)))}
        disabled={busy || !text.trim()}
        className="px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl flex items-center gap-2 cursor-pointer"
      >
        {busy && <Loader2 className="w-4 h-4 animate-spin" />} Check coverage
      </button>
      {textCov && (
        <p className="text-sm text-slate-700" role="status">
          <b className="num">{textCov.percent}%</b> of the <span className="num">{textCov.tokens}</span> words are on this list
          {textCov.words_found.length > 0 && <>: {textCov.words_found.join(", ")}</>}.
        </p>
      )}
      <div className="space-y-2 border-t border-dashed border-slate-200 pt-4">
        <h4 className="text-sm font-bold text-slate-900">Import a textbook unit</h4>
        <input
          value={unitName}
          onChange={(e) => setUnitName(e.target.value)}
          maxLength={100}
          placeholder="Unit name (optional), e.g. Unit 3 - Environment"
          className="w-full px-4 py-2 rounded-xl ring-1 ring-slate-900/10 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
        />
        <textarea
          value={unitText}
          onChange={(e) => setUnitText(e.target.value)}
          rows={4}
          placeholder={"One word per line, e.g.\nsustain - duy trì\nrenewable: có thể tái tạo\nenvironment   (meaning looked up by AI)"}
          className="w-full px-4 py-2.5 rounded-xl ring-1 ring-slate-900/10 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
        />
        <button
          onClick={() => void run(async () => {
            const result = await importVocabUnit(unitText.split("\n").filter((l) => l.trim()), unitName.trim());
            void loadUnits();
            setUnitResult(result);
            // Giữ lại các dòng chưa xử lý (chưa tra nghĩa) để người học bấm gửi tiếp.
            setUnitText(result.skipped_no_definition.join("\n"));
            await load();
          })}
          disabled={busy || !unitText.trim()}
          className="px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl flex items-center gap-2 cursor-pointer"
        >
          {busy && <Loader2 className="w-4 h-4 animate-spin" />} Add unit words
        </button>
        {unitResult && (
          <p className="text-sm text-slate-700" role="status">
            Added <b className="num">{unitResult.created.length}</b> word(s)
            {unitResult.duplicates.length > 0 && <>, already saved: {unitResult.duplicates.join(", ")}</>}
            {unitResult.invalid.length > 0 && <>, skipped invalid lines: {unitResult.invalid.join(", ")}</>}
            {unitResult.skipped_no_definition.length > 0 && <>. {unitResult.skipped_no_definition.length} word(s) without a meaning are left in the box (max 5 AI lookups per click) — press Add again.</>}
          </p>
        )}
        {units.length > 0 && (
          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-xs text-slate-500">My units:</span>
            {units.map((u) => (
              <button key={u.unit} onClick={() => void getVocabUnitWords(u.unit).then((w) => setUnitWords({ unit: u.unit, terms: w.map((x) => x.term) }))}
                className="px-3 py-1.5 rounded-full bg-slate-100 hover:bg-indigo-100 text-xs font-bold text-slate-700 cursor-pointer">{u.unit} ({u.count})</button>
            ))}
          </div>
        )}
        {unitWords && <p className="text-sm text-slate-700">{unitWords.unit}: {unitWords.terms.join(", ")}</p>}
      </div>
      <TopicWords />
      <p role="alert" className="text-xs text-rose-700">{message}</p>
      <p className="text-[11px] text-slate-400">
        Word lists: NAWL / TSL by Browne et al., newgeneralservicelist.com, CC BY-SA 4.0.
      </p>
    </section>
  );
};
