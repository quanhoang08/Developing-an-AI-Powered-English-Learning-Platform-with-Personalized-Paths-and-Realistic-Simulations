// Chuông thông báo: gom việc cần làm hôm nay từ dữ liệu thật (thẻ đến hạn, streak, nhiệm vụ nhận thưởng, bài ngữ pháp).
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";
import { motion } from "motion/react";
import { getAccessToken, getGrammarAttempts, listDailyQuests } from "../api";
import { useLearningStats } from "../stats";
import { ActiveTab } from "../types";

interface Note { id: string; text: string; action: "flashcards" | ActiveTab }

const today = () => new Date().toLocaleDateString("en-CA");

export const NotificationBell: React.FC<{ openFlashcards: () => void }> = ({ openFlashcards }) => {
  const { stats } = useLearningStats();
  const [open, setOpen] = useState(false);
  const [claimable, setClaimable] = useState(0);
  const [grammarDone, setGrammarDone] = useState<boolean | null>(null);
  const box = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    if (!getAccessToken()) {
      setClaimable(0);
      setGrammarDone(null);
      return;
    }
    listDailyQuests().then((q) => setClaimable(q.filter((x) => !x.claimed && x.progress >= x.target).length)).catch(() => {});
    getGrammarAttempts().then((rows) => setGrammarDone(rows.some((r) => new Date(r.created_at).toLocaleDateString("en-CA") === today()))).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    window.addEventListener("lumina-stats-refresh", load);
    window.addEventListener("lumina-auth-changed", load);
    const onClick = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("lumina-stats-refresh", load);
      window.removeEventListener("lumina-auth-changed", load);
      window.removeEventListener("mousedown", onClick);
    };
  }, [load]);

  const loggedIn = !!getAccessToken();
  const notes: Note[] = [];
  if (loggedIn) {
    if (stats.restorableStreak > 0) notes.push({ id: "restore", text: `Your ${stats.restorableStreak}-day streak broke. Pass a 10-question quiz today to restore it.`, action: "analytics" });
    else if (!stats.todayActive && stats.currentStreak > 0) notes.push({ id: "streak", text: `Study today to keep your ${stats.currentStreak}-day streak.`, action: "flashcards" });
    if (stats.dueCards > 0) notes.push({ id: "due", text: `${stats.dueCards} flashcard${stats.dueCards === 1 ? "" : "s"} due for review.`, action: "flashcards" });
    if (claimable > 0) notes.push({ id: "quests", text: `${claimable} daily quest reward${claimable === 1 ? "" : "s"} ready to claim.`, action: "games" });
    if (grammarDone === false) notes.push({ id: "grammar", text: "Your 3-minute grammar lesson is waiting.", action: "tools" });
  }

  const choose = (note: Note) => {
    setOpen(false);
    if (note.action === "flashcards") openFlashcards();
    else window.dispatchEvent(new CustomEvent("lumina-navigate", { detail: note.action }));
  };

  return (
    <div ref={box} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative p-3 rounded-full text-slate-500 hover:bg-slate-900/5 hover:text-slate-700 transition-colors"
        aria-label={notes.length ? `Notifications (${notes.length})` : "Notifications"}
        aria-expanded={open}
      >
        <motion.span
          className="block"
          style={{ transformOrigin: "50% 15%" }}
          animate={notes.length ? { rotate: [0, -16, 14, -10, 6, 0] } : undefined}
          whileHover={{ rotate: [0, -16, 14, -10, 6, 0], transition: { duration: 0.7 } }}
          transition={{ duration: 0.9, repeat: Infinity, repeatDelay: 7 }}
        >
          <Bell className="w-5 h-5" />
        </motion.span>
        {notes.length > 0 && (
          <span className="absolute top-1.5 right-1.5 min-w-4 h-4 px-1 rounded-full bg-purple-500 text-white text-[10px] font-bold flex items-center justify-center ring-2 ring-paper">{notes.length}</span>
        )}
      </button>
      {open && (
        <div role="dialog" aria-label="Notifications" className="absolute right-0 top-full mt-2 w-80 z-30 bg-[#fffdf8] rounded-2xl ring-1 ring-slate-900/10 shadow-[0_18px_36px_-16px_rgba(95,70,30,0.4)] p-2">
          {!loggedIn ? (
            <p className="px-3 py-3 text-sm text-slate-600">Sign in to see your reminders.</p>
          ) : notes.length === 0 ? (
            <p className="px-3 py-3 text-sm text-slate-600">All caught up. Nothing is waiting for you right now.</p>
          ) : (
            <ul>
              {notes.map((n) => (
                <li key={n.id}>
                  <button onClick={() => choose(n)} className="w-full text-left px-3 py-2.5 rounded-xl text-sm hover:bg-indigo-50 text-slate-800">
                    {n.text}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};
