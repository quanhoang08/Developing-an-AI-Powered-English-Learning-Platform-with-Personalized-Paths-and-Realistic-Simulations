// Trang Writing Lab — nối với API Writing thật ở backend (/api/writing/submissions, /submit).
// Điểm và gợi ý chỉ hiện sau khi người học bấm "Analyze & Correct with AI" và backend chấm xong
// (mất ~25 s với Ollama local), trước đó panel phản hồi ở trạng thái trống.
import React, { useEffect, useState } from "react";
import { WritingInsight } from "../types";
import {
  StructureReport,
  checkGrammarPreview,
  createWritingSubmission,
  getWritingStructures,
  rephraseSentence,
  submitWritingEssay,
  suggestWritingPrompt,
} from "../api";
import { useStudyTimer } from "../useStudyTimer";
import { CountdownTimer } from "./CountdownTimer";
import { AiWait } from "./AiWait";
import { WordHoverLookup } from "./WordHoverLookup";
import { RearrangePanel } from "./RearrangePanel";
import { GrammarPanel } from "./GrammarPanel";
import { ParaphraseBankPanel } from "./ParaphraseBankPanel";
import { CountUp } from "./CountUp";
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
  // Không có bước "tạo phiên" riêng trước khi soạn (khác Reading/Listening) — bắt đầu tính giờ
  // ngay lúc mở tab, coi đây là mốc gần đúng cho "bắt đầu viết".
  const studyTimer = useStudyTimer();
  useEffect(() => {
    studyTimer.start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [essayTitle, setEssayTitle] = useState("");
  const [essayText, setEssayText] = useState("");

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  // Bài luận sau khi áp dụng các sửa lỗi của AI; null cho tới khi chấm xong lần đầu.
  // Hover tra nghĩa chỉ bật ở vùng này (không bật ở ô soạn thảo).
  const [reviewedText, setReviewedText] = useState<string | null>(null);
  // null cho tới khi backend chấm xong: không hiển thị điểm/gợi ý mẫu như thể là kết quả thật.
  const [overallScore, setOverallScore] = useState<number | null>(null);
  const [cefrLevel, setCefrLevel] = useState("");
  const [ieltsScore, setIeltsScore] = useState("");

  const [insights, setInsights] = useState<WritingInsight[]>([]);

  // Gợi ý đề (POST /prompts/suggest): nếu đã gõ tiêu đề thì coi đó là chủ đề, không thì xin đề kiểu IELTS.
  const [promptOptions, setPromptOptions] = useState<string[]>([]);
  const [isSuggesting, setIsSuggesting] = useState(false);
  // Viết lại câu yếu nhất (POST /rephrase) — cần submission đã nộp.
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const [rephrased, setRephrased] = useState<Awaited<ReturnType<typeof rephraseSentence>> | null>(null);
  const [isRephrasing, setIsRephrasing] = useState(false);
  // Cấu trúc câu của bài vừa nộp (GET /structures, chấm bằng luật nên trả ngay).
  const [structures, setStructures] = useState<StructureReport | null>(null);

  const handleSuggestPrompt = async () => {
    setAnalyzeError(null);
    setIsSuggesting(true);
    try {
      const topic = essayTitle.trim();
      const result = await suggestWritingPrompt(topic ? { topic } : { certificateStyle: "ielts" });
      const options = result.prompt_options ?? (result.prompt_text ? [result.prompt_text] : []);
      if (options.length === 1) setEssayTitle(options[0]);
      setPromptOptions(options.length === 1 ? [] : options);
    } catch (error) {
      setAnalyzeError(error instanceof Error ? error.message : "Failed to suggest a topic");
    } finally {
      setIsSuggesting(false);
    }
  };

  // Kiểm tra nhanh ngữ pháp (POST /grammar-check với raw_text) — chỉ xem trước, không tạo submission.
  const [grammarHints, setGrammarHints] = useState<Awaited<ReturnType<typeof checkGrammarPreview>>["insights"] | null>(null);
  const [isCheckingGrammar, setIsCheckingGrammar] = useState(false);

  const handleGrammarCheck = async () => {
    setAnalyzeError(null);
    setIsCheckingGrammar(true);
    try {
      setGrammarHints((await checkGrammarPreview(essayText)).insights);
    } catch (error) {
      setAnalyzeError(error instanceof Error ? error.message : "Failed to check grammar");
    } finally {
      setIsCheckingGrammar(false);
    }
  };

  const handleRephrase = async () => {
    if (!submissionId) return;
    setAnalyzeError(null);
    setIsRephrasing(true);
    try {
      setRephrased(await rephraseSentence(submissionId));
    } catch (error) {
      setAnalyzeError(error instanceof Error ? error.message : "Failed to rephrase");
    } finally {
      setIsRephrasing(false);
    }
  };

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
      const result = await submitWritingEssay(submission.submission_id, essayText, studyTimer.lap());
      setSubmissionId(submission.submission_id);
      setRephrased(null);
      setStructures(null);
      // Báo cáo phụ: lỗi ở đây không được làm hỏng kết quả chấm điểm đã có.
      getWritingStructures(submission.submission_id).then(setStructures).catch(() => undefined);
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
    <div className="stagger-in p-6 md:p-10 max-w-7xl mx-auto space-y-8">
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

        <div className="flex flex-wrap items-center gap-3">
          <CountdownTimer skill="writing" />
          <button
            onClick={handleAnalyzeWriting}
            disabled={isAnalyzing}
            className="px-6 py-3 bg-indigo-700 hover:bg-indigo-800 text-white font-bold text-sm rounded-2xl shadow-[0_16px_26px_-14px_rgba(31,87,73,0.9)] flex items-center justify-center gap-2 transition-all cursor-pointer hover:-translate-y-0.5 active:scale-95 disabled:opacity-50"
          >
            {isAnalyzing ? <Sparkles className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4 text-amber-300" />}
            {isAnalyzing ? "Analyzing Essay..." : "Analyze & Correct with AI"}
          </button>
        </div>
      </div>

      <AiWait active={isAnalyzing} label="AI đang chấm bài và tìm lỗi..." expectedSeconds={25} />

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

            <div className="space-y-2">
              <button
                onClick={handleSuggestPrompt}
                disabled={isSuggesting}
                className="text-xs font-bold text-indigo-700 hover:text-indigo-800 flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                <Sparkles className={`w-3.5 h-3.5 ${isSuggesting ? "animate-spin" : ""}`} />
                {isSuggesting ? "Thinking of topics…" : "Suggest a topic (uses the title as theme, or IELTS style)"}
              </button>
              {promptOptions.map((option) => (
                <button
                  key={option}
                  onClick={() => {
                    setEssayTitle(option);
                    setPromptOptions([]);
                  }}
                  className="block w-full text-left text-sm px-4 py-2 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-900 cursor-pointer"
                >
                  {option}
                </button>
              ))}
            </div>

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

            <button
              onClick={handleGrammarCheck}
              disabled={isCheckingGrammar || !essayText.trim()}
              className="px-4 py-2 bg-white ring-1 ring-slate-900/10 hover:ring-indigo-400 disabled:opacity-50 text-slate-700 font-bold text-xs rounded-2xl cursor-pointer"
            >
              {isCheckingGrammar ? "Checking…" : "Quick grammar check"}
            </button>
            {grammarHints !== null && (
              <div className="space-y-2 text-sm">
                {grammarHints.length === 0 && <p className="text-slate-500">No grammar issues found.</p>}
                {grammarHints.map((hint, i) => (
                  <p key={i} className="p-3 rounded-xl bg-rose-50 border-l-4 border-rose-400">
                    <span className="line-through text-rose-700">{hint.original_text}</span> → <span className="font-semibold">{hint.suggested_text}</span>
                    <span className="block text-xs text-slate-500">{hint.explanation}</span>
                  </p>
                ))}
              </div>
            )}

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
                <span className="num text-6xl font-bold">{overallScore === null ? "—" : <CountUp value={overallScore} />}</span>
                <span className="text-xs text-indigo-200">/ 100</span>
              </div>
              <p className="text-xs text-indigo-100 font-semibold mt-1">
                {overallScore === null
                  ? isAnalyzing
                    ? "Đang chấm bài..."
                    : "Chưa chấm — hãy viết bài rồi bấm Analyze"
                  : `${cefrLevel} Level • ${ieltsScore}`}
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

            {overallScore === null && (
              <p className="text-sm text-slate-500 leading-relaxed">
                Nộp bài ({MIN_SUBMISSION_WORDS} từ trở lên) để nhận điểm, sửa lỗi ngữ pháp và gợi ý từ vựng học thuật từ AI.
              </p>
            )}
            {overallScore !== null && insights.length === 0 && (
              <p className="text-sm text-slate-500 leading-relaxed">AI không tìm thấy lỗi nào cần sửa trong bài này.</p>
            )}

            {submissionId && (
              <div className="space-y-2">
                <button
                  onClick={handleRephrase}
                  disabled={isRephrasing}
                  className="px-4 py-2 bg-indigo-700 hover:bg-indigo-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl cursor-pointer"
                >
                  {isRephrasing ? "Rephrasing…" : "Rephrase my weakest sentence"}
                </button>
                {rephrased && (
                  <div className="p-4 rounded-2xl bg-white ring-1 ring-slate-900/10 space-y-2 text-sm">
                    <p className="text-slate-500 italic">"{rephrased.original_sentence}"</p>
                    {rephrased.suggested_sentences.map((s, i) => (
                      <p key={i} className="text-slate-800">
                        <span className="font-serif font-medium">{s.text}</span>
                        <span className="block text-xs text-slate-500">{s.explanation}</span>
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}

            {structures && structures.sentence_count > 0 && (
              <div className="p-4 rounded-2xl bg-white ring-1 ring-slate-900/10 space-y-3 text-sm">
                <p className="font-bold text-slate-900">
                  Sentence structures · {structures.distinct_structures} of 8 kinds used
                </p>
                <div className="grid grid-cols-4 gap-2 text-center">
                  {([["simple", "Simple"], ["compound", "Compound"], ["complex", "Complex"], ["compound_complex", "Comp-complex"]] as const).map(
                    ([key, label]) => (
                      <div key={key} className="p-2 rounded-xl bg-slate-50">
                        <p className="num text-lg font-bold text-slate-900">{structures.types[key]}</p>
                        <p className="text-[11px] text-slate-500">{label}</p>
                      </div>
                    ),
                  )}
                </div>
                <p className="text-xs text-slate-600">
                  Conditional {structures.features.conditional} · Passive {structures.features.passive} · Relative clause{" "}
                  {structures.features.relative_clause} · Question {structures.features.question}
                </p>
                {structures.types.simple === structures.sentence_count && (
                  <p className="text-xs text-amber-800">Every sentence is simple — try joining ideas with because, although or which.</p>
                )}
              </div>
            )}

            {insights.map((ins, idx) => (
              <div
                key={idx}
                style={{ animationDelay: `${Math.min(idx, 8) * 0.06}s` }}
                className={`pop-in p-5 rounded-2xl border-l-4 space-y-2 ${
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
      <ParaphraseBankPanel />
      <GrammarPanel />
    </div>
  );
};
