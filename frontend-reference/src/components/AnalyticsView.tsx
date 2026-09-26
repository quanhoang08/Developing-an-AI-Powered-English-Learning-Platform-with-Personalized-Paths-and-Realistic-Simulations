// Trang Adaptive Progress. Dữ liệu thật: Streak/XP (GET /api/streaks), nhật ký lỗi + phân bố lỗi
// (GET /api/adaptive/errors), thói quen học (GET /api/adaptive/habits) và đề luyện tập động.
// LƯU Ý: CEFR level, Accuracy và "Four-skill mastery" vẫn là số demo cứng — backend chưa có
// bảng/endpoint nào chấm điểm theo kỹ năng.
import React, { useCallback, useEffect, useState } from "react";
import { motion } from "motion/react";
import { useLearningStats } from "../stats";
import { AdaptiveError, AdaptiveHabits, getAdaptiveHabits, listAdaptiveErrors } from "../api";
import { AdaptiveQuizPanel } from "./AdaptiveQuizPanel";
import {
  BarChart3,
  Award,
  Flame,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  TrendingUp,
} from "lucide-react";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] as const } },
};

const ERROR_COLORS = ["bg-purple-500", "bg-indigo-600", "bg-amber-400", "bg-blue-400"];
// Backend trả tối đa 100 lỗi/lần, đã xếp theo ưu tiên — phân bố tính trên nhóm lỗi đáng ôn nhất đó.
const ERRORS_FETCHED = 100;
const JOURNAL_SIZE = 5;

const labelize = (errorType: string) =>
  errorType.replace(/_/g, " ").replace(/^./, (first) => first.toUpperCase());

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)} hours ago`;
  return `${Math.round(minutes / (60 * 24))} days ago`;
}

export const AnalyticsView: React.FC = () => {
  const [expandedErrorId, setExpandedErrorId] = useState<string | null>(null);
  const [errors, setErrors] = useState<AdaptiveError[]>([]);
  const [habits, setHabits] = useState<AdaptiveHabits | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const { stats } = useLearningStats();

  const loadAdaptive = useCallback(async () => {
    try {
      const [loadedErrors, loadedHabits] = await Promise.all([listAdaptiveErrors(ERRORS_FETCHED), getAdaptiveHabits()]);
      setErrors(loadedErrors);
      setHabits(loadedHabits);
      setLoadError(null);
    } catch (caught) {
      setLoadError(caught instanceof Error ? caught.message : "Could not load progress data.");
    }
  }, []);

  useEffect(() => {
    loadAdaptive();
  }, [loadAdaptive]);

  const typeCounts = new Map<string, number>();
  errors.forEach((entry) => typeCounts.set(entry.error_type, (typeCounts.get(entry.error_type) ?? 0) + 1));
  const errorCategories = [...typeCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, ERROR_COLORS.length)
    .map(([type, count], index) => ({
      category: labelize(type),
      count,
      percentage: Math.round((count / errors.length) * 100),
      color: ERROR_COLORS[index],
    }));

  const errorJournal = errors.slice(0, JOURNAL_SIZE).map((entry) => ({
    id: entry.id,
    category: labelize(entry.error_type),
    timeAgo: timeAgo(entry.created_at),
    originalText: entry.detail?.original_text ?? "",
    correctedText: entry.detail?.corrected_text ?? "",
    spacedRepetitionLevel: entry.spaced_repetition_level,
    explanation: entry.detail?.explanation ?? "",
  }));

  const skillBreakdown = [
    { skill: "Listening Comprehension", level: "C1 Advanced", score: 88, color: "bg-purple-500" },
    { skill: "Reading & Vocabulary", level: "B2 Upper", score: 84, color: "bg-indigo-600" },
    { skill: "Writing Mechanics", level: "B2 Upper", score: 78, color: "bg-amber-400" },
    { skill: "Speaking & Pronunciation", level: "B1 Intermediate", score: 72, color: "bg-blue-400" },
  ];

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="p-6 md:p-10 max-w-7xl mx-auto space-y-8"
    >
      {/* Title & Placement Test Action Header */}
      <motion.div variants={item} className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-sm italic text-slate-500 mb-1">See where you stand</p>
          <h1 className="font-display text-4xl font-bold text-slate-900 flex items-center gap-3">
            <BarChart3 className="w-8 h-8 text-purple-500" /> Adaptive Progress & Error Analytics
          </h1>
          <p className="text-sm text-slate-500 mt-2 max-w-xl">
            Track CEFR level progression, skill radar, error distributions, and spaced repetition mastery.
          </p>
        </div>

        <button className="px-6 py-3 bg-indigo-700 hover:bg-indigo-800 text-white font-bold text-sm rounded-2xl shadow-[0_16px_26px_-14px_rgba(31,87,73,0.9)] flex items-center justify-center gap-2 transition-all cursor-pointer hover:-translate-y-0.5 active:scale-95">
          <Sparkles className="w-4 h-4 text-amber-300" /> Start Placement Test
        </button>
      </motion.div>

      {/* Top Metric Cards — thẻ CEFR lớn nổi bật, ba thẻ còn lại nhỏ hơn */}
      <div className="grid grid-cols-1 md:grid-cols-6 gap-5">
        <motion.div
          variants={item}
          className="md:col-span-2 relative overflow-hidden p-6 rounded-3xl bg-indigo-900 text-white"
        >
          <div className="absolute -right-10 -bottom-12 w-44 h-44 rounded-full bg-purple-500/30 blur-2xl pointer-events-none" aria-hidden="true" />
          <span className="relative text-sm italic text-indigo-300 block mb-1">CEFR level</span>
          <div className="relative flex items-baseline gap-3">
            <span className="num text-7xl font-bold leading-none">B2</span>
            <span className="tag bg-white/15 text-indigo-100">Upper Intermediate</span>
          </div>
        </motion.div>

        <motion.div variants={item} className="surface md:col-span-1 p-6">
          <span className="text-sm italic text-slate-500 block mb-1">Accuracy</span>
          <span className="num text-4xl font-bold text-slate-900">87%</span>
          <span className="text-xs text-emerald-600 font-bold flex items-center mt-1">
            <TrendingUp className="w-3.5 h-3.5 mr-0.5" /> +3.5%
          </span>
        </motion.div>

        {/* Streak thật từ backend (current_streak trong bảng streaks) */}
        <motion.div variants={item} className="surface md:col-span-2 p-6">
          <span className="text-sm italic text-slate-500 block mb-1">Streak</span>
          <div className="flex items-baseline gap-2">
            <span className="num text-4xl font-bold text-slate-900">{stats.currentStreak}</span>
            <span className="text-sm text-slate-500">{stats.currentStreak === 1 ? "day" : "days"}</span>
            <span className={`text-xs font-bold flex items-center ml-1 ${stats.todayActive ? "text-purple-600" : "text-slate-400"}`}>
              <Flame className={`w-3.5 h-3.5 mr-0.5 ${stats.todayActive ? "fill-purple-500 text-purple-500" : ""}`} />
              {stats.todayActive ? "Done today" : "Not yet today"}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">Longest: <span className="num font-bold">{stats.longestStreak}</span> days</p>
        </motion.div>

        <motion.div variants={item} className="surface md:col-span-1 p-6">
          <span className="text-sm italic text-slate-500 block mb-1">XP</span>
          <span className="num text-4xl font-bold text-slate-900">{stats.totalXp.toLocaleString("en-US")}</span>
          <span className="tag bg-indigo-100 text-indigo-700 mt-1">Level {stats.level}</span>
        </motion.div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* CEFR Skill Radar Breakdown (7 Cols) */}
        <motion.div variants={item} className="surface lg:col-span-7 p-7 md:p-9 space-y-8">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-2xl font-bold text-slate-900 flex items-center gap-2">
              <Award className="w-6 h-6 text-indigo-600" /> Four-skill mastery
            </h3>
            <span className="tag bg-indigo-100 text-indigo-700">
              Overall B2 · 82%
            </span>
          </div>

          <div className="space-y-6">
            {skillBreakdown.map((s, idx) => (
              <div key={idx} className="space-y-2">
                <div className="flex items-baseline justify-between">
                  <span className="text-sm font-semibold text-slate-800">{s.skill}</span>
                  <div className="flex items-baseline gap-3">
                    <span className="text-xs text-slate-500 italic">{s.level}</span>
                    <span className="num text-xl font-bold text-slate-900">{s.score}%</span>
                  </div>
                </div>
                <div className="w-full bg-slate-200/60 h-3 rounded-full overflow-hidden">
                  <motion.div
                    className={`${s.color} h-full rounded-full`}
                    initial={{ width: 0 }}
                    animate={{ width: `${s.score}%` }}
                    transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.3 + idx * 0.1 }}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Error Category Distribution */}
          <div className="pt-6 border-t border-dashed border-slate-200 space-y-4">
            <h4 className="font-display text-lg font-bold text-slate-900">
              Where the mistakes come from
            </h4>

            {errorCategories.length === 0 && (
              <p className="text-sm text-slate-500">
                {loadError ?? "No mistakes recorded yet. They appear here after essays and dictations."}
              </p>
            )}

            <div className="flex h-3 rounded-full overflow-hidden gap-1">
              {errorCategories.map((ec) => (
                <div key={ec.category} className={`${ec.color} first:rounded-l-full last:rounded-r-full`} style={{ width: `${ec.percentage}%` }} />
              ))}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {errorCategories.map((ec) => (
                <div key={ec.category}>
                  <span className="num text-3xl font-bold text-slate-900">{ec.count}</span>
                  <span className="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
                    <span className={`w-2 h-2 rounded-full ${ec.color}`} />
                    {ec.category}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Error Journal & Explanation Tooltips (5 Cols) */}
        <motion.div variants={item} className="surface lg:col-span-5 p-7 space-y-5 lg:self-start">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-2xl font-bold text-slate-900 flex items-center gap-2">
              <AlertCircle className="w-6 h-6 text-rose-500" /> Error journal
            </h3>
            <span className="text-sm italic text-slate-400">Spaced repetition</span>
          </div>

          {errorJournal.length === 0 && (
            <p className="text-sm text-slate-500">Nothing to review yet.</p>
          )}

          <div className="space-y-3">
            {errorJournal.map((entry) => {
              const isExpanded = expandedErrorId === entry.id;
              return (
                <div
                  key={entry.id}
                  className="p-5 rounded-2xl border-l-4 border-rose-300 space-y-2 bg-rose-50/50 hover:bg-rose-50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="tag bg-rose-100 text-rose-700">
                      {entry.category}
                    </span>
                    <div className="flex items-center gap-2 text-[11px] text-slate-400">
                      <span>Level {entry.spacedRepetitionLevel}</span>
                      <span>•</span>
                      <span>{entry.timeAgo}</span>
                    </div>
                  </div>

                  <div className="text-base space-y-1 font-serif">
                    {entry.originalText && (
                      <p className={`${entry.correctedText ? "text-rose-600 line-through decoration-rose-300" : "text-slate-800"}`}>
                        {entry.originalText}
                      </p>
                    )}
                    {entry.correctedText && <p className="text-emerald-800 font-semibold">{entry.correctedText}</p>}
                  </div>

                  {entry.explanation && (
                    <button
                      onClick={() => setExpandedErrorId(isExpanded ? null : entry.id)}
                      aria-expanded={isExpanded}
                      className="text-xs font-bold text-indigo-700 hover:text-indigo-800 flex items-center gap-1 cursor-pointer pt-1"
                    >
                      {isExpanded ? "Hide explanation" : "Learn why"}
                      {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                  )}

                  {isExpanded && (
                    <div className="p-4 rounded-xl bg-[#fffdf8] text-sm text-indigo-950 italic font-serif leading-relaxed animate-rise">
                      {entry.explanation}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </motion.div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <motion.div variants={item} className="lg:col-span-7">
          <AdaptiveQuizPanel onCompleted={loadAdaptive} />
        </motion.div>

        {/* Thói quen học trong 30 ngày gần nhất (GET /api/adaptive/habits) */}
        <motion.div variants={item} className="surface lg:col-span-5 p-7 space-y-4 lg:self-start">
          <h3 className="font-display text-2xl font-bold text-slate-900 flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-emerald-600" /> Study habits
          </h3>
          {habits === null || habits.active_days === 0 ? (
            <p className="text-sm text-slate-500">Study for a few days and your habits will show up here.</p>
          ) : (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <div>
                <dt className="text-slate-500 italic">Active days (30d)</dt>
                <dd className="num text-2xl font-bold text-slate-900">{habits.active_days}</dd>
              </div>
              <div>
                <dt className="text-slate-500 italic">Activities / day</dt>
                <dd className="num text-2xl font-bold text-slate-900">{habits.activities_per_active_day}</dd>
              </div>
              <div>
                <dt className="text-slate-500 italic">Peak hour</dt>
                <dd className="num text-2xl font-bold text-slate-900">
                  {habits.peak_hour === null ? "—" : `${String(habits.peak_hour).padStart(2, "0")}:00`}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500 italic">Favourite skill</dt>
                <dd className="text-2xl font-bold text-slate-900 capitalize">{habits.preferred_skill ?? "—"}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-slate-500 italic">Quiz progress</dt>
                <dd className="font-bold text-slate-900">
                  {habits.progress_trend === "insufficient_data"
                    ? "Take a few quizzes to see your trend"
                    : `${habits.progress_trend} (${(habits.quiz_score_change ?? 0) > 0 ? "+" : ""}${habits.quiz_score_change} pts)`}
                </dd>
              </div>
            </dl>
          )}
        </motion.div>
      </div>
    </motion.div>
  );
};
