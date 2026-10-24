// IPA Pronunciation Heatmap: điểm trung bình từng âm (GET /api/pronunciation/heatmap), cập nhật sau mỗi lần chấm câu mẫu.
import React, { useCallback, useEffect, useState } from "react";
import { getPhonemeHeatmap } from "../api";

const cellStyle = (score: number | null) =>
  score === null ? "bg-slate-100 text-slate-400" : score >= 80 ? "bg-emerald-400 text-white" : score >= 60 ? "bg-amber-400 text-white" : "bg-rose-500 text-white";

export const PhonemeHeatmap: React.FC = () => {
  const [cells, setCells] = useState<Array<{ phoneme: string; attempts: number; avg_score: number | null }> | null>(null);

  const load = useCallback(() => {
    getPhonemeHeatmap().then(setCells).catch(() => setCells(null));
  }, []);
  useEffect(() => {
    load();
    window.addEventListener("lumina-stats-refresh", load);
    return () => window.removeEventListener("lumina-stats-refresh", load);
  }, [load]);

  if (!cells) return null;
  const practised = cells.filter((c) => c.attempts > 0).length;
  return (
    <section className="space-y-3" aria-label="IPA heatmap">
      <h4 className="font-display text-lg font-bold text-slate-900">IPA heatmap</h4>
      <p className="text-sm text-slate-600">
        {practised ? `${practised} of ${cells.length} sounds practised.` : "Practise sentences above to see which sounds are strong (green) or weak (red)."}
      </p>
      <div className="grid grid-cols-6 sm:grid-cols-8 gap-1.5" role="grid">
        {cells.map((c) => (
          <div
            key={c.phoneme}
            role="gridcell"
            title={c.attempts ? `${c.phoneme}: ${c.avg_score} (${c.attempts} tries)` : `${c.phoneme}: not practised yet`}
            aria-label={`${c.phoneme} ${c.avg_score ?? "no data"}`}
            className={`h-10 rounded-lg flex flex-col items-center justify-center text-sm font-bold ${cellStyle(c.avg_score)}`}
          >
            {c.phoneme}
            {c.avg_score !== null && <span className="text-[10px] font-medium">{Math.round(c.avg_score)}</span>}
          </div>
        ))}
      </div>
    </section>
  );
};
