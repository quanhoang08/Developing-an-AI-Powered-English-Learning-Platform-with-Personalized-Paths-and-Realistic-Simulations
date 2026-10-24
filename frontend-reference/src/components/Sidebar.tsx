// Sidebar cố định: điều hướng tab (khóa khi chưa đăng nhập) + widget tài khoản/đăng xuất.
import React, { useState } from "react";
import { motion } from "motion/react";
import { ActiveTab } from "../types";
import { useLearningStats } from "../stats";
import { useWallet } from "./games/shared";
import { TIMER_LOCK_MESSAGE, useTimerLocked } from "../timerLock";
import {
  LayoutDashboard,
  BookOpen,
  Headphones,
  Mic,
  PenTool,
  FolderKanban,
  BarChart3,
  Gamepad2,
  Users,
  GraduationCap,
  Wrench,
  Zap,
  Flame,
  Lock,
  LogIn,
  LogOut,
  User as UserIcon,
  ChevronUp,
  PanelLeftClose,
  PanelLeftOpen
} from "lucide-react";

const COLLAPSE_KEY = "lumina_sidebar_collapsed";
const readCollapsed = () => {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
};

interface NavItem {
  id: ActiveTab;
  label: string;
  icon: any;
  badge?: string;
  // Tiêu đề nhóm hiện phía trên mục này (chỉ ở mục đầu của nhóm).
  group?: string;
}

interface SidebarProps {
  activeTab: ActiveTab;
  setActiveTab: (tab: ActiveTab) => void;
  openFlashcards: () => void;
  isLoggedIn: boolean;
  userEmail: string | null;
  onLogout: () => void;
  // Drawer trên màn hình hẹp (< md); từ md trở lên sidebar luôn hiện cố định.
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  openFlashcards,
  isLoggedIn,
  userEmail,
  onLogout,
  isOpen,
  onClose,
}) => {
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false);
  const [collapsedPref, setCollapsedPref] = useState(readCollapsed);
  // Drawer mobile (isOpen) luôn mở rộng; chỉ sidebar cố định từ md trở lên mới thu gọn được.
  const c = collapsedPref && !isOpen;
  const toggleCollapsed = () =>
    setCollapsedPref((prev) => {
      try {
        localStorage.setItem(COLLAPSE_KEY, prev ? "0" : "1");
      } catch {
        /* không lưu được thì chỉ nhớ trong phiên này */
      }
      return !prev;
    });
  const { stats } = useLearningStats();
  // Avatar/khung đã trang bị trong shop (EconomyCard) hiện ở góc tài khoản.
  const { wallet } = useWallet();
  const equipped = (slot: string) => wallet?.shop.find((i) => i.slot === slot && i.equipped);
  const avatar = equipped("avatar");
  const frame = equipped("frame");
  const timerLocked = useTimerLocked();
  const navItems: NavItem[] = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, group: "Learning hub" },
    { id: "notebook", label: "Knowledge Space", icon: FolderKanban, badge: "AI" },
    { id: "reading", label: "Reading & Vocab", icon: BookOpen, badge: "B2" },
    { id: "listening", label: "Listening & Movies", icon: Headphones },
    { id: "speaking", label: "Speaking Studio", icon: Mic, badge: "Live" },
    { id: "writing", label: "Writing Lab", icon: PenTool },
    { id: "tools", label: "Vocab & Grammar", icon: Wrench, group: "Practice & prep" },
    { id: "exam", label: "IELTS & TOEIC", icon: GraduationCap },
    { id: "games", label: "Games & Rewards", icon: Gamepad2 },
    { id: "analytics", label: "Adaptive Progress", icon: BarChart3, group: "Progress & community" },
    { id: "community", label: "Community", icon: Users },
  ];

  return (
    <>
    {isOpen && <div className="fixed inset-0 z-30 bg-slate-900/40 md:hidden" onClick={onClose} aria-hidden="true" />}
    <aside
      className={`${c ? "w-[4.5rem]" : "w-64"} bg-paper md:bg-paper-deep/60 backdrop-blur-sm flex flex-col h-screen fixed inset-y-0 left-0 md:sticky md:top-0 md:translate-x-0 transition-[transform,width] duration-200 shrink-0 z-40 md:z-20 select-none border-r border-slate-200/70 ${
        isOpen ? "translate-x-0" : "-translate-x-full"
      }`}
    >
      {/* Brand */}
      <div className={c ? "px-3 pt-6 pb-4 flex flex-col items-center gap-3" : "px-5 pt-6 pb-4"}>
        <div className="flex items-center gap-3">
          <div className="relative w-11 h-11 rounded-[14px] bg-indigo-600 flex items-center justify-center shadow-[0_8px_18px_-8px_rgba(37,109,89,0.7)] -rotate-3">
            <svg viewBox="0 0 32 32" className="w-6 h-6" aria-hidden="true">
              <path d="M11 8v13h9" fill="none" stroke="#faf6ee" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="22" cy="10" r="2.6" fill="#f77a55" />
            </svg>
          </div>
          {!c && (
            <div>
              <p className="font-display font-extrabold text-slate-900 text-xl leading-none flex items-center gap-1.5">
                Lumina
                <span className="tag bg-purple-100 text-purple-700 rotate-2">PRO</span>
              </p>
              <p className="text-xs text-slate-500 mt-1">Học tiếng Anh cùng AI</p>
            </div>
          )}
        </div>
        <button
          onClick={toggleCollapsed}
          aria-label={c ? "Expand sidebar" : "Collapse sidebar"}
          title={c ? "Expand sidebar" : "Collapse sidebar"}
          className={`hidden md:flex p-1.5 rounded-lg text-slate-400 hover:bg-slate-900/5 hover:text-slate-700 transition-colors cursor-pointer ${c ? "" : "absolute top-7 right-3"}`}
        >
          {c ? <PanelLeftOpen className="w-5 h-5" /> : <PanelLeftClose className="w-5 h-5" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto overflow-x-hidden" aria-label="Main navigation">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          const isLocked = item.id !== "dashboard" && !isLoggedIn;
          // aria-disabled (không dùng disabled) để tooltip giải thích vẫn hiện khi rê chuột.
          const isBlocked = timerLocked && !isActive;
          return (
            <React.Fragment key={item.id}>
            {item.group && (c ? (
              <div className="mx-3 my-2 border-t border-slate-200/80" aria-hidden="true" />
            ) : (
              <div className="px-3 pt-3 pb-1.5 text-xs font-semibold text-slate-400 italic">{item.group}</div>
            ))}
            <button
              onClick={() => {
                if (!isBlocked) {
                  setActiveTab(item.id as ActiveTab);
                  onClose();
                }
              }}
              title={isBlocked ? TIMER_LOCK_MESSAGE : isLocked ? "Sign in to unlock this feature" : c ? item.label : undefined}
              aria-label={c ? item.label : undefined}
              aria-current={isActive ? "page" : undefined}
              aria-disabled={isBlocked || undefined}
              className={`relative w-full flex items-center ${c ? "justify-center px-0" : "justify-between px-3.5"} py-2 rounded-xl text-sm font-medium transition-colors duration-200 group active:scale-[0.98] ${
                isActive
                  ? "text-white"
                  : isBlocked
                  ? "text-slate-400 opacity-60 cursor-not-allowed"
                  : isLocked
                  ? "text-slate-400 hover:bg-slate-900/5"
                  : "text-slate-600 hover:bg-slate-900/5 hover:text-slate-900"
              }`}
            >
              {isActive && (
                <motion.span
                  layoutId="sidebar-active-pill"
                  className="absolute inset-0 rounded-xl bg-indigo-700 shadow-[0_10px_20px_-10px_rgba(31,87,73,0.8)]"
                  transition={{ type: "spring", stiffness: 420, damping: 34 }}
                />
              )}
              <div className="relative flex items-center gap-3">
                <Icon
                  className={`w-[18px] h-[18px] transition-transform duration-200 group-hover:-rotate-6 group-hover:scale-110 ${
                    isActive ? "text-white" : isLocked ? "text-slate-400" : "text-slate-500 group-hover:text-indigo-600"
                  }`}
                />
                {!c && <span>{item.label}</span>}
              </div>
              <span className={c ? "hidden" : "relative"}>
                {isLocked ? (
                  <Lock className="w-3.5 h-3.5 text-slate-400" />
                ) : (
                  item.badge && (
                    <span
                      className={`tag ${
                        isActive
                          ? "bg-white/20 text-white"
                          : item.badge === "Live"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-indigo-100 text-indigo-700"
                      }`}
                    >
                      {item.badge}
                    </span>
                  )
                )}
              </span>
            </button>
            </React.Fragment>
          );
        })}
      </nav>

      {/* Daily Review — số thẻ đến hạn thật (GET /api/vocab/due qua store stats). Nghiêng nhẹ như tờ giấy nhớ. */}
      <div className="px-3 pb-3">
        {c ? (
          <button
            onClick={openFlashcards}
            title={`${stats.dueCards} ${stats.dueCards === 1 ? "card" : "cards"} due - start quick review`}
            aria-label="Start quick review"
            className="relative w-full flex items-center justify-center py-3 rounded-2xl bg-[#fff0c2] hover:bg-[#ffe9a8] transition-colors cursor-pointer"
          >
            <Flame className="w-5 h-5 text-purple-500 fill-purple-500" />
            {stats.dueCards > 0 && (
              <span className="num absolute -top-1.5 -right-1 min-w-5 h-5 px-1 rounded-full bg-slate-900 text-amber-50 text-[10px] font-bold flex items-center justify-center">
                {stats.dueCards > 99 ? "99+" : stats.dueCards}
              </span>
            )}
          </button>
        ) : (
        <div className="flex items-center gap-2 p-2.5 rounded-2xl bg-[#fff0c2] shadow-[0_8px_16px_-12px_rgba(140,90,10,0.55)]">
          <span className="flex-1 inline-flex items-center gap-1.5 text-sm font-bold text-amber-900 font-display">
            <Flame className="w-4 h-4 text-purple-500 fill-purple-500" /> {stats.dueCards} {stats.dueCards === 1 ? "card" : "cards"} due
          </span>
          <button
            onClick={openFlashcards}
            className="py-1.5 px-3 bg-slate-900 hover:bg-slate-800 active:scale-[0.97] text-amber-50 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all"
          >
            <Zap className="w-3.5 h-3.5 fill-amber-300 text-amber-300" /> Review
          </button>
        </div>
        )}
      </div>

      {/* User Footer Profile / Auth — chỉ nguồn thật (App.tsx), không còn dữ liệu demo. */}
      <div className="p-3 border-t border-slate-200/70 relative">
        {isAccountMenuOpen && isLoggedIn && (
          <>
            {/* Lớp phủ để bắt click-outside đóng menu, không cần thư viện ngoài. */}
            <div className="fixed inset-0 z-10" onClick={() => setIsAccountMenuOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: 6, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              className="absolute bottom-full left-3 right-3 mb-2 z-20 bg-[#fffdf8] rounded-xl shadow-[0_18px_36px_-16px_rgba(95,70,30,0.4)] ring-1 ring-slate-900/10 overflow-hidden"
            >
              <button
                onClick={() => {
                  setIsAccountMenuOpen(false);
                  onLogout();
                }}
                className="w-full flex items-center gap-2 px-3 py-2.5 text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
              >
                <LogOut className="w-4 h-4" /> Log out
              </button>
            </motion.div>
          </>
        )}

        {isLoggedIn ? (
          <button
            onClick={() => setIsAccountMenuOpen((open) => !open)}
            title={c ? userEmail ?? undefined : undefined}
            className={`w-full flex items-center ${c ? "justify-center" : "gap-3"} p-2 rounded-xl hover:bg-slate-900/5 transition-colors`}
          >
            <div className="relative shrink-0">
              <div
                className={`w-9 h-9 rounded-[12px] bg-purple-100 flex items-center justify-center text-purple-700 ${
                  frame ? (frame.id === "frame_gold" ? "ring-2 ring-amber-400" : "ring-2 ring-fuchsia-500") : ""
                }`}
                title={frame?.name}
              >
                {avatar ? <span className="text-lg" aria-label={avatar.name}>{avatar.emoji}</span> : <UserIcon className="w-4 h-4" />}
              </div>
              <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-emerald-500 border-2 border-paper rounded-full"></span>
            </div>
            {!c && (
              <>
                <div className="flex-1 min-w-0 text-left">
                  <p className="text-xs font-bold text-slate-900 truncate">{userEmail}</p>
                  <p className="text-[11px] text-slate-500">Connected account</p>
                </div>
                <ChevronUp className={`w-4 h-4 text-slate-400 transition-transform shrink-0 ${isAccountMenuOpen ? "" : "rotate-180"}`} />
              </>
            )}
          </button>
        ) : (
          <button
            onClick={() => window.dispatchEvent(new Event("lumina-open-auth"))}
            title={c ? "Sign in" : undefined}
            className={`w-full flex items-center ${c ? "justify-center" : "gap-3"} p-2 rounded-xl hover:bg-slate-900/5 transition-colors`}
          >
            <div className="w-9 h-9 rounded-[12px] bg-slate-200/70 flex items-center justify-center text-slate-500 shrink-0">
              <LogIn className="w-4 h-4" />
            </div>
            {!c && (
              <div className="flex-1 min-w-0 text-left">
                <p className="text-xs font-bold text-slate-900">Sign in</p>
                <p className="text-[11px] text-slate-500">Connect your account</p>
              </div>
            )}
          </button>
        )}
      </div>
    </aside>
    </>
  );
};
