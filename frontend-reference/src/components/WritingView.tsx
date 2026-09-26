// Trang Writing Lab — nối với API Writing thật ở backend (/api/writing/submissions, /submit).
// State khởi tạo (essayTitle/essayText/insights mẫu) vẫn là placeholder demo cho tới khi người
// học bấm "Analyze & Correct with AI" lần đầu.
import React, { useState } from "react";
import { WritingInsight } from "../types";
import { createWritingSubmission, submitWritingEssay } from "../api";
import { WordHoverLookup } from "./WordHoverLookup";
import { RearrangePanel } from "./RearrangePanel";
import {
  PenTool,
  Sparkles,
  Bold,
  Italic,
  Underline,
  List,
  ListOrdered,
  CheckCircle2,
  AlertTriangle,
  Award,
  Zap,
  ArrowRight,
  RefreshCw,
  Bookmark
} from "lucide-react";

const MIN_SUBMISSION_WORDS = 30;

export const WritingView: React.FC = () => {
  const [essayTitle, setEssayTitle] = useState("Impact of Generative AI on Modern Education");
  const [essayText, setEssayText] = useState(
    `Generative artificial intelligence is rapidly changing how students learn and teachers instruct. Some educators fear that AI tools will affect student critical thinking skills negatively. However, if integrated properly, AI can serve as a good tutor that provides personalized feedback and accelerates language acquisition.

In addition, AI tools can automate administrative tasks for teachers, allowing them to focus more on direct human interaction and mentorship.`
  );

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  // Bài luận sau khi áp dụng các sửa lỗi của AI; null cho tới khi chấm xong lần đầu.
  // Hover tra nghĩa chỉ bật ở vùng này (không bật ở ô soạn thảo).
  const [reviewedText, setReviewedText] = useState<string | null>(null);
  const [overallScore, setOverallScore] = useState(82);
  const [cefrLevel, setCefrLevel] = useState("B2 Upper");
  const [ieltsScore, setIeltsScore] = useState("6.5 IELTS");

  const [insights, setInsights] = useState<WritingInsight[]>([
    {
      type: "grammar",
      title: "Grammar & Word Choice",
      originalText: "affect",
      suggestedText: "effect",
      description: 'Consider whether "affect" or "effect" is the intended noun in this sentence.',
      rule: '"Affect" is typically a verb, while "effect" is a noun. In "will have an affect", use "effect".'
    },
    {
      type: "vocabulary",
      title: "Academic Vocabulary Enhancement",
      originalText: "good",
      description: 'Replace generic adjective "good" with a more formal academic alternative.',
      synonyms: ["beneficial", "advantageous", "valuable"]
    },
    {
      type: "style",
      title: "Flow & Structural Style",
      description: "Sentence flow is clear, but consider adding a concluding sentence summarizing long-term impact.",
      suggestion: "Ultimately, human guidance paired with AI capabilities creates an optimal learning ecosystem."
    }
  ]);

  // Gọi FastAPI Writing thật: tạo 1 submission free_topic (đề = essayTitle) rồi nộp bài ngay
  // để chấm điểm — mỗi lần bấm "Analyze" là 1 submission mới (không sửa lại bài cũ).
  const handleAnalyzeWriting = async () => {
    const wordCountNow = essayText.trim().split(/\s+/).filter(Boolean).length;
    if (wordCountNow < MIN_SUBMISSION_WORDS) {
      setAnalyzeError(`Essay must be at least ${MIN_SUBMISSION_WORDS} words (currently ${wordCountNow}).`);
      return;
    }
    setAnalyzeError(null);
    setIsAnalyzing(true);
    try {
      const submission = await createWritingSubmission(essayTitle || "Untitled Essay");
      const result = await submitWritingEssay(submission.submission_id, essayText);
      setOverallScore(Math.round(result.score));
      setCefrLevel(result.cefr_level);
      setIeltsScore(`${result.ielts_band} IELTS`);
      setReviewedText(
        result.insights.reduce(
          (text, insight) =>
            insight.original_text && insight.suggested_text ? text.replace(insight.original_text, insight.suggested_text) : text,
          essayText,
        ),
      );
      setInsights(
        result.insights.map((insight) => ({
          type: insight.insight_type as WritingInsight["type"],
          title: insight.title,
          description: insight.description,
          originalText: insight.original_text ?? undefined,
          suggestedText: insight.suggested_text ?? undefined,
        })),
      );
    } catch (error) {
      const raw = error instanceof Error ? error.message : "Failed to analyze essay";
      setAnalyzeError(raw);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Thay 1 từ trong bài luận bằng synonym gợi ý khi người học bấm chọn.
  const applySynonym = (targetWord: string, replacement: string) => {
    const updated = essayText.replace(new RegExp(`\\b${targetWord}\\b`, "i"), replacement);
    setEssayText(updated);
  };

  const wordCount = essayText.trim().split(/\s+/).filter(Boolean).length;

  return (
    <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-8">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-sm italic text-slate-500 mb-1">Write, get corrected, get better</p>
          <h1 className="font-display text-4xl font-bold text-slate-900 flex items-center gap-3">
            <PenTool className="w-8 h-8 text-purple-500 -rotate-12" /> Writing & Correction Lab
          </h1>
          <p className="text-sm text-slate-500 mt-2 max-w-xl">
            Compose essays and get instant AI scoring, grammar fixes, and academic vocabulary upgrades.
          </p>
        </div>

        <button
          onClick={handleAnalyzeWriting}
          disabled={isAnalyzing}
          className="px-6 py-3 bg-indigo-700 hover:bg-indigo-800 text-white font-bold text-sm rounded-2xl shadow-[0_16px_26px_-14px_rgba(31,87,73,0.9)] flex items-center justify-center gap-2 transition-all cursor-pointer hover:-translate-y-0.5 active:scale-95 disabled:opacity-50"
        >
          {isAnalyzing ? <Sparkles className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4 text-amber-300" />}
          {isAnalyzing ? "Analyzing Essay..." : "Analyze & Correct with AI"}
        </button>
      </div>

      {analyzeError && (
        <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-xl px-4 py-3 border-l-4 border-red-400">
          {analyzeError}
        </p>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Writing Editor (7 Cols) */}
        <div className="surface lg:col-span-7 p-7 md:p-9 flex flex-col justify-between min-h-[560px]">
          <div className="space-y-5">
            {/* Title Input */}
            <input
              type="text"
              value={essayTitle}
              onChange={(e) => setEssayTitle(e.target.value)}
              placeholder="Essay title..."
              className="w-full font-display text-3xl font-bold text-slate-900 placeholder-slate-300 bg-transparent border-b-2 border-dashed border-slate-200 pb-3 focus:outline-none focus:border-indigo-500 transition-colors"
            />

            {/* Rich Text Toolbar */}
            <div className="flex items-center gap-1 p-1.5 bg-paper-deep/80 rounded-full w-fit text-slate-600">
              <button className="p-1.5 hover:bg-white rounded-lg transition-colors cursor-pointer" title="Bold">
                <Bold className="w-4 h-4" />
              </button>
              <button className="p-1.5 hover:bg-white rounded-lg transition-colors cursor-pointer" title="Italic">
                <Italic className="w-4 h-4" />
              </button>
              <button className="p-1.5 hover:bg-white rounded-lg transition-colors cursor-pointer" title="Underline">
                <Underline className="w-4 h-4" />
              </button>
              <div className="w-px h-4 bg-slate-300 mx-1"></div>
              <button className="p-1.5 hover:bg-white rounded-lg transition-colors cursor-pointer" title="Bulleted List">
                <List className="w-4 h-4" />
              </button>
              <button className="p-1.5 hover:bg-white rounded-lg transition-colors cursor-pointer" title="Numbered List">
                <ListOrdered className="w-4 h-4" />
              </button>
            </div>

            {/* Essay Content Area */}
            <textarea
              rows={12}
              value={essayText}
              onChange={(e) => setEssayText(e.target.value)}
              placeholder="Write your essay here..."
              className="w-full px-5 py-4 text-[17px] text-slate-800 bg-[#fffef9] ring-1 ring-slate-900/10 rounded-2xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60 leading-8 font-serif [background-image:repeating-linear-gradient(transparent,transparent_31px,rgba(169,159,140,0.25)_31px,rgba(169,159,140,0.25)_32px)] bg-local"
            />

            {reviewedText !== null && (
              <div className="space-y-2">
                <h4 className="text-sm italic text-slate-400">
                  AI-corrected essay — hover a word to see its meaning
                </h4>
                <WordHoverLookup className="whitespace-pre-wrap rounded-2xl bg-emerald-50 border-l-4 border-emerald-400 p-5 text-[17px] font-serif leading-8 text-slate-800">
                  {reviewedText}
                </WordHoverLookup>
              </div>
            )}
          </div>

          <div className="pt-5 mt-4 border-t border-dashed border-slate-200 flex items-center justify-between text-xs text-slate-500">
            <span className="num">{wordCount} Words • {essayText.length} Characters</span>
            <span className="font-semibold text-indigo-600">Auto-saved to Notebook</span>
          </div>
        </div>

        {/* Right AI Feedback Panel (5 Cols) */}
        <div className="surface lg:col-span-5 p-7 space-y-7 lg:self-start">
          {/* Overall Score Header */}
          <div className="relative overflow-hidden p-6 rounded-3xl bg-indigo-900 text-white flex items-center justify-between">
            <div className="absolute -right-8 -top-10 w-40 h-40 rounded-full bg-purple-500/30 blur-2xl pointer-events-none" aria-hidden="true" />
            <div className="relative">
              <span className="text-sm italic text-indigo-300">
                Writing score
              </span>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="num text-6xl font-bold">{overallScore}</span>
                <span className="text-xs text-indigo-200">/ 100</span>
              </div>
              <p className="text-xs text-indigo-100 font-semibold mt-1">
                {cefrLevel} Level • {ieltsScore}
              </p>
            </div>

            <div className="relative w-16 h-16 rounded-2xl bg-white/10 flex flex-col items-center justify-center text-center rotate-6">
              <Award className="w-8 h-8 text-amber-300" />
            </div>
          </div>

          {/* AI Insights Cards List */}
          <div className="space-y-4">
            <h4 className="font-display text-xl font-bold text-slate-900">
              Corrections & vocabulary upgrades
            </h4>

            {insights.map((ins, idx) => (
              <div
                key={idx}
                className={`p-5 rounded-2xl border-l-4 space-y-2 ${
                  ins.type === "grammar"
                    ? "bg-rose-50 border-rose-400"
                    : ins.type === "vocabulary"
                    ? "bg-indigo-50 border-indigo-400"
                    : "bg-amber-50 border-amber-400"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`text-xs font-bold ${
                      ins.type === "grammar"
                        ? "text-rose-800"
                        : ins.type === "vocabulary"
                        ? "text-indigo-800"
                        : "text-amber-900"
                    }`}
                  >
                    {ins.title}
                  </span>
                  <span className="tag bg-white/80 text-slate-600">
                    {ins.type}
                  </span>
                </div>

                <p className="text-xs text-slate-700 leading-relaxed">
                  {ins.description}
                </p>

                {/* Vocabulary Synonyms Click-to-Apply */}
                {ins.synonyms && (
                  <div className="pt-2">
                    <span className="text-[11px] font-semibold text-slate-500 block mb-1">
                      Click to swap into essay:
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {ins.synonyms.map((syn, sIdx) => (
                        <button
                          key={sIdx}
                          onClick={() => applySynonym(ins.originalText || "good", syn)}
                          className="px-3 py-1.5 rounded-full bg-indigo-700 hover:bg-indigo-800 text-white text-xs font-bold transition-all hover:-translate-y-0.5 active:scale-95 cursor-pointer"
                        >
                          "{syn}"
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {ins.rule && (
                  <p className="text-[11px] text-slate-500 italic pt-1 border-t border-slate-200/60">
                    Rule: {ins.rule}
                  </p>
                )}

                {ins.suggestion && (
                  <p className="text-sm font-medium font-serif text-amber-950 bg-white/80 p-3 rounded-xl">
                    "{ins.suggestion}"
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <RearrangePanel skill="writing" />
    </div>
  );
};
