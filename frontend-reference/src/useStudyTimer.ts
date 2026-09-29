// Đo thời gian thật giữa lúc bắt đầu 1 hoạt động (tạo session/attempt) và lúc nộp bài, CHỈ khi
// user đã tự bật "chế độ bấm giờ" (Dashboard "This week, in minutes" — GET/PATCH /api/users/me,
// mục 3.16 lumina_context.md). Không dùng cho hiển thị đồng hồ đếm ngược có sẵn trong UI (đó là
// state riêng của từng view) — hook này chỉ phục vụ đo để gửi lên backend.
import { useRef } from "react";
import { useLearningStats } from "./stats";

export function useStudyTimer() {
  const { stats } = useLearningStats();
  const markRef = useRef<number | null>(null);

  function start() {
    markRef.current = Date.now();
  }

  // Giây trôi qua kể từ start()/lap() gần nhất, rồi tự đặt lại mốc — dùng được cả cho hoạt động
  // 1 lần (Reading/Listening/Writing: start() rồi lap() đúng 1 lần lúc nộp) lẫn nhiều lượt trong
  // cùng 1 phiên (Speaking: lap() sau mỗi lượt nói, cộng dồn đúng theo backend vì mỗi lần đều ghi
  // 1 dòng study_time_log riêng). Trả undefined khi tắt bấm giờ hoặc chưa start() — caller truyền
  // thẳng vào duration_seconds mà không cần kiểm tra thêm.
  function lap(): number | undefined {
    if (!stats.timerModeEnabled || markRef.current === null) return undefined;
    const seconds = Math.round((Date.now() - markRef.current) / 1000);
    markRef.current = Date.now();
    return seconds > 0 ? seconds : undefined;
  }

  return { start, lap };
}
