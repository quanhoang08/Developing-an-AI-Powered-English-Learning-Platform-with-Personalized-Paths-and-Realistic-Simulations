// Cổng vào duy nhất cho mèo 3D: tải lười Cat3D (three.js khá nặng) và lùi về mèo SVG 2D khi máy không có
// WebGL hoặc khi khởi tạo 3D lỗi, để trang vẫn dùng được.
import React, { Suspense } from "react";
import { CatMascot, CatMood } from "./CatMascot";
import { CatPersona, PERSONAS } from "../catPersonas";

const Cat3D = React.lazy(() => import("./Cat3D"));

interface CatStageProps {
  mouthOpen: number;
  mood: CatMood;
  persona: CatPersona;
  // Bad Kitty cau mày khi người học sai (chỉ ảnh hưởng mèo 3D).
  frown?: boolean;
  variant?: "stage" | "hero";
  className?: string;
}

const hasWebGL = (() => {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
})();

class Boundary extends React.Component<{ fallback: React.ReactNode; children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

export const CatStage: React.FC<CatStageProps> = ({ mouthOpen, mood, persona, frown, variant, className }) => {
  const flat = <CatMascot mouthOpen={mouthOpen} mood={mood} className={className} />;
  if (!hasWebGL) return flat;
  return (
    <Boundary fallback={flat}>
      <Suspense fallback={flat}>
        <Cat3D mouthOpen={mouthOpen} mood={mood} persona={persona} frown={frown} variant={variant} className={className} />
      </Suspense>
    </Boundary>
  );
};

export const PersonaChip: React.FC<{ persona: CatPersona }> = ({ persona }) => (
  <span className={`absolute top-4 left-4 z-10 px-3 py-1 rounded-full text-xs font-bold backdrop-blur ${PERSONAS[persona].ui.chip}`}>
    {PERSONAS[persona].emoji} {PERSONAS[persona].name}
  </span>
);

// Nền trang trí sau mèo: hai quầng sáng mờ đúng màu tính cách + lớp chấm nhỏ (đặt trong panel `relative overflow-hidden`).
export const StageBackdrop: React.FC<{ persona: CatPersona }> = ({ persona }) => {
  const ui = PERSONAS[persona].ui;
  return (
    <div aria-hidden="true" className="absolute inset-0 pointer-events-none">
      <div className={`absolute -top-16 -left-10 w-64 h-64 rounded-full blur-3xl ${ui.orbA}`} />
      <div className={`absolute -bottom-20 -right-10 w-72 h-72 rounded-full blur-3xl ${ui.orbB}`} />
      <div
        className="absolute inset-0 opacity-[0.07]"
        style={{ backgroundImage: "radial-gradient(currentColor 1px, transparent 1px)", backgroundSize: "20px 20px" }}
      />
    </div>
  );
};
