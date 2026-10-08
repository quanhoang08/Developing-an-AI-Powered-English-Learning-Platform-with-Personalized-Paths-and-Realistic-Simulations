// Upload kiểu "bóng rổ":
// - BasketballCourt: chọn file xong thì file thành quả bóng; nhấn giữ, kéo lùi để ngắm (chấm quỹ đạo),
//   buông tay là ném — vào rổ thì upload.
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
// Kiểu "ná cao su": nhấn giữ bóng, kéo LÙI ngược hướng muốn ném (chấm đen hiện quỹ đạo), buông tay là ném.
// Không phụ thuộc tốc độ tay nên chuột và touchpad dùng như nhau. Đơn vị: px và ms.
const COURT_HEIGHT = 210;
const BALL_R = 18;
const RIM_Y = 70;
const RIM_HALF = 48;
// Hình rổ vẽ trong viewBox rộng 80 (vành 62): phóng theo RIM_HALF để hình khớp vùng tính điểm.
const HOOP_W = (RIM_HALF * 2 * 80) / 62;
const GRAVITY = 0.0018;
// Vật lý chạy theo bước cố định để quỹ đạo chấm xem trước trùng khớp đường bay thật.
const STEP_MS = 16;
// Kéo lùi 1px -> 0.011 px/ms (từ sàn kéo ~100px là tới rổ, vừa tầm một lần vuốt touchpad);
// kéo tối đa MAX_PULL; kéo ngắn hơn MIN_PULL rồi buông = huỷ, không ném.
const POWER = 0.011;
const MAX_PULL = 150;
const MIN_PULL = 15;
const PULL_NUDGE = 25;
const PREVIEW_STEPS = 80;
const PREVIEW_EVERY = 3;

type Point = { x: number; y: number };

// Vận tốc ném = ngược hướng kéo, tỉ lệ độ dài kéo (giới hạn MAX_PULL).
export function launchVelocity(pullX: number, pullY: number): { vx: number; vy: number } {
  const length = Math.hypot(pullX, pullY);
  const scale = length > MAX_PULL ? MAX_PULL / length : 1;
  return { vx: -pullX * scale * POWER, vy: -pullY * scale * POWER };
}

// Các điểm chấm quỹ đạo (cùng công thức với step() khi bóng bay tự do), dừng khi chạm tường/sàn.
export function trajectory(x: number, y: number, vx: number, vy: number, width: number): Point[] {
  const dots: Point[] = [];
  for (let i = 1; i <= PREVIEW_STEPS; i++) {
    vy += GRAVITY * STEP_MS;
    x += vx * STEP_MS;
    y += vy * STEP_MS;
    if (x < BALL_R || x > width - BALL_R || y > COURT_HEIGHT - BALL_R) break;
    if (i % PREVIEW_EVERY === 0) dots.push({ x, y });
  }
  return dots;
}

type Hint = "ready" | "miss" | "scored";

const HINT: Record<Hint, string> = {
  ready: "Press and hold the ball, pull it back to aim along the dots, then let go to shoot.",
  miss: "Missed! Pull the ball back and try again.",
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
  const sim = useRef({ x: 0, y: 0, vx: 0, vy: 0, dragging: false, flying: false, scored: false, raf: 0, startX: 0, startY: 0, pullX: 0, pullY: 0 });
  const onScoreRef = useRef(onScore);
  onScoreRef.current = onScore;
  const [hint, setHint] = useState<Hint>("ready");
  // Chấm quỹ đạo khi đang ngắm (null = không ngắm).
  const [aim, setAim] = useState<Point[] | null>(null);

  const courtWidth = () => courtRef.current?.clientWidth ?? 400;

  const draw = () => {
    const s = sim.current;
    const ball = ballRef.current;
    if (!ball) return;
    // Đang ngắm: bóng nhích theo hướng kéo (tối đa PULL_NUDGE px) để thấy rõ là đang cầm bóng.
    const pull = s.dragging ? Math.hypot(s.pullX, s.pullY) : 0;
    const nudge = pull > 0 ? Math.min(PULL_NUDGE, pull * 0.25) / pull : 0;
    ball.style.transform = `translate(${s.x - BALL_R + s.pullX * nudge}px, ${s.y - BALL_R + s.pullY * nudge}px)`;
    // Chỉ xoay hình quả bóng, nhãn định dạng file giữ thẳng để đọc được.
    (ball.firstElementChild as SVGElement).style.transform = `rotate(${s.x * 2}deg)`;
  };

  const resetBall = () => {
    const s = sim.current;
    cancelAnimationFrame(s.raf);
    Object.assign(s, { x: courtWidth() / 2, y: COURT_HEIGHT - BALL_R, vx: 0, vy: 0, dragging: false, flying: false, scored: false });
    setHint("ready");
    setAim(null);
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
      if (s.vy > 0 && s.y < RIM_Y && ny >= RIM_Y && nx > rimLeft && nx < rimRight) {
        s.scored = true;
        s.vx = 0;
        nx = width / 2;
        setHint("scored");
        onScoreRef.current();
      }
    }

    // Tường trái/phải. Không có trần: ném cao thì bóng bay khỏi khung rồi rơi lại, đúng như đường chấm.
    if (nx < BALL_R) { nx = BALL_R; s.vx = -s.vx * 0.6; }
    if (nx > width - BALL_R) { nx = width - BALL_R; s.vx = -s.vx * 0.6; }

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
    if (resting) {
      s.flying = false;
      if (!s.scored) setHint("miss");
    }
    return !resting;
  };

  const launch = () => {
    const s = sim.current;
    s.flying = true;
    let last = performance.now();
    let pending = 0;
    const frame = (now: number) => {
      // Gom thời gian thực rồi chạy từng bước STEP_MS: tốc độ khung hình không làm lệch quỹ đạo đã ngắm.
      pending = Math.min(pending + now - last, STEP_MS * 4);
      last = now;
      let alive = true;
      while (alive && pending >= STEP_MS) {
        alive = step(STEP_MS);
        pending -= STEP_MS;
      }
      if (alive) s.raf = requestAnimationFrame(frame);
    };
    s.raf = requestAnimationFrame(frame);
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    const s = sim.current;
    if (disabled || s.scored || s.flying) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    Object.assign(s, { dragging: true, startX: event.clientX, startY: event.clientY, pullX: 0, pullY: 0 });
    setHint("ready");
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const s = sim.current;
    if (!s.dragging) return;
    // Độ kéo đo từ chỗ nhấn xuống, theo con trỏ thật (có thể ra ngoài sân nhờ pointer capture).
    s.pullX = event.clientX - s.startX;
    s.pullY = event.clientY - s.startY;
    draw();
    if (Math.hypot(s.pullX, s.pullY) < MIN_PULL) {
      setAim(null);
      return;
    }
    const v = launchVelocity(s.pullX, s.pullY);
    setAim(trajectory(s.x, s.y, v.vx, v.vy, courtWidth()));
  };

  const handlePointerUp = () => {
    const s = sim.current;
    if (!s.dragging) return;
    s.dragging = false;
    setAim(null);
    draw();
    // Kéo quá ngắn = huỷ ngắm, bóng đứng yên.
    if (Math.hypot(s.pullX, s.pullY) < MIN_PULL) return;
    const v = launchVelocity(s.pullX, s.pullY);
    s.vx = v.vx;
    s.vy = v.vy;
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
        <svg viewBox="0 0 80 40" className="absolute pointer-events-none" style={{ width: HOOP_W, left: `calc(50% - ${HOOP_W / 2}px)`, top: RIM_Y - 36 * (HOOP_W / 80) }} aria-hidden="true">
          <rect x="14" y="0" width="52" height="34" rx="3" fill="#fffdf8" stroke="#475569" strokeWidth="2" />
          <rect x="29" y="14" width="22" height="16" fill="none" stroke="#e85d38" strokeWidth="1.6" />
        </svg>

        {/* Sàn sân. */}
        <div className="absolute inset-x-0 bottom-0 h-1 bg-amber-900/15" />

        {/* Quỹ đạo dự kiến khi đang kéo ngắm: chấm đen nhỏ dần về cuối. */}
        {aim && (
          <svg className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden="true">
            {aim.map((dot, index) => (
              <circle key={index} cx={dot.x} cy={dot.y} r={Math.max(1.5, 3.5 - index * 0.08)} fill="#1f1b16" opacity={Math.max(0.25, 0.85 - index * 0.02)} />
            ))}
          </svg>
        )}

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
          className="absolute pointer-events-none"
          style={{ width: HOOP_W, left: `calc(50% - ${HOOP_W / 2}px)`, top: RIM_Y - 2 * (HOOP_W / 80) }}
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
