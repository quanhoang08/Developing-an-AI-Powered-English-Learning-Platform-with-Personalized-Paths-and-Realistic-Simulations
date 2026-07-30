import React, { useState } from "react";
import { FlashcardItem } from "../types";
import { X, RotateCw, CheckCircle2, Zap, ArrowRight, BookOpen, Volume2 } from "lucide-react";

interface SpacedRepetitionModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const SAMPLE_FLASHCARDS: FlashcardItem[] = [
  {
    id: "1",
    front: "Pervasive",
    back: "Spreading or existing widely throughout an area or group of people.",
    type: "Vocabulary",
    context: "The influence of smartphones is pervasive in modern culture."
  },
  {
    id: "2",
    front: "Piece of cake",
    back: "Something that is very easy to do.",
    type: "Phrasal Verb",
    context: "Pitching to investors is a piece of cake for her."
  },
  {
    id: "3",
    front: "Third Conditional Grammar",
    back: "If + Past Perfect, ... Would Have + Past Participle",
    type: "Grammar",
    context: "If I had studied harder, I would have passed the exam."
  },
  {
    id: "4",
    front: "Atrophy",
    back: "Gradually decline in effectiveness or vigor due to underuse.",
    type: "Vocabulary",
    context: "Without practice, your conversational skills can atrophy."
  },
  {
    id: "5",
    front: "Mitigate",
    back: "Make something less severe, serious, or painful.",
    type: "Vocabulary",
    context: "Real-time navigation apps help mitigate traffic congestion."
  }
];

export const SpacedRepetitionModal: React.FC<SpacedRepetitionModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [reviewedCount, setReviewedCount] = useState(0);

  if (!isOpen) return null;

  const currentCard = SAMPLE_FLASHCARDS[currentIndex % SAMPLE_FLASHCARDS.length];

  const handleNext = () => {
    setIsFlipped(false);
    setReviewedCount((prev) => prev + 1);
    setCurrentIndex((prev) => prev + 1);
  };

  const playTTS = (text: string) => {
    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-US";
      window.speechSynthesis.speak(utterance);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl max-w-xl w-full shadow-2xl overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-200">
        {/* Modal Header */}
        <div className="p-5 bg-gradient-to-r from-amber-500 to-orange-500 text-white flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 fill-white" />
            <div>
              <h3 className="font-bold text-base leading-tight">Spaced Repetition Review</h3>
              <p className="text-xs text-amber-100">Card {currentIndex + 1} of {SAMPLE_FLASHCARDS.length} ({reviewedCount} reviewed today)</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-white/20 text-white transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Card Body Container */}
        <div className="p-8">
          <div
            onClick={() => setIsFlipped(!isFlipped)}
            className={`min-h-[260px] rounded-2xl p-8 border-2 transition-all duration-300 cursor-pointer flex flex-col justify-between select-none relative group ${
              isFlipped
                ? "bg-indigo-50/70 border-indigo-300 shadow-lg shadow-indigo-100"
                : "bg-white border-slate-200 hover:border-amber-400 hover:shadow-md"
            }`}
          >
            {/* Top Badge */}
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700">
                {currentCard.type}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  playTTS(currentCard.front);
                }}
                className="p-2 rounded-full bg-white hover:bg-indigo-100 text-indigo-600 transition-colors shadow-xs"
                title="Listen to Pronunciation"
              >
                <Volume2 className="w-4 h-4" />
              </button>
            </div>

            {/* Front vs Back Content */}
            <div className="text-center py-6">
              {!isFlipped ? (
                <div>
                  <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight mb-3">
                    {currentCard.front}
                  </h2>
                  <p className="text-xs text-slate-400 font-medium italic flex items-center justify-center gap-1">
                    <RotateCw className="w-3.5 h-3.5" /> Click card to reveal answer
                  </p>
                </div>
              ) : (
                <div className="animate-in fade-in duration-200">
                  <p className="text-lg font-bold text-indigo-950 mb-4 leading-relaxed">
                    {currentCard.back}
                  </p>
                  <div className="p-3 bg-white/80 rounded-xl border border-indigo-100 text-xs text-slate-600 italic">
                    "{currentCard.context}"
                  </div>
                </div>
              )}
            </div>

            <div className="text-center text-[11px] font-semibold text-slate-400">
              Space Repetition Algorithm: SuperMemo-2
            </div>
          </div>

          {/* Answer Controls */}
          {isFlipped ? (
            <div className="mt-6 grid grid-cols-4 gap-2.5 animate-in fade-in duration-200">
              <button
                onClick={handleNext}
                className="py-2.5 px-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-xl text-xs font-bold text-center transition-colors cursor-pointer"
              >
                Again
                <span className="block text-[10px] font-normal text-rose-500">1 min</span>
              </button>
              <button
                onClick={handleNext}
                className="py-2.5 px-2 bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 rounded-xl text-xs font-bold text-center transition-colors cursor-pointer"
              >
                Hard
                <span className="block text-[10px] font-normal text-amber-500">2 days</span>
              </button>
              <button
                onClick={handleNext}
                className="py-2.5 px-2 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-xl text-xs font-bold text-center transition-colors cursor-pointer"
              >
                Good
                <span className="block text-[10px] font-normal text-emerald-500">5 days</span>
              </button>
              <button
                onClick={handleNext}
                className="py-2.5 px-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold text-center shadow-md shadow-indigo-200 transition-all cursor-pointer"
              >
                Easy
                <span className="block text-[10px] font-normal text-indigo-200">12 days</span>
              </button>
            </div>
          ) : (
            <div className="mt-6">
              <button
                onClick={() => setIsFlipped(true)}
                className="w-full py-3 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-bold text-xs shadow-md flex items-center justify-center gap-2 transition-all cursor-pointer"
              >
                Show Answer <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
