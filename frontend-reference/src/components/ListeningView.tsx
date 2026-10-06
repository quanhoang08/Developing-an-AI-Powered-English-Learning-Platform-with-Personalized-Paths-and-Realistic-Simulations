// Trang Listening & Movie Context. Cả 2 tab dùng backend FastAPI thật: Podcast/Dictation (PodcastPanel)
// và Movie Context nhánh TTS fallback (MovieContextPanel).
import React, { useState } from "react";
import { CountdownTimer } from "./CountdownTimer";
import { MovieContextPanel } from "./MovieContextPanel";
import { PodcastPanel } from "./PodcastPanel";
import { ToeicPanel } from "./ToeicPanel";
import {
  Headphones,
  Film,
  Search,
  Play,
  Pause,
  RotateCcw,
  RotateCw,
  Volume2,
  Sparkles,
  CheckCircle2,
  Languages,
  Mic,
  Bookmark,
  Check,
  Zap,
  Sliders,
  ChevronRight
} from "lucide-react";

export const ListeningView: React.FC = () => {
  const [subMode, setSubMode] = useState<"listening" | "movies">("listening");

  // Listening Audio Player State
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1.0);
  const [progress, setProgress] = useState(25);
  const [showTranslation, setShowTranslation] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState("Spanish");

  // Dictation Mode State
  const [userDictationInput, setUserDictationInput] = useState("");
  const [accuracyScore, setAccuracyScore] = useState<number | null>(null);
  const targetDictationSegment = "We need to iron out the contractual details before signing.";

  // So khớp text người học gõ với transcript mẫu (client-side, không gọi backend) để tính % đúng.
  const handleCheckDictation = () => {
    const cleanUser = userDictationInput.trim().toLowerCase().replace(/[^a-z0-9 ]/g, "");
    const cleanTarget = targetDictationSegment.trim().toLowerCase().replace(/[^a-z0-9 ]/g, "");

    if (cleanUser === cleanTarget) {
      setAccuracyScore(100);
    } else {
      const userWords = cleanUser.split(" ");
      const targetWords = cleanTarget.split(" ");
      let matched = 0;
      userWords.forEach((w) => {
        if (targetWords.includes(w)) matched++;
      });
      const score = Math.round((matched / targetWords.length) * 100);
      setAccuracyScore(Math.min(100, Math.max(20, score)));
    }
  };

  // Đọc to transcript bằng Web Speech API của trình duyệt (không gọi Azure TTS thật).
  const playTTS = (text: string) => {
    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-US";
      utterance.rate = playbackSpeed;
      window.speechSynthesis.speak(utterance);
    }
  };

  return (
    <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-8">
      {/* View Sub-Toggle Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-sm italic text-slate-500 mb-1">Train your ear</p>
          <h1 className="font-display text-4xl font-bold text-slate-900 flex items-center gap-3">
            <Headphones className="w-8 h-8 text-purple-500 -rotate-6" /> Listening & Movie Context Hub
          </h1>
          <p className="text-sm text-slate-500 mt-2 max-w-xl">
            Train native listening comprehension, dictation accuracy, and explore idiom usages in movie clips.
          </p>
        </div>

        <CountdownTimer skill="listening" />

        {/* Tab Toggle */}
        <div className="inline-flex p-1 bg-paper-deep rounded-full">
          <button
            onClick={() => setSubMode("listening")}
            className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer ${
              subMode === "listening"
                ? "bg-indigo-700 text-white shadow-[0_8px_16px_-8px_rgba(31,87,73,0.9)]"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Headphones className="w-3.5 h-3.5 inline mr-1.5" /> AI Podcast & Dictation
          </button>
          <button
            onClick={() => setSubMode("movies")}
            className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer ${
              subMode === "movies"
                ? "bg-indigo-700 text-white shadow-[0_8px_16px_-8px_rgba(31,87,73,0.9)]"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Film className="w-3.5 h-3.5 inline mr-1.5" /> Movie Context Finder
          </button>
        </div>
      </div>

      {subMode === "listening" ? (
        <PodcastPanel />
      ) : (
        <MovieContextPanel />
      )}

      <ToeicPanel />

    </div>
  );
};
