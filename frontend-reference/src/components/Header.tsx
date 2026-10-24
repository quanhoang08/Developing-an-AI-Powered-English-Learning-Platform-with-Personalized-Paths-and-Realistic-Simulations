import React from "react";
import { Flame, Trophy, Menu, Snowflake } from "lucide-react";
import { ActiveTab } from "../types";
import { useLearningStats } from "../stats";
import { AuthPanel } from "./AuthPanel";
import { HeaderSearch } from "./HeaderSearch";
import { NotificationBell } from "./NotificationBell";

interface HeaderProps {
  activeTab: ActiveTab;
  openFlashcards: () => void;
  onAuthChanged: () => void;
  onOpenMenu: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  openFlashcards,
  onAuthChanged,
  onOpenMenu,
}) => {
  const { stats } = useLearningStats();
  // Đổi tiêu đề header theo tab đang xem.
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
      case "games":
        return "Games & Rewards";
      case "community":
        return "Friends, Classes & Guild";
      case "exam":
        return "IELTS & TOEIC Prep";
      case "tools":
        return "Vocabulary & Grammar Tools";
      default:
        return "Lumina Learning";
    }
  };

  return (
    <header className="h-20 bg-paper/80 backdrop-blur-xl border-b border-slate-200/60 px-4 md:px-8 flex items-center justify-between gap-3 sticky top-0 z-30">
      {/* Title / Search */}
      <div className="flex items-center gap-3 md:gap-6 flex-1 min-w-0 max-w-2xl">
        <button
          onClick={onOpenMenu}
          className="md:hidden shrink-0 p-2 -ml-2 rounded-full text-slate-600 hover:bg-slate-900/5"
          aria-label="Open navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>
        <h2 className="font-display text-2xl font-bold text-slate-900 shrink-0 hidden md:block">
          {getTabTitle()}
        </h2>

        <HeaderSearch />
      </div>

      {/* Gamification & User Stats */}
      <div className="flex items-center gap-2.5">
        {/* Streak + XP là số liệu thật từ GET /api/streaks (bảng streaks), 0 khi chưa đăng nhập.
            Ngọn lửa chỉ sáng khi hôm nay đã học, mờ đi nếu streak đang chờ được giữ. */}
        <button
          onClick={openFlashcards}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-full active:scale-95 transition-all cursor-pointer group ${
            stats.todayActive
              ? "bg-purple-50 text-purple-800 hover:bg-purple-100"
              : "bg-paper-deep text-slate-600 hover:bg-slate-200/70"
          }`}
          title={stats.todayActive ? "Streak kept for today" : "Study today to keep your streak - click to review"}
        >
          <Flame
            className={`w-5 h-5 group-hover:animate-wiggle ${
              stats.todayActive ? "text-purple-500 fill-purple-500" : "text-slate-400"
            }`}
          />
          <span className="num text-sm font-bold">
            {stats.currentStreak} {stats.currentStreak === 1 ? "day" : "days"}
          </span>
        </button>

        {/* Freeze: tặng mỗi 7 ngày liên tiếp (tối đa 2), tự lấp ngày bỏ lỡ. Streak vừa đứt thì báo có thể khôi phục. */}
        <div
          className={`hidden sm:flex items-center gap-1.5 px-3.5 py-2.5 rounded-full ${
            stats.restorableStreak > 0 ? "bg-amber-50 text-amber-800" : "bg-sky-50 text-sky-800"
          }`}
          title={
            stats.restorableStreak > 0
              ? `Your ${stats.restorableStreak}-day streak broke - pass a 10-question quiz today to restore it`
              : `${stats.freezesAvailable} streak freeze(s): each covers a missed day`
          }
        >
          <Snowflake className="w-5 h-5" />
          <span className="num text-sm font-bold">{stats.restorableStreak > 0 ? "Restore" : stats.freezesAvailable}</span>
        </div>

        {/* XP Level */}
        <div
          className="hidden lg:flex items-center gap-2 px-4 py-2.5 rounded-full bg-indigo-50 text-indigo-900"
          title={`${stats.xpIntoLevel} / ${stats.xpForNextLevel} XP to level ${stats.level + 1}`}
        >
          <Trophy className="w-5 h-5 text-indigo-600" />
          <span className="num text-sm font-bold">{stats.totalXp.toLocaleString("en-US")} XP</span>
          <span className="tag bg-indigo-600 text-white !text-xs !px-2 !py-0.5">Lv {stats.level}</span>
        </div>

        <NotificationBell openFlashcards={openFlashcards} />

        {/* Kết nối phiên đăng nhập của giao diện với FastAPI backend. */}
        <AuthPanel onAuthChanged={onAuthChanged} />
      </div>
    </header>
  );
};
