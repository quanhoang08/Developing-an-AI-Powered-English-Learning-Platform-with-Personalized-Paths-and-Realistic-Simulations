// Nhắc bài ngữ pháp 3 phút/ngày (backlog 3.8): hiện đã làm hôm nay chưa + nhắc bằng Notification của trình duyệt.
// Chỉ nhắc khi tab Lumina đang mở (không cần dịch vụ push/email trả phí).
import React, { useEffect, useState } from "react";
import { getGrammarAttempts } from "../api";
import { ActiveTab } from "../types";

const HOUR_KEY = "lumina_grammar_reminder_hour";
const NOTIFIED_KEY = "lumina_grammar_notified_on";

const today = () => new Date().toLocaleDateString("en-CA");

const readHour = (): number | null => {
  try {
    const raw = localStorage.getItem(HOUR_KEY);
    return raw === null ? null : Number(raw);
  } catch {
    return null;
  }
};

export const GrammarDailyCard: React.FC<{ setActiveTab: (tab: ActiveTab) => void }> = ({ setActiveTab }) => {
  const [doneToday, setDoneToday] = useState<boolean | null>(null);
  const [hour, setHour] = useState<number | null>(readHour);
  const supported = typeof Notification !== "undefined";

  useEffect(() => {
    getGrammarAttempts()
      .then((rows) => setDoneToday(rows.some((r) => new Date(r.created_at).toLocaleDateString("en-CA") === today())))
      .catch(() => setDoneToday(null));
  }, []);

  useEffect(() => {
    if (hour === null || doneToday !== false || !supported) return;
    const tick = () => {
      if (new Date().getHours() < hour || Notification.permission !== "granted") return;
      try {
        if (localStorage.getItem(NOTIFIED_KEY) === today()) return;
        localStorage.setItem(NOTIFIED_KEY, today());
      } catch {
        return;
      }
      new Notification("Lumina", { body: "Your 3-minute grammar lesson is waiting." });
    };
    tick();
    const timer = window.setInterval(tick, 60_000);
    return () => window.clearInterval(timer);
  }, [hour, doneToday, supported]);

  const enable = async (value: number | null) => {
    if (value !== null && Notification.permission !== "granted" && (await Notification.requestPermission()) !== "granted") return;
    try {
      if (value === null) localStorage.removeItem(HOUR_KEY);
      else localStorage.setItem(HOUR_KEY, String(value));
    } catch {
      /* lưu không được thì chỉ nhắc trong phiên này */
    }
    setHour(value);
  };

  if (doneToday === null) return null;

  return (
    <section className="pop-in surface p-6 space-y-4 h-full" aria-label="Daily grammar lesson">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-xl font-bold text-slate-900">Daily grammar lesson</h3>
        <span className={`tag shrink-0 ${doneToday ? "bg-emerald-100 text-emerald-700" : "bg-purple-100 text-purple-700"}`}>
          {doneToday ? "Done" : "3 min"}
        </span>
      </div>
      <p className="text-sm text-slate-600">{doneToday ? "Done for today. Nice work." : "Not done yet today: 6 questions on your weakest topic."}</p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        {!doneToday && (
          <button onClick={() => setActiveTab("writing")} className="btn-primary">
            Open Grammar map
          </button>
        )}
        {supported && (
          <label className="text-xs text-slate-600 flex flex-wrap items-center gap-2">
            Remind me at
            <select
              value={hour ?? ""}
              onChange={(e) => enable(e.target.value === "" ? null : Number(e.target.value))}
              className="field !py-1 !px-2 !rounded-lg"
            >
              <option value="">Off</option>
              {[8, 12, 18, 20, 21].map((h) => <option key={h} value={h}>{h}:00</option>)}
            </select>
            <span className="text-slate-400">(only while Lumina is open in a tab)</span>
          </label>
        )}
      </div>
    </section>
  );
};
