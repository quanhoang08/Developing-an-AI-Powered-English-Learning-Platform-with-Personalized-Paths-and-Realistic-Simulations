import React from "react";
import { ActiveTab } from "../types";
import {
  LayoutDashboard,
  BookOpen,
  Headphones,
  Mic,
  PenTool,
  FolderKanban,
  BarChart3,
  Sparkles,
  Zap,
  GraduationCap,
  Flame
} from "lucide-react";

interface NavItem {
  id: ActiveTab;
  label: string;
  icon: any;
  badge?: string;
}

interface SidebarProps {
  activeTab: ActiveTab;
  setActiveTab: (tab: ActiveTab) => void;
  openFlashcards: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  openFlashcards,
}) => {
  const navItems: NavItem[] = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "notebook", label: "Knowledge Space", icon: FolderKanban, badge: "AI" },
    { id: "reading", label: "Reading & Vocab", icon: BookOpen, badge: "B2" },
    { id: "listening", label: "Listening & Movies", icon: Headphones },
    { id: "speaking", label: "Speaking Studio", icon: Mic, badge: "Live" },
    { id: "writing", label: "Writing Lab", icon: PenTool },
    { id: "analytics", label: "Adaptive Progress", icon: BarChart3 },
  ];

  return (
    <aside className="w-64 bg-white border-r border-slate-200/80 flex flex-col h-screen sticky top-0 shrink-0 z-20 select-none shadow-xs">
      {/* Brand Logo Header */}
      <div className="p-5 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-md shadow-indigo-200">
            <GraduationCap className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-bold text-slate-900 text-lg tracking-tight leading-tight flex items-center gap-1.5">
              Lumina <span className="text-xs px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-semibold border border-indigo-200/60">PRO</span>
            </h1>
            <p className="text-xs text-slate-500 font-medium">AI English Master</p>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        <div className="px-3 py-2 text-[11px] font-bold tracking-wider text-slate-400 uppercase">
          Learning Hub
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id as ActiveTab)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 group ${
                isActive
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-200 font-semibold"
                  : "text-slate-600 hover:bg-slate-100/80 hover:text-slate-900"
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon
                  className={`w-4 h-4 transition-transform duration-150 group-hover:scale-110 ${
                    isActive ? "text-white" : "text-slate-500 group-hover:text-indigo-600"
                  }`}
                />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span
                  className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md ${
                    isActive
                      ? "bg-white/20 text-white"
                      : item.badge === "Live"
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-indigo-50 text-indigo-600"
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Daily Review Callout */}
      <div className="p-3">
        <div className="p-3.5 rounded-2xl bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200/60 relative overflow-hidden">
          <div className="flex items-center justify-between mb-2">
            <span className="inline-flex items-center gap-1 text-xs font-bold text-amber-800">
              <Flame className="w-3.5 h-3.5 text-amber-500 fill-amber-500" /> 24 Cards Due
            </span>
            <span className="text-[10px] font-semibold text-amber-700 bg-amber-200/50 px-1.5 py-0.5 rounded-full">
              Spaced Rep.
            </span>
          </div>
          <p className="text-xs text-slate-600 mb-3 leading-snug">
            Reinforce vocabulary & grammar memory before it fades today.
          </p>
          <button
            onClick={openFlashcards}
            className="w-full py-2 px-3 bg-amber-500 hover:bg-amber-600 active:scale-[0.98] text-white rounded-xl text-xs font-semibold shadow-xs flex items-center justify-center gap-1.5 transition-all"
          >
            <Zap className="w-3.5 h-3.5 fill-white" /> Start Quick Review
          </button>
        </div>
      </div>

      {/* User Footer Profile */}
      <div className="p-3 border-t border-slate-100">
        <div className="flex items-center gap-3 p-2 rounded-xl hover:bg-slate-50 cursor-pointer transition-colors">
          <div className="relative">
            <img
              src="https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150&auto=format&fit=crop&q=80"
              alt="Sarah Jenkins"
              className="w-9 h-9 rounded-full object-cover border border-slate-200 shadow-xs"
            />
            <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-emerald-500 border-2 border-white rounded-full"></span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <p className="text-xs font-bold text-slate-900 truncate">Sarah Jenkins</p>
              <span className="text-[10px] text-indigo-600 font-bold bg-indigo-50 px-1 rounded">B2 Upper</span>
            </div>
            <p className="text-[11px] text-slate-500 truncate">sarah.j@example.com</p>
          </div>
        </div>
      </div>
    </aside>
  );
};
