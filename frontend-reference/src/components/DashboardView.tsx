// Trang chủ, xem được cả khi chưa đăng nhập. Dữ liệu thật: greeting/tên user (App.tsx truyền
// userEmail xuống) và streak/XP (useLearningStats -> GET /api/streaks). Số liệu mastery,
// weekly breakdown, recent materials và "24 cards" vẫn là demo cứng vì Adaptive Progress
// backend chưa implement.
import React from "react";
import { motion } from "motion/react";
import { ActiveTab } from "../types";
import { CatMascot } from "./CatMascot";
import { useLearningStats } from "../stats";
import {
  Flame,
  Zap,
  BookOpen,
  Headphones,
  Mic,
  PenTool,
  ArrowUpRight,
  TrendingUp,
  ChevronRight,
  PlayCircle
} from "lucide-react";

interface DashboardViewProps {
  setActiveTab: (tab: ActiveTab) => void;
  openFlashcards: () => void;
  userEmail: string | null;
}

// Giờ thực tế quyết định lời chào — không còn cố định "Good morning" như trước.
function getTimeBasedGreeting(): string {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return "Good morning";
  if (hour >= 12 && hour < 18) return "Good afternoon";
  return "Good night";
}

// Các khối xuất hiện lần lượt (stagger) thay vì bật ra cùng lúc.
const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};
const item = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] as const } },
};

const STREAK_TARGET = 30;
const MASTERY_PERCENT = 82;

// Ngày local dạng YYYY-MM-DD, khớp định dạng recent_active_dates của backend.
function toIsoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

// 30 ngày gần nhất, ngày cuối là hôm nay.
function lastDays(count: number): string[] {
  const today = new Date();
  return Array.from({ length: count }, (_, index) => {
    const day = new Date(today);
    day.setDate(today.getDate() - (count - 1 - index));
    return toIsoDate(day);
  });
}
const RING_RADIUS = 34;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

export const DashboardView: React.FC<DashboardViewProps> = ({
  setActiveTab,
  openFlashcards,
  userEmail,
}) => {
  const greeting = getTimeBasedGreeting();
  const { stats } = useLearningStats();
  const streakDays = lastDays(STREAK_TARGET);
  const activeDaySet = new Set(stats.recentActiveDates);
  const displayName = userEmail ? userEmail.split("@")[0] : null;
  // Danh sách demo cứng — chưa gọi listDocuments()/reading history thật từ backend.
  const recentMaterials = [
    {
      id: "1",
      title: "Business English: Negotiation Tactics",
      category: "Reading & Vocab",
      level: "B2 Upper",
      timeAgo: "2 hours ago",
      tab: "reading" as ActiveTab,
      image: "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=900&auto=format&fit=crop&q=80",
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
  const [featured, ...others] = recentMaterials;

  // Tỷ lệ thanh tổng: 3h00 / 2h15 / 1h30 / 0h45 trên tổng 7h30 (450 phút).
  const weekly = [
    { label: "Reading", time: "3h 00m", share: 40, icon: BookOpen, bar: "bg-indigo-600", text: "text-indigo-700" },
    { label: "Listening", time: "2h 15m", share: 30, icon: Headphones, bar: "bg-purple-500", text: "text-purple-700" },
    { label: "Writing", time: "1h 30m", share: 20, icon: PenTool, bar: "bg-amber-400", text: "text-amber-700" },
    { label: "Speaking", time: "0h 45m", share: 10, icon: Mic, bar: "bg-blue-400", text: "text-blue-700" },
  ];

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="p-6 md:p-10 space-y-10 max-w-7xl mx-auto"
    >
      {/* Welcome hero — bất đối xứng, mascot nhô ra khỏi khung tạo chiều sâu */}
      <motion.section
        variants={item}
        className="relative rounded-[2rem] bg-indigo-900 text-white overflow-hidden shadow-[0_30px_60px_-30px_rgba(11,33,27,0.9)]"
      >
        <div className="absolute -top-24 -right-10 w-[28rem] h-[28rem] rounded-full bg-purple-500/25 blur-3xl pointer-events-none" aria-hidden="true" />
        <div className="absolute -bottom-32 left-1/3 w-[26rem] h-[26rem] rounded-full bg-indigo-400/20 blur-3xl pointer-events-none" aria-hidden="true" />
        <div
          className="absolute inset-0 opacity-[0.08] pointer-events-none"
          style={{ backgroundImage: "radial-gradient(#fff 1px, transparent 1px)", backgroundSize: "22px 22px" }}
          aria-hidden="true"
        />

        <div className="relative z-10 grid md:grid-cols-[1.4fr_1fr] items-end">
          <div className="p-8 md:p-12 md:pr-0">
            <p className="text-sm text-indigo-200 mb-4 flex items-center gap-2">
              <span className="w-6 h-px bg-indigo-300/60" /> Your AI tutor is ready
            </p>
            <h1 className="font-display text-4xl sm:text-5xl md:text-6xl font-extrabold leading-[0.98] tracking-tight mb-5">
              {greeting}
              {displayName && (
                <>
                  ,<br />
                  <span className="italic font-semibold text-purple-300">{displayName}</span>
                </>
              )}
            </h1>
            <p className="text-indigo-100/90 text-base mb-8 leading-relaxed max-w-md">
              {stats.currentStreak > 0 ? (
                <>
                  You're on a <strong className="text-amber-300 font-semibold">{stats.currentStreak}-day streak</strong>
                  {stats.todayActive ? ". Nice work keeping it alive today." : ". Study a little today to keep it going."}
                </>
              ) : (
                <>Start your streak today: one review, one reading or one dictation is enough.</>
              )}
            </p>

            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={openFlashcards}
                className="px-5 py-3 bg-amber-300 hover:bg-amber-200 text-slate-900 font-bold text-sm rounded-2xl shadow-[0_12px_24px_-10px_rgba(252,211,77,0.6)] flex items-center gap-2 transition-all cursor-pointer hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.97]"
              >
                <Zap className="w-4 h-4 fill-slate-900" /> Start review · 24 cards
              </button>
              <button
                onClick={() => setActiveTab("speaking")}
                className="px-3 py-3 text-white/90 hover:text-white font-semibold text-sm flex items-center gap-2 transition-colors cursor-pointer group"
              >
                <Mic className="w-4 h-4" /> Speaking warm-up
                <ChevronRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
              </button>
            </div>
          </div>

          <div className="hidden md:flex justify-center self-end h-full pr-6">
            <CatMascot mouthOpen={0} mood="idle" className="h-72 w-auto translate-y-6 drop-shadow-[0_24px_24px_rgba(0,0,0,0.35)]" />
          </div>
        </div>
      </motion.section>

      {/* Stats — lưới bất đối xứng 5/4/3 thay vì 3 thẻ bằng nhau */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Streak: lưới 30 chấm, 14 chấm đã sáng */}
        <motion.div variants={item} className="surface surface-lift lg:col-span-5 p-6">
          <div className="flex items-start justify-between mb-5">
            <div>
              <p className="text-sm text-slate-500 italic mb-1">Current streak</p>
              <div className="flex items-baseline gap-2">
                <span className="num text-5xl font-extrabold text-slate-900">{stats.currentStreak}</span>
                <span className="text-sm text-slate-500">{stats.currentStreak === 1 ? "day" : "days"} · goal {STREAK_TARGET}</span>
              </div>
            </div>
            <Flame
              className={`w-9 h-9 ${
                stats.todayActive ? "fill-purple-500 text-purple-500 animate-wiggle" : "text-slate-300"
              }`}
            />
          </div>
          <div
            className="grid grid-cols-10 gap-1.5"
            role="img"
            aria-label={`Studied on ${streakDays.filter((day) => activeDaySet.has(day)).length} of the last ${STREAK_TARGET} days`}
          >
            {streakDays.map((day, index) => {
              const isDone = activeDaySet.has(day);
              const isToday = index === streakDays.length - 1;
              return (
                <span
                  key={day}
                  title={day}
                  className={`aspect-square rounded-md ${
                    isDone && isToday
                      ? "bg-purple-500 ring-4 ring-purple-200 animate-pulse-slow"
                      : isDone
                      ? "bg-purple-300"
                      : isToday
                      ? "bg-slate-200/70 ring-2 ring-purple-300"
                      : "bg-slate-200/70"
                  }`}
                />
              );
            })}
          </div>
          <p className="text-xs text-slate-500 mt-4">
            Longest streak: <span className="num font-bold text-slate-700">{stats.longestStreak}</span> days
            <span className="mx-2">·</span>
            <span className="num font-bold text-slate-700">{stats.totalXp.toLocaleString("en-US")}</span> XP, level {stats.level}
          </p>
        </motion.div>

        {/* Spaced repetition: nền màu đặc, không viền */}
        <motion.div
          variants={item}
          className="lg:col-span-4 rounded-3xl bg-indigo-100 p-6 flex flex-col justify-between relative overflow-hidden"
        >
          <div className="absolute -right-6 -bottom-6 w-32 h-32 rounded-full bg-indigo-200/70" aria-hidden="true" />
          <div className="relative">
            <p className="text-sm text-indigo-800/80 italic mb-1">Memory review queue</p>
            <div className="flex items-baseline gap-2">
              <span className="num text-5xl font-extrabold text-indigo-950">24</span>
              <span className="text-sm text-indigo-900/70">items ready now</span>
            </div>
            <p className="text-xs text-indigo-900/70 mt-2">18 vocab · 6 grammar</p>
          </div>
          <button
            onClick={openFlashcards}
            className="relative mt-6 py-2.5 px-4 bg-indigo-700 hover:bg-indigo-800 text-white rounded-xl text-sm font-semibold flex items-center justify-between transition-all cursor-pointer active:scale-[0.98] group"
          >
            Launch flashcards
            <ChevronRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
          </button>
        </motion.div>

        {/* Mastery: vòng tiến độ */}
        <motion.div variants={item} className="surface surface-lift lg:col-span-3 p-6 flex flex-col justify-between">
          <div className="flex items-center gap-4">
            <div className="relative w-20 h-20 shrink-0">
              <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90" aria-hidden="true">
                <circle cx="40" cy="40" r={RING_RADIUS} fill="none" strokeWidth="8" className="stroke-slate-200/80" />
                <motion.circle
                  cx="40"
                  cy="40"
                  r={RING_RADIUS}
                  fill="none"
                  strokeWidth="8"
                  strokeLinecap="round"
                  className="stroke-purple-500"
                  strokeDasharray={RING_CIRCUMFERENCE}
                  initial={{ strokeDashoffset: RING_CIRCUMFERENCE }}
                  animate={{ strokeDashoffset: RING_CIRCUMFERENCE * (1 - MASTERY_PERCENT / 100) }}
                  transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1], delay: 0.4 }}
                />
              </svg>
              <span className="num absolute inset-0 flex items-center justify-center text-xl font-extrabold text-slate-900">
                {MASTERY_PERCENT}%
              </span>
            </div>
            <div>
              <p className="text-sm text-slate-500 italic">Overall mastery</p>
              <p className="tag bg-purple-100 text-purple-700 mt-1">CEFR B2</p>
              <p className="text-xs text-emerald-600 font-semibold flex items-center mt-1.5">
                <TrendingUp className="w-3.5 h-3.5 mr-1" /> +4.2% this week
              </p>
            </div>
          </div>
          <button
            onClick={() => setActiveTab("analytics")}
            className="mt-5 text-sm font-semibold text-purple-700 hover:text-purple-800 flex items-center gap-1 cursor-pointer group self-start"
          >
            View skill radar
            <ArrowUpRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </button>
        </motion.div>
      </div>

      {/* Weekly breakdown: một thanh chia tỷ lệ + chú giải, thay cho 4 ô bằng nhau */}
      <motion.section variants={item} className="surface p-6 md:p-8">
        <div className="flex flex-wrap items-end justify-between gap-2 mb-6">
          <div>
            <h3 className="font-display text-2xl font-bold text-slate-900">This week, in minutes</h3>
            <p className="text-sm text-slate-500">7 hours 30 minutes of practice across four skills</p>
          </div>
          <span className="tag bg-slate-100 text-slate-600">This week</span>
        </div>

        <div className="flex h-4 rounded-full overflow-hidden gap-1 mb-6" role="img" aria-label="Weekly practice time split by skill">
          {weekly.map((row, index) => (
            <motion.div
              key={row.label}
              className={`${row.bar} first:rounded-l-full last:rounded-r-full`}
              initial={{ width: 0 }}
              animate={{ width: `${row.share}%` }}
              transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.3 + index * 0.1 }}
            />
          ))}
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-4">
          {weekly.map((row) => {
            const Icon = row.icon;
            return (
              <div key={row.label} className="flex items-center gap-3">
                <span className={`w-9 h-9 rounded-[12px] flex items-center justify-center bg-slate-100 ${row.text}`}>
                  <Icon className="w-4 h-4" />
                </span>
                <div>
                  <p className="text-xs text-slate-500">{row.label}</p>
                  <p className="num text-base font-bold text-slate-900">{row.time}</p>
                </div>
              </div>
            );
          })}
        </div>
      </motion.section>

      {/* Recent materials: một thẻ lớn nổi bật + danh sách ngang */}
      <motion.section variants={item}>
        <div className="flex items-end justify-between mb-5">
          <h3 className="font-display text-2xl font-bold text-slate-900">Pick up where you left off</h3>
          <button
            onClick={() => setActiveTab("notebook")}
            className="text-sm font-semibold text-indigo-700 hover:text-indigo-800 flex items-center gap-1 cursor-pointer group"
          >
            All materials
            <ArrowUpRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
          <button
            onClick={() => setActiveTab(featured.tab)}
            className="lg:col-span-3 lg:row-span-2 relative rounded-[1.75rem] overflow-hidden text-left group cursor-pointer min-h-[22rem] shadow-[0_24px_40px_-24px_rgba(32,29,24,0.7)]"
          >
            <img
              src={featured.image}
              alt={featured.title}
              className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-slate-950/20 to-transparent" />
            <span className="absolute top-4 left-4 tag bg-paper text-slate-800">{featured.category}</span>
            <div className="absolute bottom-0 left-0 right-0 p-6 text-white">
              <p className="text-xs text-white/70 mb-2">{featured.level} · {featured.timeAgo}</p>
              <h4 className="font-display text-3xl font-bold leading-tight mb-4 max-w-md">{featured.title}</h4>
              <div className="flex items-center gap-3">
                <div className="flex-1 h-1.5 rounded-full bg-white/25 overflow-hidden">
                  <div className="h-full rounded-full bg-amber-300" style={{ width: `${featured.progress}%` }} />
                </div>
                <span className="num text-xs font-bold">{featured.progress}%</span>
                <span className="flex items-center gap-1 text-sm font-semibold">
                  Continue <PlayCircle className="w-5 h-5 transition-transform group-hover:translate-x-1" />
                </span>
              </div>
            </div>
          </button>

          {others.map((mat) => (
            <button
              key={mat.id}
              onClick={() => setActiveTab(mat.tab)}
              className="surface surface-lift lg:col-span-2 flex items-stretch gap-4 p-3 text-left cursor-pointer group"
            >
              <img
                src={mat.image}
                alt={mat.title}
                className="w-28 sm:w-32 rounded-2xl object-cover shrink-0 transition-transform duration-500 group-hover:scale-[1.03]"
              />
              <div className="flex-1 min-w-0 py-1 pr-2 flex flex-col justify-between">
                <div>
                  <span className="tag bg-indigo-100 text-indigo-700 mb-2">{mat.category}</span>
                  <h4 className="font-display font-bold text-base leading-snug text-slate-900 line-clamp-2 group-hover:text-indigo-700 transition-colors">
                    {mat.title}
                  </h4>
                </div>
                <div>
                  <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1.5">
                    <span>{mat.level} · {mat.timeAgo}</span>
                    <span className="num font-bold text-slate-700">{mat.progress}%</span>
                  </div>
                  <div className="w-full bg-slate-200/70 h-1.5 rounded-full overflow-hidden">
                    <div className="bg-indigo-600 h-full rounded-full" style={{ width: `${mat.progress}%` }} />
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </motion.section>
    </motion.div>
  );
};
