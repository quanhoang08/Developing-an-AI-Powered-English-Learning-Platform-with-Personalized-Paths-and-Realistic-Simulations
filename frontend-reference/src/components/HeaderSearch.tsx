// Ô tìm kiếm ở Header (Ctrl/Cmd+K): nhảy nhanh tới tính năng + tra từ trong kho từ chủ đề, có nút lưu từ vào flashcard.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Command, Search } from "lucide-react";
import { getAccessToken, saveVocabulary } from "../api";
import { ActiveTab } from "../types";
import { GameWord, loadGameWords } from "./games/shared";

interface Feature { label: string; tab: ActiveTab; keywords: string }

// Chỉ mục tính năng: từ khóa tiếng Anh + tiếng Việt không dấu thường gõ.
const FEATURES: Feature[] = [
  { label: "Dashboard", tab: "dashboard", keywords: "home streak xp tong quan trang chu quiz quests" },
  { label: "Knowledge Space (upload documents, chat with notes)", tab: "notebook", keywords: "notebook upload docx pdf document rag chat tai lieu ghi chu" },
  { label: "Reading: classic and skim and scan", tab: "reading", keywords: "reading passage skim scan tfng story doc hieu bai doc" },
  { label: "Listening: podcast and dictation", tab: "listening", keywords: "listening podcast dictation transcript nghe chep chinh ta" },
  { label: "Movie context (find a phrase in films)", tab: "listening", keywords: "movie film subtitle video phim phu de youglish" },
  { label: "Speaking: conversation, live call, captions, pronunciation lab", tab: "speaking", keywords: "speaking conversation roleplay live call captions slang noi hoi thoai phat am pronunciation shadowing heatmap ipa" },
  { label: "Writing Lab (essay grading, rephrase)", tab: "writing", keywords: "writing essay rubric rephrase grammar check viet bai luan" },
  { label: "Vocab and grammar tools", tab: "tools", keywords: "vocab vocabulary grammar paraphrase readability cefr hemingway word family collocation mnemonic confusing pairs wordlist nawl tsl tu vung ngu phap" },
  { label: "IELTS and TOEIC prep", tab: "exam", keywords: "ielts toeic mock test band exam goal study plan thi thu luyen thi" },
  { label: "Games: Wordle, Memory Match, Word Rain, Bubble Pop...", tab: "games", keywords: "game wordle memory match word rain bubble pop word search chain detective dictation racer voice runner speed quiz 1v1 tro choi" },
  { label: "Rewards: coins, shop, gacha, hearts, daily quests", tab: "games", keywords: "coins shop gacha hearts booster avatar quests xu cua hang nhiem vu" },
  { label: "Community: friends, classes, study guild", tab: "community", keywords: "friends leaderboard class classroom teacher guild clan ban be lop hoc bang hoi" },
  { label: "Adaptive Progress (error journal, quizzes, analytics)", tab: "analytics", keywords: "analytics progress adaptive errors quiz restore streak so loi tien do" },
];

const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d");

type Result = { kind: "feature"; feature: Feature } | { kind: "word"; word: GameWord };

export const HeaderSearch: React.FC = () => {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [words, setWords] = useState<GameWord[]>([]);
  const [saved, setSaved] = useState<Record<string, string>>({});
  const input = useRef<HTMLInputElement>(null);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        input.current?.focus();
        setOpen(true);
      }
    };
    const onClick = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, []);

  // Kho từ chỉ tải khi người dùng đã đăng nhập và bắt đầu dùng ô tìm kiếm.
  const ensureWords = () => {
    if (words.length === 0 && getAccessToken()) loadGameWords().then(setWords).catch(() => {});
  };

  const results = useMemo<Result[]>(() => {
    const q = norm(query.trim());
    if (!q) return [];
    const parts = q.split(/\s+/);
    const features = FEATURES.filter((f) => {
      const hay = norm(f.label + " " + f.keywords);
      return parts.every((p) => hay.includes(p));
    }).map((feature): Result => ({ kind: "feature", feature }));
    const matched = words
      .filter((w) => norm(w.term).includes(q) || norm(w.meaning_vi).includes(q))
      .sort((a, b) => Number(norm(b.term).startsWith(q)) - Number(norm(a.term).startsWith(q)))
      .slice(0, 5)
      .map((word): Result => ({ kind: "word", word }));
    return [...features.slice(0, 6), ...matched];
  }, [query, words]);

  const go = (r: Result) => {
    if (r.kind === "feature") {
      window.dispatchEvent(new CustomEvent("lumina-navigate", { detail: r.feature.tab }));
      setOpen(false);
      setQuery("");
      input.current?.blur();
    }
  };

  const save = async (word: GameWord) => {
    setSaved((s) => ({ ...s, [word.term]: "saving" }));
    try {
      await saveVocabulary({ term: word.term, definition: word.meaning_vi, sourceUrl: "search:topic-words", exampleSentence: "", synonyms: [], antonyms: [] });
      setSaved((s) => ({ ...s, [word.term]: "saved" }));
    } catch (e) {
      setSaved((s) => ({ ...s, [word.term]: (e as Error).message === "duplicate_vocab" ? "saved" : "failed" }));
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setOpen(false);
      input.current?.blur();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && results[active]) {
      go(results[active]);
    }
  };

  return (
    <div ref={box} className="relative flex-1 min-w-0 group">
      <Search className="w-5 h-5 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2 transition-colors group-focus-within:text-indigo-600" />
      <input
        ref={input}
        type="text"
        value={query}
        role="combobox"
        aria-expanded={open && results.length > 0}
        aria-controls="header-search-results"
        aria-label="Search features and words"
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onFocus={() => {
          ensureWords();
          setOpen(true);
        }}
        onKeyDown={onKeyDown}
        placeholder="Search features or words..."
        className="w-full pl-12 pr-16 py-3 text-base bg-[#fffdf8] rounded-full ring-1 ring-slate-900/10 focus:outline-none focus:ring-2 focus:ring-indigo-500/60 text-slate-800 placeholder-slate-400 transition-shadow shadow-[0_6px_16px_-12px_rgba(95,70,30,0.5)]"
      />
      <div className="absolute right-4 top-1/2 -translate-y-1/2 hidden sm:flex items-center gap-0.5 text-xs text-slate-400 font-mono pointer-events-none">
        <Command className="w-3 h-3" /> K
      </div>
      {open && query.trim() && (
        <ul id="header-search-results" role="listbox" className="absolute left-0 right-0 top-full mt-2 z-30 bg-[#fffdf8] rounded-2xl ring-1 ring-slate-900/10 shadow-[0_18px_36px_-16px_rgba(95,70,30,0.4)] p-1.5 max-h-96 overflow-auto">
          {results.length === 0 && <li className="px-3 py-2 text-sm text-slate-500">No match. Try a feature name or an English word.</li>}
          {results.map((r, i) =>
            r.kind === "feature" ? (
              <li key={r.feature.label} role="option" aria-selected={i === active} onMouseEnter={() => setActive(i)} onClick={() => go(r)} className={`px-3 py-2 rounded-xl text-sm cursor-pointer ${i === active ? "bg-indigo-50 text-indigo-900" : ""}`}>
                {r.feature.label}
                <span className="ml-2 text-xs text-slate-400">go to tab</span>
              </li>
            ) : (
              <li key={r.word.term} role="option" aria-selected={i === active} onMouseEnter={() => setActive(i)} className={`px-3 py-2 rounded-xl text-sm flex items-center gap-2 ${i === active ? "bg-indigo-50" : ""}`}>
                <span className="font-semibold">{r.word.term}</span>
                <span className="flex-1 min-w-0 truncate text-slate-600">{r.word.meaning_vi}</span>
                <button onClick={() => save(r.word)} disabled={saved[r.word.term] === "saving" || saved[r.word.term] === "saved"} className="text-xs font-bold text-indigo-700 disabled:text-emerald-700 shrink-0">
                  {saved[r.word.term] === "saved" ? "Saved" : saved[r.word.term] === "failed" ? "Retry" : "+ Save"}
                </button>
              </li>
            ),
          )}
        </ul>
      )}
    </div>
  );
};
