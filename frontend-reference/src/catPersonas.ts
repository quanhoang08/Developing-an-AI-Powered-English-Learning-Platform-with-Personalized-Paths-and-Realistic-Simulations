// 3 tính cách của mèo: mỗi loại có giọng điệu AI (gửi lên backend), ngoại hình 3D và giao diện sân khấu riêng.
import { useCallback, useEffect, useState } from "react";

export type CatPersona = "polite" | "rebel" | "buddy";

export interface PersonaDef {
  id: CatPersona;
  name: string;
  emoji: string;
  tagline: string;
  // Màu mèo 3D (hex): lông, vằn/mảng tối, bụng-mõm, trong tai, màu nhấn của phụ kiện, đèn viền.
  look: { fur: string; dark: string; cream: string; ear: string; accent: string; rim: string; tempo: number };
  // Class Tailwind của sân khấu (panel chứa mèo) và các thành phần trên đó.
  ui: { stage: string; text: string; muted: string; bubble: string; mic: string; chip: string; picked: string };
}

export const PERSONAS: Record<CatPersona, PersonaDef> = {
  polite: {
    id: "polite",
    name: "Sir Whiskers",
    emoji: "🎩",
    tagline: "Polite, patient, and always properly dressed.",
    look: { fur: "#f7b267", dark: "#e58f3a", cream: "#fff1dc", ear: "#ff9fb2", accent: "#4f46e5", rim: "#a5b4fc", tempo: 1 },
    ui: {
      stage: "bg-[radial-gradient(ellipse_at_50%_35%,var(--color-purple-100),var(--color-indigo-100)_70%)]",
      text: "text-slate-900",
      muted: "text-slate-600",
      bubble: "bg-[#fffdf8] text-slate-700",
      mic: "bg-indigo-700 hover:bg-indigo-800 shadow-[0_18px_28px_-12px_rgba(31,87,73,0.9)]",
      chip: "bg-white/70 text-indigo-900",
      picked: "ring-2 ring-indigo-500 bg-indigo-50",
    },
  },
  rebel: {
    id: "rebel",
    name: "Bad Kitty",
    emoji: "😈",
    tagline: "Sassy troublemaker. Teases you, still teaches you.",
    look: { fur: "#3b3b4f", dark: "#1d1d2b", cream: "#8d8da6", ear: "#ff2e93", accent: "#c6ff00", rim: "#ff2e93", tempo: 1.6 },
    ui: {
      stage: "bg-[radial-gradient(ellipse_at_50%_30%,#5b1f86,#160a26_75%)] shadow-[0_0_60px_-10px_rgba(255,46,147,0.55)]",
      text: "text-lime-300",
      muted: "text-fuchsia-200",
      bubble: "bg-[#1b1030] text-lime-200 ring-2 ring-fuchsia-500",
      mic: "bg-fuchsia-600 hover:bg-fuchsia-500 shadow-[0_0_28px_rgba(255,46,147,0.8)]",
      chip: "bg-black/60 text-lime-300",
      picked: "ring-2 ring-fuchsia-500 bg-fuchsia-50",
    },
  },
  buddy: {
    id: "buddy",
    name: "Chill Buddy",
    emoji: "🎧",
    tagline: "Relaxed best friend. Zero pressure, just vibes.",
    look: { fur: "#f4d2a4", dark: "#d98c4a", cream: "#fff6e8", ear: "#ffb4a2", accent: "#14b8a6", rim: "#fdba74", tempo: 0.7 },
    ui: {
      stage: "bg-[radial-gradient(ellipse_at_50%_35%,#fff1dc,#ffd9b8_55%,#ffb4a2)]",
      text: "text-amber-950",
      muted: "text-amber-900/80",
      bubble: "bg-white text-amber-950",
      mic: "bg-teal-600 hover:bg-teal-700 shadow-[0_18px_28px_-12px_rgba(13,148,136,0.9)]",
      chip: "bg-white/70 text-teal-900",
      picked: "ring-2 ring-teal-500 bg-teal-50",
    },
  },
};

export const PERSONA_ORDER: CatPersona[] = ["polite", "rebel", "buddy"];

const STORAGE_KEY = "chatPersona";
const CHANGE_EVENT = "lumina-persona";

const readPersona = (): CatPersona => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === "rebel" || saved === "buddy" ? saved : "polite";
  } catch {
    return "polite";
  }
};

// Một lựa chọn dùng chung cho Notebook Chat, Speaking và Live Call; đổi ở đâu cũng đồng bộ mọi nơi đang mở.
export const usePersona = (): [CatPersona, (next: CatPersona) => void] => {
  const [persona, setPersonaState] = useState<CatPersona>(readPersona);

  useEffect(() => {
    const sync = () => setPersonaState(readPersona());
    window.addEventListener(CHANGE_EVENT, sync);
    return () => window.removeEventListener(CHANGE_EVENT, sync);
  }, []);

  const setPersona = useCallback((next: CatPersona) => {
    setPersonaState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage không khả dụng: lựa chọn chỉ có hiệu lực trong phiên hiện tại.
    }
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);

  return [persona, setPersona];
};
