// Nút upload kiểu "bóng rổ": đang tải thì bóng nảy, xong thì ném vào rổ, lỗi thì bóng bật vành rơi ra.
// Toàn bộ chuyển động là CSS keyframes (index.css, nhóm .bb-*), component chỉ đổi class theo phase.
import React from "react";

export type UploadPhase = "idle" | "uploading" | "success" | "error";

interface BasketballUploadButtonProps {
  phase: UploadPhase;
  disabled?: boolean;
  onClick: () => void;
}

const LABEL: Record<UploadPhase, string> = {
  idle: "Upload to Notebook",
  uploading: "Uploading…",
  success: "Uploaded!",
  error: "Missed — try again",
};

const Ball: React.FC<{ className?: string }> = ({ className }) => (
  <svg viewBox="0 0 20 20" className={className} aria-hidden="true">
    <circle cx="10" cy="10" r="9.2" fill="#e8742a" stroke="#7a3410" strokeWidth="1.2" />
    <path
      d="M10 .8v18.4M.8 10h18.4M3.6 3.4c3 2.6 3 10.6 0 13.2M16.4 3.4c-3 2.6-3 10.6 0 13.2"
      fill="none"
      stroke="#7a3410"
      strokeWidth="1"
    />
  </svg>
);

export const BasketballUploadButton: React.FC<BasketballUploadButtonProps> = ({ phase, disabled, onClick }) => {
  const isIdle = phase === "idle";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || !isIdle}
      className={`bb-court bb-${phase} relative h-11 w-56 rounded-xl text-xs font-bold transition-colors duration-300 disabled:cursor-not-allowed ${
        isIdle
          ? "bg-indigo-700 hover:bg-indigo-800 text-white disabled:opacity-40"
          : "bg-indigo-50 ring-1 ring-indigo-200 text-indigo-800"
      }`}
    >
      {/* Rổ: chỉ hiện sau khi bấm upload. */}
      <svg viewBox="0 0 40 34" className="bb-hoop absolute right-2 -top-4 w-10 h-9" aria-hidden="true">
        <rect x="33" y="0" width="3" height="24" rx="1" fill="#475569" />
        <rect x="6" y="9" width="27" height="2.5" rx="1.2" fill="#e85d38" />
        <path
          className="bb-net"
          d="M7 11.5l3 12h17l3-12M13 11.5l2 12M19.5 11.5v12M26 11.5l-2 12"
          fill="none"
          stroke="#94a3b8"
          strokeWidth="1.1"
        />
      </svg>

      {/* Bóng: lớp ngoài chạy trục X, lớp giữa trục Y (easing khác nhau -> quỹ đạo parabol), lớp trong xoay. */}
      <span className="bb-x absolute left-3 top-3 w-5 h-5" aria-hidden="true">
        <span className="bb-y block w-5 h-5">
          <Ball className="bb-spin block w-5 h-5" />
        </span>
      </span>

      <span className={`relative block transition-[padding] duration-300 ${isIdle ? "pl-6" : "pl-6 pr-10"}`}>
        {LABEL[phase]}
      </span>
    </button>
  );
};
