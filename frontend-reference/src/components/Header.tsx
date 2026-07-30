import React from "react";
import { Search, Flame, Trophy, Bell, Sparkles, Command } from "lucide-react";
import { ActiveTab } from "../types";

interface HeaderProps {
  activeTab: ActiveTab;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  openFlashcards: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  searchQuery,
  setSearchQuery,
  openFlashcards,
}) => {
  const getTabTitle = () => {
    switch (activeTab) {
      case "dashboard":
        return "Learning Dashboard";
      case "notebook":
        return "Knowledge Space";
      case "reading":
        return "Reading & Vocabulary Studio";
      case "listening":
        return "Listening & Dictation Hub";
      case "speaking":
        return "AI Speaking Practice";
      case "writing":
        return "Writing & Correction Lab";
      case "analytics":
        return "Adaptive Analytics";
      default:
        return "Lumina Learning";
    }
  };

  return (
    <header className="h-16 bg-white/90 backdrop-blur-md border-b border-slate-200/80 px-6 flex items-center justify-between sticky top-0 z-10 shadow-xs">
      {/* Title / Search */}
      <div className="flex items-center gap-6 flex-1 max-w-xl">
        <h2 className="text-lg font-bold text-slate-900 tracking-tight shrink-0 hidden md:block">
          {getTabTitle()}
        </h2>

        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search idioms, grammar, stories, or movie quotes..."
            className="w-full pl-9 pr-12 py-1.5 text-xs bg-slate-100/80 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-800 placeholder-slate-400 transition-all"
          />
          <div className="absolute right-2.5 top-1/2 -translate-y-1/2 hidden sm:flex items-center gap-0.5 text-[10px] text-slate-400 font-mono bg-white px-1.5 py-0.5 rounded border border-slate-200">
            <Command className="w-2.5 h-2.5" /> K
          </div>
        </div>
      </div>

      {/* Gamification & User Stats */}
      <div className="flex items-center gap-3">
        {/* Streak Button */}
        <button
          onClick={openFlashcards}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-50 border border-amber-200/80 text-amber-800 hover:bg-amber-100 transition-all cursor-pointer group"
          title="Daily Streak - Click to Review"
        >
          <Flame className="w-4 h-4 text-amber-500 fill-amber-500 group-hover:scale-110 transition-transform" />
          <span className="text-xs font-bold">14 Days</span>
        </button>

        {/* XP Level */}
        <div className="hidden lg:flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-50 border border-indigo-200/80 text-indigo-900">
          <Trophy className="w-4 h-4 text-indigo-600" />
          <span className="text-xs font-bold">1,240 XP</span>
          <span className="text-[10px] bg-indigo-200/60 text-indigo-800 font-bold px-1.5 py-0.2 rounded-md">
            Level 12
          </span>
        </div>

        {/* AI Model Status */}
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">
          <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
          <span className="hidden sm:inline">Gemini 3.6 Active</span>
        </div>

        {/* Notifications */}
        <button className="relative p-2 rounded-xl text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors">
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-indigo-600 rounded-full"></span>
        </button>
      </div>
    </header>
  );
};
