// Mục tiêu band IELTS + ngày thi → kế hoạch học mỗi ngày (GET /api/users/me/study-plan, backlog 2.5).
import React, { useEffect, useState } from "react";
import { StudyPlan, getStudyPlan, setExamGoal } from "../api";

const BANDS = [5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5];

export const ExamGoalCard: React.FC = () => {
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [band, setBand] = useState("");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const load = async () => {
    try {
      const next = await getStudyPlan();
      setPlan(next);
      setBand(next.target_band?.toString() ?? "");
      setDate(next.exam_date ?? "");
    } catch {
      setFailed(true);
    }
  };
  useEffect(() => {
    void load();
  }, []);

  const save = async () => {
    setBusy(true);
    setFailed(false);
    try {
      await setExamGoal(band ? Number(band) : null, date || null);
      await load();
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="surface p-6 space-y-4 mt-6">
      <h3 className="font-display text-xl font-bold text-slate-900">IELTS goal &amp; daily plan</h3>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs font-bold text-slate-600 space-y-1">
          Target band
          <select name="target_band" value={band} onChange={(e) => setBand(e.target.value)} className="block px-3 py-2 rounded-xl ring-1 ring-slate-900/10 text-sm">
            <option value="">—</option>
            {BANDS.map((b) => <option key={b} value={b}>{b.toFixed(1)}</option>)}
          </select>
        </label>
        <label className="text-xs font-bold text-slate-600 space-y-1">
          Exam date
          <input name="exam_date" type="date" value={date} onChange={(e) => setDate(e.target.value)} className="block px-3 py-2 rounded-xl ring-1 ring-slate-900/10 text-sm" />
        </label>
        <button onClick={save} disabled={busy} className="px-4 py-2 bg-indigo-700 hover:bg-indigo-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl cursor-pointer">
          Save goal
        </button>
      </div>
      {failed && <p className="text-sm text-rose-700" role="alert">Could not reach the server — try again.</p>}
      {plan && plan.target_band !== null && (
        <div className="space-y-2 text-sm text-slate-700" role="status">
          <p>
            {plan.days_left !== null && plan.days_left >= 0 && <b>{plan.days_left} days to go · </b>}
            {plan.current_band !== null ? `latest mock ≈ ${plan.current_band.toFixed(1)} (gap ${plan.band_gap?.toFixed(1)})` : "no mock test yet"}
            {" · "}{plan.daily_minutes} min/day
          </p>
          <ul className="list-disc ml-5">
            {plan.daily_tasks.map((t) => <li key={t.task}>{t.minutes} min — {t.task}</li>)}
          </ul>
          {plan.notes.map((note) => <p key={note} className="text-xs text-amber-700">{note}</p>)}
        </div>
      )}
    </section>
  );
};
