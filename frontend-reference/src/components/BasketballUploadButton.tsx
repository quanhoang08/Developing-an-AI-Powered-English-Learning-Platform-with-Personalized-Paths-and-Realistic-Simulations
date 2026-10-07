// Upload kiểu "bóng rổ":
// - BasketballCourt: chọn file xong thì file thành quả bóng, kéo tự do rồi vuốt ném vào rổ để upload.
// - BasketballUploadButton: nút dự phòng (bàn phím/trình đọc màn hình); đang tải thì bóng nảy, xong thì
//   ném vào rổ, lỗi thì bật vành. Chuyển động của nút là CSS keyframes (index.css, nhóm .bb-*).
import React, { useEffect, useRef, useState } from "react";

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

// ---- Sân ném bóng ----
// Đơn vị: px và ms. Vành rổ nằm giữa sân, cao RIM_Y; bóng chỉ được kéo trong nửa dưới để phải ném thật.
const COURT_HEIGHT = 210;
const BALL_R = 18;
const RIM_Y = 70;
const RIM_HALF = 30;
const GRAVITY = 0.0022;
const MAX_SPEED = 2.6;
const MIN_DRAG_Y = COURT_HEIGHT * 0.5;

type Hint = "ready" | "miss" | "scored";

const HINT: Record<Hint, string> = {
  ready: "Drag the ball anywhere, then flick it up into the hoop to upload.",
  miss: "Missed! Grab the ball and try again.",
  scored: "Swish! Uploading your file…",
};

interface BasketballCourtProps {
  // Nhãn in lên quả bóng, ví dụ "PDF".
  fileLabel: string;
  // true khi đang upload hoặc chưa kết nối backend: không cho kéo bóng.
  disabled: boolean;
  onScore: () => void;
}

export const BasketballCourt: React.FC<BasketballCourtProps> = ({ fileLabel, disabled, onScore }) => {
  const courtRef = useRef<HTMLDivElement>(null);
  const ballRef = useRef<HTMLDivElement>(null);
  // Trạng thái vật lý để trong ref và vẽ thẳng vào style: tránh re-render React mỗi frame.
  const sim = useRef({ x: 0, y: 0, vx: 0, vy: 0, dragging: false, scored: false, raf: 0, samples: [] as { x: number; y: number; t: number }[] });
  const onScoreRef = useRef(onScore);
  onScoreRef.current = onScore;
  const [hint, setHint] = useState<Hint>("ready");

  const courtWidth = () => courtRef.current?.clientWidth ?? 400;

  const draw = () => {
    const s = sim.current;
    const ball = ballRef.current;
    if (!ball) return;
    ball.style.transform = `translate(${s.x - BALL_R}px, ${s.y - BALL_R}px)`;
    // Chỉ xoay hình quả bóng, nhãn định dạng file giữ thẳng để đọc được.
    (ball.firstElementChild as SVGElement).style.transform = `rotate(${s.x * 2}deg)`;
  };

  const resetBall = () => {
    const s = sim.current;
    cancelAnimationFrame(s.raf);
    Object.assign(s, { x: courtWidth() / 2, y: COURT_HEIGHT - BALL_R, vx: 0, vy: 0, dragging: false, scored: false });
    setHint("ready");
    draw();
  };

  useEffect(() => {
    resetBall();
    return () => cancelAnimationFrame(sim.current.raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Upload lỗi thì parent mở khóa lại (disabled=false): trả bóng về vạch để ném lại.
  useEffect(() => {
    if (!disabled && sim.current.scored) resetBall();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled]);

  const step = (dt: number): boolean => {
    const s = sim.current;
    const width = courtWidth();
    const rimLeft = width / 2 - RIM_HALF;
    const rimRight = width / 2 + RIM_HALF;
    s.vy += GRAVITY * dt;
    let nx = s.x + s.vx * dt;
    let ny = s.y + s.vy * dt;

    if (!s.scored) {
      // Va vào 2 mép vành: phản xạ vận tốc theo pháp tuyến (hệ số nảy 0.6).
      for (const edge of [rimLeft, rimRight]) {
        const dx = nx - edge;
        const dy = ny - RIM_Y;
        const dist = Math.hypot(dx, dy);
        if (dist > 0 && dist < BALL_R) {
          const nxN = dx / dist;
          const nyN = dy / dist;
          nx = edge + nxN * BALL_R;
          ny = RIM_Y + nyN * BALL_R;
          const dot = s.vx * nxN + s.vy * nyN;
          if (dot < 0) {
            s.vx -= 1.6 * dot * nxN;
            s.vy -= 1.6 * dot * nyN;
          }
        }
      }
      // Vào rổ: tâm bóng đi XUỐNG qua mặt vành, nằm lọt giữa 2 mép.
      if (s.vy > 0 && s.y < RIM_Y && ny >= RIM_Y && nx > rimLeft + BALL_R * 0.4 && nx < rimRight - BALL_R * 0.4) {
        s.scored = true;
        s.vx = 0;
        nx = width / 2;
        setHint("scored");
        onScoreRef.current();
      }
    }

    // Tường trái/phải và trần.
    if (nx < BALL_R) { nx = BALL_R; s.vx = -s.vx * 0.6; }
    if (nx > width - BALL_R) { nx = width - BALL_R; s.vx = -s.vx * 0.6; }
    if (ny < BALL_R) { ny = BALL_R; s.vy = Math.abs(s.vy) * 0.5; }

    // Sàn: nảy rồi lăn chậm dần; dừng hẳn thì kết thúc vòng lặp.
    let resting = false;
    if (ny >= COURT_HEIGHT - BALL_R) {
      ny = COURT_HEIGHT - BALL_R;
      if (s.vy > 0) s.vy = -s.vy * 0.45;
      s.vx *= 0.92;
      if (Math.abs(s.vy) < 0.06) s.vy = 0;
      resting = s.vy === 0 && Math.abs(s.vx) < 0.02;
    }

    s.x = nx;
    s.y = ny;
    draw();
    if (resting && !s.scored) setHint("miss");
    return !resting;
  };

  const launch = () => {
    let last = performance.now();
    const frame = (now: number) => {
      const dt = Math.min(32, now - last);
      last = now;
      if (step(dt)) sim.current.raf = requestAnimationFrame(frame);
    };
    sim.current.raf = requestAnimationFrame(frame);
  };

  const localPoint = (event: React.PointerEvent) => {
    const rect = courtRef.current!.getBoundingClientRect();
    return {
      x: Math.min(rect.width - BALL_R, Math.max(BALL_R, event.clientX - rect.left)),
      y: Math.min(COURT_HEIGHT - BALL_R, Math.max(MIN_DRAG_Y, event.clientY - rect.top)),
    };
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    const s = sim.current;
    if (disabled || s.scored) return;
    cancelAnimationFrame(s.raf);
    event.currentTarget.setPointerCapture(event.pointerId);
    s.dragging = true;
    s.samples = [];
    setHint("ready");
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const s = sim.current;
    if (!s.dragging) return;
    const point = localPoint(event);
    s.x = point.x;
    s.y = point.y;
    s.samples.push({ ...point, t: event.timeStamp });
    // Chỉ giữ ~100ms cuối để tính lực vuốt lúc thả tay.
    s.samples = s.samples.filter((sample) => event.timeStamp - sample.t < 100);
    draw();
  };

  const handlePointerUp = () => {
    const s = sim.current;
    if (!s.dragging) return;
    s.dragging = false;
    const first = s.samples[0];
    const last = s.samples[s.samples.length - 1];
    const elapsed = first && last ? last.t - first.t : 0;
    s.vx = elapsed > 0 ? (last.x - first.x) / elapsed : 0;
    s.vy = elapsed > 0 ? (last.y - first.y) / elapsed : 0;
    const speed = Math.hypot(s.vx, s.vy);
    if (speed > MAX_SPEED) {
      s.vx *= MAX_SPEED / speed;
      s.vy *= MAX_SPEED / speed;
    }
    launch();
  };

  return (
    <div>
      <div
        ref={courtRef}
        className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-amber-50 to-orange-100/70 ring-1 ring-amber-900/10 select-none"
        style={{ height: COURT_HEIGHT }}
      >
        {/* Bảng rổ nằm sau bóng. */}
        <svg viewBox="0 0 80 40" className="absolute w-20 h-10 pointer-events-none" style={{ left: "calc(50% - 40px)", top: RIM_Y - 36 }} aria-hidden="true">
          <rect x="14" y="0" width="52" height="34" rx="3" fill="#fffdf8" stroke="#475569" strokeWidth="2" />
          <rect x="29" y="14" width="22" height="16" fill="none" stroke="#e85d38" strokeWidth="1.6" />
        </svg>

        {/* Sàn sân. */}
        <div className="absolute inset-x-0 bottom-0 h-1 bg-amber-900/15" />

        <div
          ref={ballRef}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          className={`absolute left-0 top-0 touch-none ${disabled ? "cursor-not-allowed" : "cursor-grab active:cursor-grabbing"}`}
          style={{ width: BALL_R * 2, height: BALL_R * 2 }}
          aria-hidden="true"
        >
          <Ball className="block w-full h-full drop-shadow" />
          <span className="absolute inset-0 flex items-center justify-center text-[9px] font-black text-white [text-shadow:0_1px_2px_rgba(0,0,0,0.7)]">
            {fileLabel}
          </span>
        </div>

        {/* Vành + lưới vẽ SAU bóng để bóng trông như lọt vào trong rổ. */}
        <svg
          viewBox="0 0 80 34"
          className="absolute w-20 pointer-events-none"
          style={{ left: "calc(50% - 40px)", top: RIM_Y - 2, height: 34 }}
          aria-hidden="true"
        >
          <rect x="9" y="0.5" width="62" height="3.5" rx="1.7" fill="#e85d38" />
          <path d="M11 4l6 28h46l6-28M23 4l3 28M40 4v28M57 4l-3 28M14 16h52" fill="none" stroke="#94a3b8" strokeWidth="1.2" />
        </svg>
      </div>
      <p className="mt-2 text-[11px] text-slate-500" aria-live="polite">
        {HINT[hint]}
      </p>
    </div>
  );
};
