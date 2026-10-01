// Modal flashcard ôn từ SM-2. Dùng dữ liệu due thật từ backend khi đã đăng nhập (listDueVocabulary/
// reviewVocabulary), fallback về SAMPLE_FLASHCARDS demo khi chưa đăng nhập hoặc chưa có từ đến hạn.
import React, { useEffect, useState } from "react";
import { FlashcardItem } from "../types";
import { getAccessToken, importVocabularyFromErrors, listDueVocabulary, reviewVocabulary } from "../api";
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
  const [backendCards, setBackendCards] = useState<FlashcardItem[]>([]);

  const [importMessage, setImportMessage] = useState("");
  const [importing, setImporting] = useState(false);

  const loadDue = () =>
    listDueVocabulary()
      .then((items) => {
        setBackendCards(items.map((item) => ({
          id: item.id,
          front: item.term,
          back: item.definition || "No definition yet",
          type: "Vocabulary",
          context: item.example_sentence || "Saved from your reading materials.",
        })));
        setCurrentIndex(0);
        setReviewedCount(0);
      })
      .catch(() => setBackendCards([]));

  useEffect(() => {
    // Khi đã login, ưu tiên dữ liệu due thật từ SM-2 backend.
    if (!isOpen || !getAccessToken()) return;
    void loadDue();
  }, [isOpen]);

  const handleImport = async () => {
    setImporting(true);
    setImportMessage("");
    try {
      const added = await importVocabularyFromErrors();
      setImportMessage(
        added.length
          ? `Added ${added.length} word${added.length > 1 ? "s" : ""} you missed in Dictation.`
          : "No new missed words to add.",
      );
      if (added.length) await loadDue();
    } catch (error) {
      setImportMessage(error instanceof Error ? error.message : "Could not add words.");
    } finally {
      setImporting(false);
    }
  };

  if (!isOpen) return null;

  const cards = backendCards.length ? backendCards : SAMPLE_FLASHCARDS;
  const currentCard = cards[currentIndex % cards.length];

  const handleNext = async (quality: number) => {
    // Lưu quality vào SM-2 khi card đến từ backend.
    if (backendCards.length && getAccessToken()) {
      await reviewVocabulary(currentCard.id, quality);
    }
    setIsFlipped(false);
    setReviewedCount((prev) => prev + 1);
    setCurrentIndex((prev) => prev + 1);
  };

  // Đọc to mặt trước của thẻ bằng Web Speech API trình duyệt.
  const playTTS = (text: string) => {
    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-US";
      window.speechSynthesis.speak(utterance);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-950/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#fffdf8] rounded-[2rem] max-w-xl w-full shadow-[0_40px_80px_-30px_rgba(32,29,24,0.6)] overflow-hidden animate-rise">
        {/* Modal Header */}
        <div className="relative overflow-hidden p-6 bg-indigo-900 text-white flex items-center justify-between">
          <div className="absolute -right-8 -top-10 w-40 h-40 rounded-full bg-purple-500/30 blur-2xl pointer-events-none" aria-hidden="true" />
          <div className="relative flex items-center gap-3">
            <Zap className="w-6 h-6 fill-amber-300 text-amber-300" />
            <div>
              <h3 className="font-display font-bold text-xl leading-tight">Spaced repetition review</h3>
              <p className="text-xs text-indigo-200">
                Card <span className="num">{currentIndex + 1}</span> of <span className="num">{cards.length}</span> · <span className="num">{reviewedCount}</span> reviewed today
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close review"
            className="relative p-2 rounded-full hover:bg-white/15 text-white transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Card Body Container */}
        <div className="p-8">
          <div
            onClick={() => setIsFlipped(!isFlipped)}
            className={`min-h-[280px] rounded-3xl p-8 transition-all duration-300 cursor-pointer flex flex-col justify-between select-none relative group ${
              isFlipped
                ? "bg-indigo-50 shadow-[0_24px_40px_-24px_rgba(31,87,73,0.6)] rotate-0"
                : "bg-white shadow-[0_18px_36px_-22px_rgba(95,70,30,0.5)] -rotate-[0.8deg] hover:rotate-0 hover:-translate-y-1"
            }`}
          >
            {/* Top Badge */}
            <div className="flex items-center justify-between">
              <span className="tag bg-paper-deep text-slate-600">
                {currentCard.type}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  playTTS(currentCard.front);
                }}
                className="p-2.5 rounded-full bg-paper-deep hover:bg-indigo-100 text-indigo-700 transition-colors active:scale-90"
                title="Listen to Pronunciation"
                aria-label="Listen to pronunciation"
              >
                <Volume2 className="w-4 h-4" />
              </button>
            </div>

            {/* Front vs Back Content */}
            <div className="text-center py-6">
              {!isFlipped ? (
                <div>
                  <h2 className="font-display text-5xl font-bold text-slate-900 mb-4">
                    {currentCard.front}
                  </h2>
                  <p className="text-sm text-slate-400 italic flex items-center justify-center gap-1.5">
                    <RotateCw className="w-3.5 h-3.5" /> Click the card to reveal the answer
                  </p>
                </div>
              ) : (
                <div className="animate-rise">
                  <p className="font-serif text-xl font-semibold text-indigo-950 mb-4 leading-relaxed">
                    {currentCard.back}
                  </p>
                  <div className="p-4 bg-[#fffdf8] rounded-2xl text-sm text-slate-600 italic font-serif">
                    "{currentCard.context}"
                  </div>
                </div>
              )}
            </div>

            <div className="text-center text-xs text-slate-400 italic">
              Scheduled with the SuperMemo-2 algorithm
            </div>
          </div>

          {getAccessToken() && (
            <div className="mt-4 flex items-center justify-between gap-3 text-xs text-slate-500">
              <span role="status">{importMessage}</span>
              <button
                onClick={() => void handleImport()}
                disabled={importing}
                className="px-3 py-1.5 rounded-full bg-paper-deep hover:bg-indigo-100 text-indigo-800 font-semibold disabled:opacity-50 cursor-pointer"
              >
                {importing ? "Adding…" : "Add words I missed in Dictation"}
              </button>
            </div>
          )}

          {/* Answer Controls */}
          {isFlipped ? (
            <div className="mt-6 grid grid-cols-4 gap-2.5 animate-rise">
              <button
                onClick={() => void handleNext(0)}
                className="py-3 px-2 bg-rose-100 hover:bg-rose-200 text-rose-800 rounded-2xl text-sm font-bold text-center transition-all active:scale-95 cursor-pointer"
              >
                Again
                <span className="block text-[10px] font-normal text-rose-500">1 min</span>
              </button>
              <button
                onClick={() => void handleNext(2)}
                className="py-3 px-2 bg-amber-100 hover:bg-amber-200 text-amber-900 rounded-2xl text-sm font-bold text-center transition-all active:scale-95 cursor-pointer"
              >
                Hard
                <span className="block text-[10px] font-normal text-amber-500">2 days</span>
              </button>
              <button
                onClick={() => void handleNext(4)}
                className="py-3 px-2 bg-emerald-100 hover:bg-emerald-200 text-emerald-900 rounded-2xl text-sm font-bold text-center transition-all active:scale-95 cursor-pointer"
              >
                Good
                <span className="block text-[10px] font-normal text-emerald-500">5 days</span>
              </button>
              <button
                onClick={() => void handleNext(5)}
                className="py-3 px-2 bg-indigo-700 hover:bg-indigo-800 text-white rounded-2xl text-sm font-bold text-center shadow-[0_12px_20px_-12px_rgba(31,87,73,0.9)] transition-all active:scale-95 cursor-pointer"
              >
                Easy
                <span className="block text-[10px] font-normal text-indigo-200">12 days</span>
              </button>
            </div>
          ) : (
            <div className="mt-6">
              <button
                onClick={() => setIsFlipped(true)}
                className="w-full py-3.5 bg-slate-900 hover:bg-slate-800 text-white rounded-2xl font-bold text-sm flex items-center justify-center gap-2 transition-all active:scale-[0.98] cursor-pointer"
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
