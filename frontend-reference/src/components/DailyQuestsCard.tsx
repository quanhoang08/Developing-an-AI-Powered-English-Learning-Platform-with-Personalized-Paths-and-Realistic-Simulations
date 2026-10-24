// Nhiệm vụ ngày (GET /api/games/quests): tiến độ tính từ hoạt động thật hôm nay, nhận thưởng XP 1 lần/nhiệm vụ.
import React, { useCallback, useEffect, useState } from "react";
import { DailyQuest, claimDailyQuest, listDailyQuests } from "../api";

export const DailyQuestsCard: React.FC = () => {
  const [quests, setQuests] = useState<DailyQuest[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    listDailyQuests().then(setQuests).catch(() => setQuests(null));
  }, []);
  useEffect(() => {
    load();
    // Mọi lần ghi thành công (ôn từ, chơi game...) phát sự kiện này; tải lại để thanh tiến độ luôn mới.
    window.addEventListener("lumina-stats-refresh", load);
    return () => window.removeEventListener("lumina-stats-refresh", load);
  }, [load]);

  const claim = async (id: string) => {
    setError("");
    try {
      await claimDailyQuest(id);
    } catch (e) {
      setError((e as Error).message);
    }
    load();
  };

  if (!quests) return null;
  return (
    <section className="pop-in surface p-6 space-y-4 h-full" aria-label="Daily quests">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-xl font-bold text-slate-900">Daily quests</h3>
        <span className="tag bg-purple-100 text-purple-700 shrink-0">
          {quests.filter((q) => q.claimed).length}/{quests.length} claimed
        </span>
      </div>
      <ul className="space-y-3">
        {quests.map((q) => {
          const done = q.progress >= q.target;
          return (
            <li key={q.id} className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-800">{q.title}</p>
                <div className="mt-1 h-1.5 rounded-full bg-slate-200 overflow-hidden" role="progressbar" aria-valuemin={0} aria-valuemax={q.target} aria-valuenow={q.progress}>
                  <div className="h-full bg-emerald-500 transition-all" style={{ width: `${(q.progress / q.target) * 100}%` }} />
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">{q.progress}/{q.target}</p>
              </div>
              {q.claimed ? (
                <span className="tag bg-emerald-100 text-emerald-700 shrink-0">Claimed</span>
              ) : (
                <button onClick={() => claim(q.id)} disabled={!done} className="btn-primary shrink-0 disabled:opacity-40" aria-label={`Claim ${q.title}`}>
                  +{q.bonus_xp} XP
                </button>
              )}
            </li>
          );
        })}
      </ul>
      {error && <p className="text-sm text-rose-700" role="alert">{error}</p>}
    </section>
  );
};
