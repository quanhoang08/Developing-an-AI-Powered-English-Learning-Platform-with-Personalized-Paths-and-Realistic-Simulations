// Store dùng chung cho streak/XP thật: một lần fetch, nhiều component đọc (Header, Sidebar,
// Dashboard, Analytics) nên không mỗi nơi tự gọi API rồi lệch số với nhau.
import { useSyncExternalStore } from "react";
import { getAccessToken, getStreaks } from "./api";

export interface LearningStats {
  currentStreak: number;
  longestStreak: number;
  todayActive: boolean;
  totalXp: number;
  level: number;
  xpIntoLevel: number;
  xpForNextLevel: number;
  recentActiveDates: string[];
}

// Chưa đăng nhập hoặc chưa tải xong: 0 thật, không phải số demo.
const EMPTY_STATS: LearningStats = {
  currentStreak: 0,
  longestStreak: 0,
  todayActive: false,
  totalXp: 0,
  level: 1,
  xpIntoLevel: 0,
  xpForNextLevel: 100,
  recentActiveDates: [],
};

const REFRESH_DELAY_MS = 300;

let snapshot: LearningStats = EMPTY_STATS;
let refreshTimer: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<() => void>();

function publish(next: LearningStats) {
  snapshot = next;
  listeners.forEach((listener) => listener());
}

async function loadStats() {
  if (!getAccessToken()) {
    publish(EMPTY_STATS);
    return;
  }
  try {
    const data = await getStreaks();
    publish({
      currentStreak: data.current_streak,
      longestStreak: data.longest_streak,
      todayActive: data.today_active,
      totalXp: data.total_xp,
      level: data.level,
      xpIntoLevel: data.xp_into_level,
      xpForNextLevel: data.xp_for_next_level,
      recentActiveDates: data.recent_active_dates,
    });
  } catch (error) {
    // Giữ số liệu cũ khi backend lỗi tạm thời; 401 đã được api.ts xử lý (xóa token + phát auth event).
    console.error("Failed to load learning stats", error);
  }
}

// Gom nhiều sự kiện liên tiếp (vd nộp bài + lưu từ) thành một lần fetch.
function scheduleLoad() {
  if (refreshTimer) clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => {
    refreshTimer = null;
    void loadStats();
  }, REFRESH_DELAY_MS);
}

function subscribe(listener: () => void) {
  if (listeners.size === 0) {
    window.addEventListener("lumina-stats-refresh", scheduleLoad);
    window.addEventListener("lumina-auth-changed", scheduleLoad);
    void loadStats();
  }
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      window.removeEventListener("lumina-stats-refresh", scheduleLoad);
      window.removeEventListener("lumina-auth-changed", scheduleLoad);
      if (refreshTimer) clearTimeout(refreshTimer);
      refreshTimer = null;
    }
  };
}

export function useLearningStats(): { stats: LearningStats } {
  const stats = useSyncExternalStore(subscribe, () => snapshot, () => EMPTY_STATS);
  return { stats };
}
