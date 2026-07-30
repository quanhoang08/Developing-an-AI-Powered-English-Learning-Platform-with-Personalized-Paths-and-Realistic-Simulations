import React, { useState } from "react";
import { ErrorJournalItem } from "../types";
import {
  BarChart3,
  Award,
  Zap,
  Flame,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  RefreshCw,
  TrendingUp,
  RotateCcw
} from "lucide-react";

export const AnalyticsView: React.FC = () => {
  const [expandedErrorId, setExpandedErrorId] = useState<string | null>("1");

  const skillBreakdown = [
    { skill: "Listening Comprehension", level: "C1 Advanced", score: 88, color: "bg-purple-600" },
    { skill: "Reading & Vocabulary", level: "B2 Upper", score: 84, color: "bg-indigo-600" },
    { skill: "Writing Mechanics", level: "B2 Upper", score: 78, color: "bg-blue-600" },
    { skill: "Speaking & Pronunciation", level: "B1 Intermediate", score: 72, color: "bg-emerald-600" },
  ];

  const errorCategories = [
    { category: "Grammar & Tenses", count: 45, percentage: 52 },
    { category: "Vocabulary Precision", count: 28, percentage: 32 },
    { category: "Pronunciation & Phonetics", count: 12, percentage: 16 },
  ];

  const errorJournal: ErrorJournalItem[] = [
    {
      id: "1",
      category: "Grammar",
      timeAgo: "2 hours ago",
      originalText: "I go to the park yesterday.",
      correctedText: "I went to the park yesterday.",
      spacedRepetitionLevel: 1,
      explanation: "Actions that occurred at a specific completed time in the past ('yesterday') require the simple past tense verb ('went' instead of 'go')."
    },
    {
      id: "2",
      category: "Vocabulary",
      timeAgo: "Yesterday",
      originalText: "will affect student critical thinking",
      correctedText: "will have an effect on student critical thinking",
      spacedRepetitionLevel: 2,
      explanation: "'Affect' is typically used as a verb (e.g. 'It affects us'). 'Effect' is used as a noun (e.g. 'It has an effect on us')."
    },
    {
      id: "3",
      category: "Pronunciation",
      timeAgo: "3 days ago",
      originalText: "Pervasive (/pərˈvāsiv/)",
      correctedText: "Stress second syllable /vā/",
      spacedRepetitionLevel: 3,
      explanation: "Focus on pronouncing the second syllable with an elongated 'A' sound (/vāv/)."
    }
  ];

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Title & Placement Test Action Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-indigo-600" /> Adaptive Progress & Error Analytics
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Track CEFR level progression, skill radar, error distributions, and spaced repetition mastery.
          </p>
        </div>

        <button className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-2xl shadow-md shadow-indigo-200 flex items-center justify-center gap-2 transition-all cursor-pointer">
          <Sparkles className="w-4 h-4 text-amber-300" /> Start Placement Test
        </button>
      </div>

      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="p-5 bg-white rounded-3xl border border-slate-200/80 shadow-xs">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1">
            CEFR Level
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">B2</span>
            <span className="text-xs text-indigo-600 font-bold bg-indigo-50 px-2 py-0.5 rounded">Upper Intermediate</span>
          </div>
        </div>

        <div className="p-5 bg-white rounded-3xl border border-slate-200/80 shadow-xs">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1">
            Accuracy Rate
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">87%</span>
            <span className="text-xs text-emerald-600 font-bold flex items-center">
              <TrendingUp className="w-3.5 h-3.5 mr-0.5" /> +3.5%
            </span>
          </div>
        </div>

        <div className="p-5 bg-white rounded-3xl border border-slate-200/80 shadow-xs">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1">
            Streak Days
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">14 Days</span>
            <span className="text-xs text-amber-600 font-bold flex items-center">
              <Flame className="w-3.5 h-3.5 mr-0.5 fill-amber-500 text-amber-500" /> Active
            </span>
          </div>
        </div>

        <div className="p-5 bg-white rounded-3xl border border-slate-200/80 shadow-xs">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1">
            Mastered Vocab
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">342 Words</span>
            <span className="text-xs text-slate-500 font-medium">B2 / C1</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* CEFR Skill Radar Breakdown (7 Cols) */}
        <div className="lg:col-span-7 bg-white rounded-3xl border border-slate-200/80 p-6 md:p-8 shadow-xs space-y-6">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 className="font-bold text-sm text-slate-900 flex items-center gap-2">
              <Award className="w-4 h-4 text-indigo-600" /> CEFR 4-Skill Mastery Breakdown
            </h3>
            <span className="text-xs font-bold text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full">
              Overall B2 (82%)
            </span>
          </div>

          <div className="space-y-5">
            {skillBreakdown.map((s, idx) => (
              <div key={idx} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs font-bold">
                  <span className="text-slate-800">{s.skill}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500 font-normal">{s.level}</span>
                    <span className="text-slate-900">{s.score}%</span>
                  </div>
                </div>
                <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                  <div
                    className={`${s.color} h-full rounded-full transition-all duration-500`}
                    style={{ width: `${s.score}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>

          {/* Error Category Distribution */}
          <div className="pt-6 border-t border-slate-100 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Error Distribution Breakdown
            </h4>

            <div className="grid grid-cols-3 gap-3 text-center">
              {errorCategories.map((ec, idx) => (
                <div key={idx} className="p-3 rounded-2xl bg-slate-50 border border-slate-100 space-y-1">
                  <span className="text-2xl font-extrabold text-slate-900">{ec.count}</span>
                  <span className="text-[11px] font-bold text-slate-500 block">{ec.category}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Error Journal & Explanation Tooltips (5 Cols) */}
        <div className="lg:col-span-5 bg-white rounded-3xl border border-slate-200/80 p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 className="font-bold text-sm text-slate-900 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600" /> Recent Error Journal
            </h3>
            <span className="text-xs font-bold text-slate-500">Spaced Repetition</span>
          </div>

          <div className="space-y-3">
            {errorJournal.map((item) => {
              const isExpanded = expandedErrorId === item.id;
              return (
                <div
                  key={item.id}
                  className="p-4 rounded-2xl border border-slate-200/80 space-y-2 bg-slate-50/50 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded">
                      {item.category}
                    </span>
                    <div className="flex items-center gap-2 text-[11px] text-slate-400">
                      <span>Level {item.spacedRepetitionLevel}</span>
                      <span>•</span>
                      <span>{item.timeAgo}</span>
                    </div>
                  </div>

                  <div className="text-xs space-y-1 font-mono">
                    <p className="text-rose-600 line-through">❌ {item.originalText}</p>
                    <p className="text-emerald-700 font-semibold">✅ {item.correctedText}</p>
                  </div>

                  <button
                    onClick={() => setExpandedErrorId(isExpanded ? null : item.id)}
                    className="text-[11px] font-bold text-indigo-600 hover:underline flex items-center gap-1 cursor-pointer pt-1"
                  >
                    {isExpanded ? "Hide Explanation" : "Learn Why"}
                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>

                  {isExpanded && (
                    <div className="p-3 rounded-xl bg-indigo-50/80 border border-indigo-100 text-xs text-indigo-950 italic leading-relaxed animate-in fade-in duration-150">
                      {item.explanation}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
