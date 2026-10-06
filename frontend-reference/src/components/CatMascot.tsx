// Mèo mascot đứng bằng 2 chân (SVG). `mouthOpen` (0..1) điều khiển độ mở miệng để nhóp nhép
// theo giọng nói: SpeakingView đo biên độ audio phản hồi rồi truyền vào đây mỗi frame.
import React from "react";

export type CatMood = "idle" | "listening" | "thinking" | "speaking";

interface CatMascotProps {
  mouthOpen: number;
  mood: CatMood;
  className?: string;
}

const FUR = "#f7b267";
const FUR_DARK = "#e58f3a";
const CREAM = "#fff1dc";
const PINK = "#ff9fb2";
const INK = "#3b2a2a";

export const CatMascot: React.FC<CatMascotProps> = ({ mouthOpen, mood, className }) => {
  const open = Math.max(0, Math.min(1, mouthOpen));
  const mouthRy = 1.5 + open * 15;
  const mouthRx = 11 + open * 5;
  const isSpeaking = mood === "speaking";
  const eyeScale = mood === "listening" ? 1.12 : 1;

  return (
    <svg
      viewBox="0 0 300 400"
      className={`cat-mascot cat-${mood} ${className ?? ""}`}
      role="img"
      aria-label={isSpeaking ? "Cat mascot speaking" : "Cat mascot"}
    >
      <style>{`
        @keyframes cat-blink { 0%, 92%, 100% { transform: scaleY(1); } 96% { transform: scaleY(0.08); } }
        @keyframes cat-tail { 0%, 100% { transform: rotate(-8deg); } 50% { transform: rotate(10deg); } }
        @keyframes cat-bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-5px); } }
        @keyframes cat-breathe { 0%, 100% { transform: scale(1, 1); } 50% { transform: scale(1.025, 1.04); } }
        @keyframes cat-sway { 0%, 100% { transform: rotate(-2deg); } 50% { transform: rotate(2deg); } }
        @keyframes cat-think { 0%, 100% { transform: rotate(-5deg); } 50% { transform: rotate(5deg); } }
        @keyframes cat-listen { 0%, 100% { transform: rotate(7deg) translateY(2px); } 50% { transform: rotate(4deg) translateY(0); } }
        @keyframes cat-nod { 0%, 100% { transform: rotate(0) translateY(0); } 25% { transform: rotate(-3deg) translateY(2px); } 75% { transform: rotate(3deg) translateY(-1px); } }
        @keyframes cat-ear-l { 0%, 86%, 100% { transform: rotate(0); } 90% { transform: rotate(-9deg); } 94% { transform: rotate(3deg); } }
        @keyframes cat-ear-r { 0%, 60%, 70%, 100% { transform: rotate(0); } 64% { transform: rotate(9deg); } 67% { transform: rotate(-3deg); } }
        @keyframes cat-ear-perk { 0%, 100% { transform: rotate(0) scaleY(1); } 50% { transform: rotate(-4deg) scaleY(1.08); } }
        @keyframes cat-wave-l { 0%, 100% { transform: rotate(0); } 50% { transform: rotate(-24deg); } }
        @keyframes cat-wave-r { 0%, 100% { transform: rotate(0); } 50% { transform: rotate(24deg); } }
        @keyframes cat-look { 0%, 40% { transform: translate(0, 0); } 50%, 80% { transform: translate(5px, 1px); } 90%, 100% { transform: translate(-4px, 0); } }
        @keyframes cat-dot { 0%, 20% { opacity: 0; transform: scale(0.4); } 40%, 100% { opacity: 1; transform: scale(1); } }
        @keyframes cat-float { 0% { opacity: 0; transform: translateY(14px) scale(0.5); } 30% { opacity: 1; } 100% { opacity: 0; transform: translateY(-34px) scale(1.1); } }
        @keyframes cat-ring { 0% { opacity: 0.55; transform: scale(0.7); } 100% { opacity: 0; transform: scale(1.35); } }
        @keyframes cat-shadow { 0%, 100% { transform: scaleX(1); } 50% { transform: scaleX(0.92); } }
        @keyframes cat-cheek { 0%, 100% { opacity: 0.75; } 50% { opacity: 1; } }
        .cat-eye { transform-box: fill-box; transform-origin: center; animation: cat-blink 4.5s infinite; }
        .cat-look { animation: cat-look 9s ease-in-out infinite; }
        .cat-tail { transform-box: fill-box; transform-origin: 0% 100%; animation: cat-tail 3s ease-in-out infinite; }
        .cat-body { animation: cat-bob 3s ease-in-out infinite; }
        .cat-torso { transform-box: fill-box; transform-origin: 50% 100%; animation: cat-breathe 3s ease-in-out infinite; }
        .cat-head { transform-box: fill-box; transform-origin: 50% 100%; animation: cat-sway 5s ease-in-out infinite; }
        .cat-ear-l { transform-box: fill-box; transform-origin: 100% 100%; animation: cat-ear-l 6s infinite; }
        .cat-ear-r { transform-box: fill-box; transform-origin: 0% 100%; animation: cat-ear-r 7s infinite; }
        .cat-arm-l { transform-box: fill-box; transform-origin: 100% 0%; }
        .cat-arm-r { transform-box: fill-box; transform-origin: 0% 0%; }
        .cat-shadow { transform-box: fill-box; transform-origin: center; animation: cat-shadow 3s ease-in-out infinite; }
        .cat-cheek { animation: cat-cheek 3s ease-in-out infinite; }
        .cat-ring, .cat-note, .cat-dot { transform-box: fill-box; transform-origin: center; opacity: 0; }
        .cat-thinking .cat-head { animation: cat-think 1.6s ease-in-out infinite; }
        .cat-thinking .cat-look { animation: none; transform: translate(7px, -7px); }
        .cat-thinking .cat-dot { animation: cat-dot 1.5s infinite; }
        .cat-listening .cat-head { animation: cat-listen 2.4s ease-in-out infinite; }
        .cat-listening .cat-ear-l, .cat-listening .cat-ear-r { animation: cat-ear-perk 1.2s ease-in-out infinite; }
        .cat-listening .cat-look { animation: none; }
        .cat-listening .cat-ring { animation: cat-ring 1.6s ease-out infinite; }
        .cat-speaking .cat-body, .cat-speaking .cat-torso { animation-duration: 0.5s; }
        .cat-speaking .cat-head { animation: cat-nod 0.9s ease-in-out infinite; }
        .cat-speaking .cat-tail { animation-duration: 0.8s; }
        .cat-speaking .cat-arm-l { animation: cat-wave-l 0.8s ease-in-out infinite; }
        .cat-speaking .cat-arm-r { animation: cat-wave-r 0.8s ease-in-out 0.4s infinite; }
        .cat-speaking .cat-look { animation: none; }
        .cat-speaking .cat-note { animation: cat-float 2s ease-out infinite; }
        .cat-speaking .cat-ring { animation: cat-ring 1.2s ease-out infinite; }
        @media (prefers-reduced-motion: reduce) { .cat-mascot * { animation: none !important; } }
      `}</style>

      {/* Bóng dưới chân */}
      <ellipse className="cat-shadow" cx="150" cy="384" rx="78" ry="10" fill="#000" opacity="0.08" />

      {/* Sóng âm lan ra quanh mèo khi nghe / nói */}
      {[0, 0.6].map((d) => (
        <circle key={d} className="cat-ring" cx="150" cy="200" r="150" fill="none" stroke={isSpeaking ? FUR : "#818cf8"} strokeWidth="3" style={{ animationDelay: `${d}s` }} />
      ))}

      <g className="cat-body">
        {/* Đuôi */}
        <path
          className="cat-tail"
          d="M205 300 C265 290 285 235 262 200 C255 190 240 196 246 208 C258 232 246 268 205 274 Z"
          fill={FUR}
          stroke={FUR_DARK}
          strokeWidth="3"
        />
        <path d="M252 214 L262 208 M256 232 L268 228" stroke={FUR_DARK} strokeWidth="5" strokeLinecap="round" />

        {/* Hai chân (đứng thẳng) */}
        <rect x="112" y="322" width="30" height="48" rx="14" fill={FUR} stroke={FUR_DARK} strokeWidth="3" />
        <rect x="158" y="322" width="30" height="48" rx="14" fill={FUR} stroke={FUR_DARK} strokeWidth="3" />
        <ellipse cx="121" cy="372" rx="24" ry="12" fill={CREAM} stroke={FUR_DARK} strokeWidth="3" />
        <ellipse cx="179" cy="372" rx="24" ry="12" fill={CREAM} stroke={FUR_DARK} strokeWidth="3" />
        <path d="M111 374 v-4 M121 376 v-5 M131 374 v-4 M169 374 v-4 M179 376 v-5 M189 374 v-4" stroke={PINK} strokeWidth="3" strokeLinecap="round" />

        {/* Thân */}
        <g className="cat-torso">
          <ellipse cx="150" cy="272" rx="66" ry="72" fill={FUR} stroke={FUR_DARK} strokeWidth="3" />
          <ellipse cx="150" cy="284" rx="40" ry="52" fill={CREAM} />
          <path d="M98 250 h14 M96 270 h14 M188 250 h14 M190 270 h14" stroke={FUR_DARK} strokeWidth="5" strokeLinecap="round" />
        </g>

        {/* Hai tay */}
        <g className="cat-arm-l">
        <path d="M92 236 C70 252 68 286 82 300 C92 306 100 296 98 286 C96 270 102 256 108 246 Z" fill={FUR} stroke={FUR_DARK} strokeWidth="3" />
        <circle cx="84" cy="299" r="9" fill={CREAM} stroke={FUR_DARK} strokeWidth="2.5" />
        </g>
        <g className="cat-arm-r">
        <path d="M208 236 C230 252 232 286 218 300 C208 306 200 296 202 286 C204 270 198 256 192 246 Z" fill={FUR} stroke={FUR_DARK} strokeWidth="3" />
        <circle cx="216" cy="299" r="9" fill={CREAM} stroke={FUR_DARK} strokeWidth="2.5" />
        </g>
      </g>

      <g className="cat-body">
        <g className="cat-head">
          {/* Tai */}
          <g className="cat-ear-l">
            <path d="M70 92 L82 22 L138 66 Z" fill={FUR} stroke={FUR_DARK} strokeWidth="3" strokeLinejoin="round" />
            <path d="M84 78 L90 42 L120 66 Z" fill={PINK} />
          </g>
          <g className="cat-ear-r">
            <path d="M230 92 L218 22 L162 66 Z" fill={FUR} stroke={FUR_DARK} strokeWidth="3" strokeLinejoin="round" />
            <path d="M216 78 L210 42 L180 66 Z" fill={PINK} />
          </g>

          {/* Đầu */}
          <ellipse cx="150" cy="130" rx="98" ry="84" fill={FUR} stroke={FUR_DARK} strokeWidth="3" />
          <path d="M150 52 v22 M132 56 l4 18 M168 56 l-4 18" stroke={FUR_DARK} strokeWidth="6" strokeLinecap="round" />
          <ellipse cx="150" cy="158" rx="52" ry="36" fill={CREAM} />

          {/* Mắt */}
          <g style={{ transform: `scale(${eyeScale})`, transformOrigin: "150px 128px", transition: "transform 0.3s" }}>
          <g className="cat-look">
          <g className="cat-eye">
            <ellipse cx="108" cy="126" rx="17" ry="21" fill={INK} />
            <ellipse cx="192" cy="126" rx="17" ry="21" fill={INK} />
            <circle cx="114" cy="118" r="7" fill="#fff" />
            <circle cx="198" cy="118" r="7" fill="#fff" />
            <circle cx="103" cy="134" r="3.5" fill="#fff" />
            <circle cx="187" cy="134" r="3.5" fill="#fff" />
          </g>
          </g>
          </g>

          {/* Má hồng */}
          <ellipse className="cat-cheek" cx="80" cy="156" rx="15" ry="9" fill={PINK} />
          <ellipse className="cat-cheek" cx="220" cy="156" rx="15" ry="9" fill={PINK} />

          {/* Mũi */}
          <path d="M141 146 Q150 140 159 146 Q155 156 150 158 Q145 156 141 146 Z" fill="#ff7a93" />

          {/* Miệng: khép (nụ cười chữ w) hoặc mở theo mouthOpen */}
          <g style={{ opacity: open > 0.06 ? 0 : 1 }}>
            <path d="M150 158 Q150 168 138 168 M150 158 Q150 168 162 168" stroke={INK} strokeWidth="3" fill="none" strokeLinecap="round" />
          </g>
          <g style={{ opacity: open > 0.06 ? 1 : 0 }}>
            <ellipse cx="150" cy={166 + mouthRy * 0.6} rx={mouthRx} ry={mouthRy} fill="#7a2e3a" stroke={INK} strokeWidth="2.5" />
            {open > 0.3 && (
              <ellipse cx="150" cy={166 + mouthRy * 1.05} rx={mouthRx * 0.6} ry={mouthRy * 0.45} fill="#ff8fa3" />
            )}
          </g>

          {/* Ria */}
          <path d="M96 160 L52 150 M96 168 L50 172 M98 176 L58 192" stroke={INK} strokeWidth="2.5" strokeLinecap="round" />
          <path d="M204 160 L248 150 M204 168 L250 172 M202 176 L242 192" stroke={INK} strokeWidth="2.5" strokeLinecap="round" />
        </g>
      </g>

      {/* Đang nghĩ: 3 chấm lần lượt hiện */}
      {[[250, 70, 5], [266, 48, 7], [284, 22, 9]].map(([x, y, r], i) => (
        <circle key={i} className="cat-dot" cx={x} cy={y} r={r} fill="#a5b4fc" style={{ animationDelay: `${i * 0.25}s` }} />
      ))}

      {/* Đang nói: nốt nhạc bay lên */}
      {[[26, 120, "♪", 0], [272, 100, "♫", 0.7], [40, 60, "♫", 1.3]].map(([x, y, ch, d]) => (
        <text key={String(x)} className="cat-note" x={x as number} y={y as number} fontSize="26" fill={FUR_DARK} style={{ animationDelay: `${d}s` }}>{ch}</text>
      ))}
    </svg>
  );
};
