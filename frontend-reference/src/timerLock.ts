// Cờ toàn cục "đồng hồ đếm ngược đang dở" (đang chạy hoặc tạm dừng giữa chừng). CountdownTimer bật/tắt cờ,
// App chặn đổi tab và Sidebar hiển thị trạng thái khóa — vì đổi tab sẽ unmount view và reset đồng hồ.
import { useSyncExternalStore } from "react";

export const TIMER_LOCK_MESSAGE = "Timer in progress — let it finish, or pick a new time to reset, before switching.";

let locked = false;
const listeners = new Set<() => void>();

export function setTimerLocked(next: boolean) {
  if (locked === next) return;
  locked = next;
  listeners.forEach((listener) => listener());
}

export function isTimerLocked() {
  return locked;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useTimerLocked() {
  return useSyncExternalStore(subscribe, isTimerLocked, () => false);
}
