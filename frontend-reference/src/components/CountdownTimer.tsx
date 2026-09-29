// Đồng hồ đếm ngược dùng chung cho 4 kỹ năng: gợi ý mốc giờ theo dạng bài thật của IELTS / TOEIC
// (Reading còn lọc theo level CEFR của bài đọc) hoặc tự nhập "phút" / "phút:giây". Độc lập với
// useStudyTimer (hook đó chỉ đo thời gian thật để gửi backend, không hiển thị gì).
import React, { useEffect, useRef, useState } from "react";
import { ChevronDown, Pause, Play, RotateCcw, Timer } from "lucide-react";
import { setTimerLocked } from "../timerLock";

export type TimerSkill = "reading" | "listening" | "writing" | "speaking";

interface Preset {
  label: string;
  seconds: number;
  levels?: string[]; // chỉ hiện với các level CEFR này (bỏ trống = luôn hiện)
}

const PRESETS: Record<TimerSkill, Preset[]> = {
  reading: [
    { label: "TOEIC Part 6 · 4 texts", seconds: 8 * 60, levels: ["B1"] },
    { label: "TOEIC Part 7 · single passage", seconds: 4 * 60, levels: ["B1", "B2"] },
    { label: "TOEIC Part 7 · multiple passages", seconds: 9 * 60, levels: ["B2", "C1"] },
    { label: "IELTS Reading · 1 passage", seconds: 20 * 60, levels: ["B2", "C1", "C2"] },
    { label: "IELTS Reading · full test", seconds: 60 * 60, levels: ["C1", "C2"] },
  ],
  listening: [
    { label: "TOEIC Part 1 · photographs", seconds: 4 * 60 },
    { label: "TOEIC Part 2 · question-response", seconds: 10 * 60 },
    { label: "TOEIC Part 3 · conversations", seconds: 17 * 60 },
    { label: "TOEIC Part 4 · talks", seconds: 14 * 60 },
    { label: "IELTS Listening · 1 section", seconds: 8 * 60 },
    { label: "IELTS Listening · full test", seconds: 30 * 60 },
  ],
  writing: [
    { label: "TOEIC Q1–5 · sentence from picture", seconds: 8 * 60 },
    { label: "TOEIC Q6–7 · email reply", seconds: 10 * 60 },
    { label: "TOEIC Q8 · opinion essay", seconds: 30 * 60 },
    { label: "IELTS Task 1 · report", seconds: 20 * 60 },
    { label: "IELTS Task 2 · essay", seconds: 40 * 60 },
  ],
  speaking: [
    { label: "TOEIC · prep (read aloud / picture)", seconds: 45 },
    { label: "TOEIC · opinion answer", seconds: 60 },
    { label: "IELTS Part 2 · prep", seconds: 60 },
    { label: "IELTS Part 2 · talk", seconds: 2 * 60 },
    { label: "IELTS Part 1 · interview", seconds: 5 * 60 },
    { label: "IELTS Part 3 · discussion", seconds: 5 * 60 },
  ],
};

const MAX_SECONDS = 180 * 60;

export function formatClock(secs: number): string {
  const mins = Math.floor(secs / 60);
  return `${String(mins).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}`;
}

// "20" = 20 phút, "1:30" = 1 phút 30 giây; trả null nếu sai định dạng hoặc ngoài (0, 180 phút].
function parseDuration(text: string): number | null {
  const match = text.trim().match(/^(\d{1,3})(?::([0-5]?\d))?$/);
  if (!match) return null;
  const seconds = Number(match[1]) * 60 + Number(match[2] ?? 0);
  return seconds > 0 && seconds <= MAX_SECONDS ? seconds : null;
}

interface Props {
  skill: TimerSkill;
  level?: string; // level CEFR hiện tại, chỉ Reading dùng để lọc gợi ý
  initialSeconds?: number; // ép mốc ban đầu (vd. time_limit_seconds từ backend); đổi `key` để áp dụng lại
  autoStart?: boolean;
}

export const CountdownTimer: React.FC<Props> = ({ skill, level, initialSeconds, autoStart = false }) => {
  const options = PRESETS[skill].filter((preset) => !preset.levels || !level || preset.levels.includes(level));
  const [total, setTotal] = useState(() => initialSeconds ?? options[0].seconds);
  const [left, setLeft] = useState(total);
  const [running, setRunning] = useState(autoStart);
  const [open, setOpen] = useState(false);
  const [custom, setCustom] = useState("");
  const leftRef = useRef(left);
  leftRef.current = left;

  // Đang dở (chạy hoặc tạm dừng giữa chừng) thì khóa đổi tab, vì đổi tab unmount view và reset đồng hồ.
  const inProgress = running || (left > 0 && left < total);
  useEffect(() => setTimerLocked(inProgress), [inProgress]);
  useEffect(() => () => setTimerLocked(false), []);

  // Tính theo mốc kết thúc thay vì trừ 1 mỗi tick để không bị trôi khi tab nền bị throttle.
  useEffect(() => {
    if (!running) return;
    const endAt = Date.now() + leftRef.current * 1000;
    const id = window.setInterval(() => {
      const remaining = Math.max(0, Math.ceil((endAt - Date.now()) / 1000));
      setLeft(remaining);
      if (remaining === 0) setRunning(false);
    }, 250);
    return () => window.clearInterval(id);
  }, [running]);

  function choose(seconds: number) {
    setTotal(seconds);
    setLeft(seconds);
    setRunning(false);
    setOpen(false);
    setCustom("");
  }

  const customSeconds = parseDuration(custom);
  const finished = left === 0;

  return (
    <div className="relative shrink-0">
      <div
        className={`flex items-center gap-2 pl-3.5 pr-1.5 py-1.5 rounded-full text-xs font-bold whitespace-nowrap ${
          finished ? "bg-rose-100 text-rose-800" : "bg-amber-100 text-amber-900"
        }`}
      >
        <Timer className={`w-4 h-4 ${finished ? "text-rose-600" : "text-amber-600"}`} />
        <button
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          aria-label="Choose timer duration"
          className="flex items-center gap-1 cursor-pointer"
        >
          <span className="num text-sm">{finished ? "Time's up" : formatClock(left)}</span>
          <ChevronDown className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => (finished ? choose(total) : setRunning(!running))}
          aria-label={finished ? "Restart timer" : running ? "Pause timer" : "Start timer"}
          className="p-1.5 rounded-full bg-black/10 hover:bg-black/20 transition-colors cursor-pointer"
        >
          {finished ? <RotateCcw className="w-3.5 h-3.5" /> : running ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-current" />}
        </button>
      </div>

      {open && (
        <div className="absolute right-0 mt-2 w-72 z-30 bg-[#fffdf8] rounded-2xl p-3 shadow-[0_24px_48px_-20px_rgba(32,29,24,0.5)] ring-1 ring-slate-900/10 space-y-2">
          <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider px-1">Suggested time</p>
          {options.map((preset) => (
            <button
              key={preset.label}
              onClick={() => choose(preset.seconds)}
              className={`w-full flex items-center justify-between gap-3 px-3 py-2 rounded-xl text-xs text-left cursor-pointer transition-colors ${
                preset.seconds === total ? "bg-indigo-100 text-indigo-900 font-bold" : "hover:bg-slate-100 text-slate-700 font-medium"
              }`}
            >
              <span>{preset.label}</span>
              <span className="num shrink-0">{formatClock(preset.seconds)}</span>
            </button>
          ))}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (customSeconds) choose(customSeconds);
            }}
            className="flex items-center gap-2 pt-2 border-t border-dashed border-slate-200"
          >
            <input
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
              placeholder="Custom: minutes or m:ss"
              aria-label="Custom duration"
              className="flex-1 min-w-0 px-3 py-2 text-xs bg-white ring-1 ring-slate-900/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
            />
            <button
              type="submit"
              disabled={!customSeconds}
              className="px-3 py-2 text-xs font-bold bg-indigo-700 hover:bg-indigo-800 text-white rounded-xl disabled:opacity-40 cursor-pointer"
            >
              Set
            </button>
          </form>
        </div>
      )}
    </div>
  );
};
