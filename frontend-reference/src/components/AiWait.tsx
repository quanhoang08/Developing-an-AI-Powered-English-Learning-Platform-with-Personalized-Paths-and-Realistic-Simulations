// Chỉ báo chờ cho lệnh gọi AI local (Ollama 7B trên GPU 6GB: 10–30 s/lượt, không streaming).
// Đếm giây + thanh tiến độ ước lượng để người học biết app không bị treo; quá ngưỡng thì báo rõ.
import React, { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";

interface AiWaitProps {
  active: boolean;
  label: string;
  // Thời gian điển hình (giây) của luồng này — chỉ dùng để vẽ thanh tiến độ và ngưỡng "lâu hơn thường lệ".
  expectedSeconds: number;
  className?: string;
}

export const AiWait: React.FC<AiWaitProps> = ({ active, label, expectedSeconds, className = "" }) => {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!active) return;
    setElapsed(0);
    const startedAt = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 500);
    return () => window.clearInterval(timer);
  }, [active]);

  if (!active) return null;

  // Thanh dừng ở 95% cho tới khi API trả về — không giả vờ đã xong.
  const percent = Math.min(95, Math.round((elapsed / expectedSeconds) * 100));
  const slow = elapsed > expectedSeconds * 1.5;

  return (
    <div role="status" aria-live="polite" className={`rounded-2xl bg-indigo-50 border border-indigo-200 px-4 py-3 ${className}`}>
      <div className="flex items-center gap-2 text-sm font-semibold text-indigo-900">
        <Sparkles className="w-4 h-4 animate-spin shrink-0" aria-hidden="true" />
        <span>{label}</span>
        <span className="num ml-auto text-xs font-normal text-indigo-700">{elapsed}s</span>
      </div>
      <div className="mt-2 h-1.5 rounded-full bg-indigo-100 overflow-hidden" aria-hidden="true">
        <div className="h-full rounded-full bg-indigo-600 transition-[width] duration-500" style={{ width: `${percent}%` }} />
      </div>
      <p className="mt-1.5 text-xs text-indigo-800">
        {slow
          ? "Lâu hơn thường lệ — model AI trên máy vẫn đang chạy, bạn cứ đợi thêm chút nhé (đừng chuyển tab)."
          : `AI chạy trên máy bạn nên cần khoảng ${expectedSeconds} giây. Vui lòng ở lại trang này cho tới khi xong.`}
      </p>
    </div>
  );
};
