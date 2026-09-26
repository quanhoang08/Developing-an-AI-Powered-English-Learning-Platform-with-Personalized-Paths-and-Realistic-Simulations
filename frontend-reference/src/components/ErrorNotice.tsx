// Thông báo lỗi thân thiện dùng chung: nói rõ chuyện gì xảy ra, người dùng có thể làm gì, kèm nút
// "Try again" (chạy lại đúng thao tác vừa lỗi) và "Back to Dashboard" thay vì chỉ hiện mã lỗi trơ trọi.
import React from "react";
import { AlertTriangle, Home, RotateCw } from "lucide-react";
import { ApiError } from "../api";

// Theo mã lỗi (ApiError.code): tiêu đề + gợi ý cách tự xử lý. Mã lạ dùng nội dung mặc định bên dưới.
const HELP: Record<string, { title: string; hint: string }> = {
  ollama_unreachable: {
    title: "The local AI isn't running",
    hint: "Start Ollama on this computer (open the Ollama app or run “ollama serve”), then try again.",
  },
  ollama_model_missing: {
    title: "The AI model isn't installed",
    hint: "Install it with “ollama pull qwen2.5:7b-instruct-q4_K_M”, then try again.",
  },
  ollama_timeout: {
    title: "The AI is taking too long",
    hint: "The first request after a break can be slow while the model loads. Trying again usually works.",
  },
  ai_quota_exceeded: {
    title: "AI usage limit reached",
    hint: "Try again later, or continue with another activity in the meantime.",
  },
  ai_bad_output: {
    title: "The AI gave an unusable answer",
    hint: "Small local models slip up sometimes. A fresh try usually works.",
  },
  ai_unavailable: {
    title: "The AI service is unavailable",
    hint: "Try again in a moment.",
  },
  network_unreachable: {
    title: "Can't reach the server",
    hint: "Check your connection and that the Lumina backend is running, then try again.",
  },
  invalid_token: {
    title: "Your session has expired",
    hint: "Please sign in again from the top of the page.",
  },
  attempt_already_submitted: {
    title: "This exercise was already submitted",
    hint: "Start a new exercise to keep practising.",
  },
};

const FALLBACK = { title: "Something went wrong", hint: "Try again. If it keeps happening, come back a bit later." };

// Lỗi mà bấm thử lại vô ích (cần người dùng cài model / đăng nhập lại / chờ hết hạn mức).
const NOT_RETRYABLE = ["ollama_model_missing", "ai_quota_exceeded", "invalid_token", "attempt_already_submitted"];

interface ErrorNoticeProps {
  error: unknown;
  // Chạy lại đúng thao tác vừa lỗi; không truyền thì ẩn nút "Try again".
  onRetry?: () => void;
  retryLabel?: string;
}

// Chuyển sang tab khác mà không cần prop drilling: App lắng nghe sự kiện này.
export function navigateTo(tab: string) {
  window.dispatchEvent(new CustomEvent("lumina-navigate", { detail: tab }));
}

export const ErrorNotice: React.FC<ErrorNoticeProps> = ({ error, onRetry, retryLabel = "Try again" }) => {
  const code = error instanceof ApiError ? error.code : "unknown";
  const help = HELP[code] ?? FALLBACK;
  // message của endpoint cũ chính là mã lỗi (vd "ai_service_unavailable") — không đưa cho người dùng đọc.
  const detail =
    error instanceof Error && error.message !== code && !error.message.startsWith("Backend request failed")
      ? error.message
      : null;
  const canRetry = onRetry !== undefined && !NOT_RETRYABLE.includes(code);

  return (
    <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 space-y-3">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="text-sm font-bold text-rose-900">{help.title}</p>
          {detail && detail !== help.title && <p className="text-sm text-rose-800">{detail}</p>}
          <p className="text-sm text-rose-800/90">{help.hint}</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 pl-8">
        {canRetry && (
          <button
            onClick={onRetry}
            className="px-4 py-2 bg-rose-700 hover:bg-rose-800 text-white font-bold text-xs rounded-xl flex items-center gap-1.5 cursor-pointer"
          >
            <RotateCw className="w-3.5 h-3.5" /> {retryLabel}
          </button>
        )}
        <button
          onClick={() => navigateTo("dashboard")}
          className="px-4 py-2 bg-white hover:bg-rose-100 border border-rose-200 text-rose-900 font-bold text-xs rounded-xl flex items-center gap-1.5 cursor-pointer"
        >
          <Home className="w-3.5 h-3.5" /> Back to Dashboard
        </button>
      </div>
    </div>
  );
};
