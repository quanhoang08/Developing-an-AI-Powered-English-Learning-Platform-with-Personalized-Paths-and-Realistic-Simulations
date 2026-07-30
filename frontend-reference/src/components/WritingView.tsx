import React, { useState } from "react";
import { WritingInsight } from "../types";
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

export const WritingView: React.FC = () => {
  const [essayTitle, setEssayTitle] = useState("Impact of Generative AI on Modern Education");
  const [essayText, setEssayText] = useState(
    `Generative artificial intelligence is rapidly changing how students learn and teachers instruct. Some educators fear that AI tools will affect student critical thinking skills negatively. However, if integrated properly, AI can serve as a good tutor that provides personalized feedback and accelerates language acquisition.

In addition, AI tools can automate administrative tasks for teachers, allowing them to focus more on direct human interaction and mentorship.`
  );

  const [isAnalyzing, setIsAnalyzing] = useState(false);
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

  const handleAnalyzeWriting = async () => {
    setIsAnalyzing(true);
    try {
      const res = await fetch("/api/ai/writing-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: essayTitle, text: essayText })
      });
      const data = await res.json();
      if (data.overallScore) setOverallScore(data.overallScore);
      if (data.cefrLevel) setCefrLevel(data.cefrLevel);
      if (data.ieltsScore) setIeltsScore(data.ieltsScore);
      if (data.insights && data.insights.length > 0) setInsights(data.insights);
    } catch (e) {
      console.error(e);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const applySynonym = (targetWord: string, replacement: string) => {
    const updated = essayText.replace(new RegExp(`\\b${targetWord}\\b`, "i"), replacement);
    setEssayText(updated);
  };

  const wordCount = essayText.trim().split(/\s+/).filter(Boolean).length;

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <PenTool className="w-6 h-6 text-indigo-600" /> Writing & Correction Lab
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Compose essays and get instant AI scoring, grammar fixes, and academic vocabulary upgrades.
          </p>
        </div>

        <button
          onClick={handleAnalyzeWriting}
          disabled={isAnalyzing}
          className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-2xl shadow-md shadow-indigo-200 flex items-center justify-center gap-2 transition-all cursor-pointer active:scale-95 disabled:opacity-50"
        >
          {isAnalyzing ? <Sparkles className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4 text-amber-300" />}
          {isAnalyzing ? "Analyzing Essay..." : "Analyze & Correct with AI"}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Writing Editor (7 Cols) */}
        <div className="lg:col-span-7 bg-white rounded-3xl border border-slate-200/80 p-6 shadow-xs flex flex-col justify-between min-h-[560px]">
          <div className="space-y-4">
            {/* Title Input */}
            <input
              type="text"
              value={essayTitle}
              onChange={(e) => setEssayTitle(e.target.value)}
              placeholder="Essay Title..."
              className="w-full text-lg font-extrabold text-slate-900 border-b border-slate-100 pb-2 focus:outline-none focus:border-indigo-500 transition-colors"
            />

            {/* Rich Text Toolbar */}
            <div className="flex items-center gap-1 p-1.5 bg-slate-100/80 rounded-xl border border-slate-200 text-slate-600">
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
              className="w-full p-4 text-xs sm:text-sm text-slate-800 bg-slate-50/50 border border-slate-200/80 rounded-2xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 leading-relaxed font-sans"
            />
          </div>

          <div className="pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>{wordCount} Words • {essayText.length} Characters</span>
            <span className="font-semibold text-indigo-600">Auto-saved to Notebook</span>
          </div>
        </div>

        {/* Right AI Feedback Panel (5 Cols) */}
        <div className="lg:col-span-5 bg-white rounded-3xl border border-slate-200/80 p-6 shadow-xs space-y-6">
          {/* Overall Score Header */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-indigo-900 to-purple-900 text-white flex items-center justify-between">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-300">
                Writing Score
              </span>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-3xl font-extrabold">{overallScore}</span>
                <span className="text-xs text-indigo-200">/ 100</span>
              </div>
              <p className="text-xs text-indigo-100 font-semibold mt-1">
                {cefrLevel} Level • {ieltsScore}
              </p>
            </div>

            <div className="w-16 h-16 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 flex flex-col items-center justify-center text-center">
              <Award className="w-7 h-7 text-amber-300" />
            </div>
          </div>

          {/* AI Insights Cards List */}
          <div className="space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              AI Corrections & Vocabulary Upgrades
            </h4>

            {insights.map((ins, idx) => (
              <div
                key={idx}
                className={`p-4 rounded-2xl border space-y-2 ${
                  ins.type === "grammar"
                    ? "bg-rose-50/60 border-rose-200"
                    : ins.type === "vocabulary"
                    ? "bg-indigo-50/60 border-indigo-200"
                    : "bg-amber-50/60 border-amber-200"
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
                  <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-white/80">
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
                          className="px-2.5 py-1 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-xs transition-transform active:scale-95 cursor-pointer"
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
                  <p className="text-xs font-medium text-amber-900 bg-white/80 p-2.5 rounded-xl border border-amber-200/60">
                    "{ins.suggestion}"
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
