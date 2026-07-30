import React from "react";
import { ActiveTab } from "../types";
import {
  Flame,
  Zap,
  BookOpen,
  Headphones,
  Mic,
  PenTool,
  Clock,
  ArrowUpRight,
  Sparkles,
  TrendingUp,
  Award,
  ChevronRight,
  PlayCircle
} from "lucide-react";

interface DashboardViewProps {
  setActiveTab: (tab: ActiveTab) => void;
  openFlashcards: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  setActiveTab,
  openFlashcards,
}) => {
  const recentMaterials = [
    {
      id: "1",
      title: "Business English: Negotiation Tactics",
      category: "Reading & Vocab",
      level: "B2 Upper",
      timeAgo: "2 hours ago",
      tab: "reading" as ActiveTab,
      image: "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=600&auto=format&fit=crop&q=80",
      progress: 75
    },
    {
      id: "2",
      title: "TED Talk: The Secrets of Creative Thinking",
      category: "Listening & Dictation",
      level: "C1 Advanced",
      timeAgo: "Yesterday",
      tab: "listening" as ActiveTab,
      image: "https://images.unsplash.com/photo-1475721027785-f74eccf877e2?w=600&auto=format&fit=crop&q=80",
      progress: 40
    },
    {
      id: "3",
      title: "AI Job Interview Practice Routine",
      category: "Speaking Studio",
      level: "B2 Upper",
      timeAgo: "3 days ago",
      tab: "speaking" as ActiveTab,
      image: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=600&auto=format&fit=crop&q=80",
      progress: 90
    }
  ];

  return (
    <div className="p-6 md:p-8 space-y-8 max-w-7xl mx-auto">
      {/* Welcome Hero Banner */}
      <div className="relative rounded-3xl bg-gradient-to-r from-indigo-600 via-indigo-700 to-purple-800 text-white p-8 overflow-hidden shadow-xl shadow-indigo-100">
        <div className="absolute right-0 top-0 bottom-0 w-1/2 opacity-15 pointer-events-none bg-[radial-gradient(circle_at_top_right,_var(--tw-gradient-stops))] from-white via-indigo-300 to-transparent"></div>
        
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur-md text-xs font-semibold text-indigo-100 mb-4 border border-white/10">
            <Sparkles className="w-3.5 h-3.5 text-amber-300" /> Powered by Gemini 3.6 AI Engine
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-2 leading-tight">
            Good morning, Sarah! 👋
          </h1>
          <p className="text-indigo-100 text-sm sm:text-base mb-6 leading-relaxed">
            You're on a <strong className="text-amber-300">14-day streak</strong>. Today's focus is mastering B2 Business English idioms and refining past conditional grammar.
          </p>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={openFlashcards}
              className="px-5 py-2.5 bg-amber-400 hover:bg-amber-300 text-slate-900 font-bold text-xs rounded-xl shadow-md flex items-center gap-2 transition-all cursor-pointer active:scale-95"
            >
              <Zap className="w-4 h-4 fill-slate-900" /> Start Review (24 Cards)
            </button>
            <button
              onClick={() => setActiveTab("speaking")}
              className="px-5 py-2.5 bg-white/15 hover:bg-white/25 text-white font-semibold text-xs rounded-xl backdrop-blur-md border border-white/20 flex items-center gap-2 transition-all cursor-pointer"
            >
              <Mic className="w-4 h-4" /> Speaking Warmup
            </button>
          </div>
        </div>
      </div>

      {/* Grid Stats & Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Daily Streak Card */}
        <div className="p-6 bg-white rounded-3xl border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 rounded-2xl bg-amber-50 border border-amber-200/60 flex items-center justify-center text-amber-600">
              <Flame className="w-6 h-6 fill-amber-500 text-amber-500 animate-pulse-slow" />
            </div>
            <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full">
              Top 5% Learner
            </span>
          </div>
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
            Current Streak
          </p>
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-3xl font-extrabold text-slate-900">14 Days</span>
            <span className="text-xs text-slate-500">Target: 30 Days</span>
          </div>
          <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
            <div className="bg-amber-500 h-full rounded-full" style={{ width: "46%" }}></div>
          </div>
        </div>

        {/* Spaced Repetition Card */}
        <div className="p-6 bg-white rounded-3xl border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-200/60 flex items-center justify-center text-indigo-600">
                <Zap className="w-6 h-6 fill-indigo-600" />
              </div>
              <span className="text-xs font-bold text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded-full">
                Ready Now
              </span>
            </div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Memory Review Queue
            </p>
            <div className="flex items-baseline gap-2 mb-1">
              <span className="text-3xl font-extrabold text-slate-900">24 Items</span>
              <span className="text-xs text-slate-500">18 Vocab • 6 Grammar</span>
            </div>
          </div>
          <button
            onClick={openFlashcards}
            className="w-full mt-4 py-2 px-3 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
          >
            Launch Flashcards <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Level & Mastery Card */}
        <div className="p-6 bg-white rounded-3xl border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 rounded-2xl bg-purple-50 border border-purple-200/60 flex items-center justify-center text-purple-600">
                <Award className="w-6 h-6" />
              </div>
              <span className="text-xs font-bold text-purple-700 bg-purple-50 px-2.5 py-1 rounded-full">
                CEFR B2
              </span>
            </div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Overall Mastery
            </p>
            <div className="flex items-baseline gap-2 mb-1">
              <span className="text-3xl font-extrabold text-slate-900">82%</span>
              <span className="text-xs text-emerald-600 font-bold flex items-center">
                <TrendingUp className="w-3.5 h-3.5 mr-0.5" /> +4.2% this week
              </span>
            </div>
          </div>
          <button
            onClick={() => setActiveTab("analytics")}
            className="w-full mt-4 py-2 px-3 bg-purple-50 hover:bg-purple-100 text-purple-700 rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
          >
            View Skill Radar <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Weekly Progress Breakdown */}
      <div className="p-6 md:p-8 bg-white rounded-3xl border border-slate-200/80 shadow-xs">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-base font-bold text-slate-900">Weekly Learning Breakdown</h3>
            <p className="text-xs text-slate-500">7 hours 30 minutes total practice time this week</p>
          </div>
          <span className="text-xs font-bold text-slate-500 bg-slate-100 px-3 py-1 rounded-full">
            This Week
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100">
            <div className="flex items-center justify-between text-xs font-bold text-slate-700 mb-2">
              <span className="flex items-center gap-1.5"><BookOpen className="w-4 h-4 text-indigo-600" /> Reading</span>
              <span>3h 00m</span>
            </div>
            <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
              <div className="bg-indigo-600 h-full rounded-full" style={{ width: "80%" }}></div>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100">
            <div className="flex items-center justify-between text-xs font-bold text-slate-700 mb-2">
              <span className="flex items-center gap-1.5"><Headphones className="w-4 h-4 text-purple-600" /> Listening</span>
              <span>2h 15m</span>
            </div>
            <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
              <div className="bg-purple-600 h-full rounded-full" style={{ width: "60%" }}></div>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100">
            <div className="flex items-center justify-between text-xs font-bold text-slate-700 mb-2">
              <span className="flex items-center gap-1.5"><PenTool className="w-4 h-4 text-blue-600" /> Writing</span>
              <span>1h 30m</span>
            </div>
            <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
              <div className="bg-blue-600 h-full rounded-full" style={{ width: "40%" }}></div>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100">
            <div className="flex items-center justify-between text-xs font-bold text-slate-700 mb-2">
              <span className="flex items-center gap-1.5"><Mic className="w-4 h-4 text-emerald-600" /> Speaking</span>
              <span>0h 45m</span>
            </div>
            <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
              <div className="bg-emerald-600 h-full rounded-full" style={{ width: "25%" }}></div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Materials */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-bold text-slate-900">Recent Materials & Saved Sessions</h3>
          <button
            onClick={() => setActiveTab("notebook")}
            className="text-xs font-bold text-indigo-600 hover:text-indigo-700 flex items-center gap-1 cursor-pointer"
          >
            View All Materials <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {recentMaterials.map((mat) => (
            <div
              key={mat.id}
              onClick={() => setActiveTab(mat.tab)}
              className="bg-white rounded-3xl border border-slate-200/80 overflow-hidden shadow-xs hover:shadow-lg transition-all duration-200 group cursor-pointer flex flex-col justify-between"
            >
              <div>
                <div className="relative h-40 overflow-hidden">
                  <img
                    src={mat.image}
                    alt={mat.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-slate-900/80 via-transparent to-transparent"></div>
                  <div className="absolute top-3 left-3 flex items-center gap-2">
                    <span className="px-2.5 py-1 rounded-full bg-white/90 backdrop-blur-md text-[11px] font-bold text-slate-800 shadow-xs">
                      {mat.category}
                    </span>
                  </div>
                  <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between text-white text-xs">
                    <span className="font-semibold">{mat.level}</span>
                    <span className="text-slate-300 text-[11px]">{mat.timeAgo}</span>
                  </div>
                </div>

                <div className="p-5">
                  <h4 className="font-bold text-sm text-slate-900 group-hover:text-indigo-600 transition-colors line-clamp-2 mb-3">
                    {mat.title}
                  </h4>
                  <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                    <div
                      className="bg-indigo-600 h-full rounded-full"
                      style={{ width: `${mat.progress}%` }}
                    ></div>
                  </div>
                </div>
              </div>

              <div className="px-5 pb-5 pt-1 flex items-center justify-between text-xs text-indigo-600 font-bold border-t border-slate-50">
                <span>Continue Learning</span>
                <PlayCircle className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
