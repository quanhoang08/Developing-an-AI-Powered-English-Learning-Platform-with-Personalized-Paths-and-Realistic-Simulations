import React, { useState, useEffect } from "react";
import { VocabWord } from "../types";
import {
  Timer,
  BookOpen,
  Sparkles,
  Volume2,
  CheckCircle2,
  HelpCircle,
  Play,
  Pause,
  RotateCcw,
  Tag,
  ArrowRight,
  Bookmark,
  Check,
  Zap,
  Flame,
  Search
} from "lucide-react";

export const ReadingView: React.FC = () => {
  // Timer state
  const [secondsLeft, setSecondsLeft] = useState(299); // 4:59
  const [isTimerRunning, setIsTimerRunning] = useState(true);

  // AI Story Generator Modal
  const [isGeneratorOpen, setIsGeneratorOpen] = useState(false);
  const [storyTopic, setStoryTopic] = useState("Technology & Society");
  const [storyLevel, setStoryLevel] = useState("B2");
  const [isGenerating, setIsGenerating] = useState(false);

  // Active Reading Story State
  const [passage, setPassage] = useState({
    title: "The ubiquitous nature of artificial intelligence in daily life",
    category: "Technology & Society",
    readTime: "8 min read",
    wordCount: "1,200 words",
    content: `In recent years, the integration of artificial intelligence into our daily routines has become increasingly pervasive. It is no longer confined to the realms of science fiction or specialized research laboratories; rather, it has seamlessly woven itself into the fabric of our existence. From the moment we wake up to the time we go to sleep, AI algorithms are quietly working in the background, shaping our experiences and making decisions on our behalf.

Consider the simple act of navigating through city traffic. Applications utilizing real-time data and predictive modeling mitigate congestion by suggesting optimal routes. These systems are highly sophisticated, constantly learning from vast amounts of user inputs to refine their accuracy.

However, this growing reliance on technology is not without its detractors. Critics argue that an over-dependence on automated systems could atrophy human cognitive abilities over time. If we outsource our analytical thinking to machines, we risk losing the critical problem-solving skills that have historically driven human progress.

Furthermore, the ethical implications surrounding data privacy remain deeply contentious. As these algorithms require vast troves of personal information to function optimally, establishing robust regulatory frameworks is imperative to protect individual rights.`,
    vocabWords: ["pervasive", "ubiquitous", "mitigate", "sophisticated", "atrophy", "contentious"],
    comprehensionQuestion: "What does the author suggest is a potential negative consequence of relying too heavily on AI?",
    comprehensionOptions: [
      "Decreased GPS battery efficiency",
      "Loss of human cognitive & problem-solving skills",
      "Increased municipal traffic congestion"
    ],
    correctOptionIndex: 1
  });

  // Active Selected Word for Lookup
  const [selectedWord, setSelectedWord] = useState("pervasive");
  const [wordData, setWordData] = useState<VocabWord>({
    id: "1",
    word: "pervasive",
    phonetics: "/pərˈvāsiv/",
    partOfSpeech: "adjective",
    meaning: "Spreading or existing widely throughout an area or group of people.",
    contextQuote: "In recent years, the integration of artificial intelligence into our daily routines has become increasingly pervasive.",
    synonyms: ["widespread", "ubiquitous", "omnipresent"],
    antonyms: ["rare", "uncommon", "isolated"],
    challengeSentence: "The smell of fresh coffee was _____ throughout the small cafe, drawing people in.",
    challengeOptions: ["pervasive", "atrophy", "mitigate"],
    challengeCorrectIndex: 0
  });

  // Quiz Interaction States
  const [userQuizChoice, setUserQuizChoice] = useState<number | null>(null);
  const [userChallengeChoice, setUserChallengeChoice] = useState<number | null>(null);
  const [isSavedWord, setIsSavedWord] = useState(false);
  const [isLoadingWord, setIsLoadingWord] = useState(false);

  // Skim & Scan Countdown Timer effect
  useEffect(() => {
    let interval: any = null;
    if (isTimerRunning && secondsLeft > 0) {
      interval = setInterval(() => {
        setSecondsLeft((s) => s - 1);
      }, 1000);
    } else if (secondsLeft === 0) {
      setIsTimerRunning(false);
    }
    return () => clearInterval(interval);
  }, [isTimerRunning, secondsLeft]);

  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remainder = secs % 60;
    return `${mins.toString().padStart(2, "0")}:${remainder.toString().padStart(2, "0")}`;
  };

  // Fetch AI Word Lookup
  const handleWordClick = async (word: string) => {
    const cleanWord = word.toLowerCase().replace(/[^a-z]/g, "");
    setSelectedWord(cleanWord);
    setIsLoadingWord(true);
    setUserChallengeChoice(null);

    try {
      const res = await fetch("/api/ai/word-lookup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          word: cleanWord,
          contextSentence: passage.content
        })
      });
      const data = await res.json();
      setWordData({
        id: Date.now().toString(),
        word: data.word || cleanWord,
        phonetics: data.phonetics || `/${cleanWord}/`,
        partOfSpeech: data.partOfSpeech || "adjective",
        meaning: data.meaning || "Spreading or existing widely throughout an area or group of people.",
        contextQuote: data.contextQuote || passage.content.slice(0, 150),
        synonyms: data.synonyms || ["widespread", "common", "broad"],
        antonyms: data.antonyms || ["rare", "limited"],
        challengeSentence: data.challengeSentence || `The influence was _____ throughout the room.`,
        challengeOptions: data.challengeOptions || [cleanWord, "mitigate", "atrophy"],
        challengeCorrectIndex: data.challengeCorrectIndex ?? 0
      });
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingWord(false);
    }
  };

  // Generate New AI Reading Passage
  const handleGenerateStory = async () => {
    setIsGenerating(true);
    try {
      const res = await fetch("/api/ai/generate-story", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: storyTopic, level: storyLevel })
      });
      const data = await res.json();
      setPassage(data);
      if (data.vocabWords && data.vocabWords.length > 0) {
        handleWordClick(data.vocabWords[0]);
      }
      setIsGeneratorOpen(false);
    } catch (e) {
      console.error(e);
    } finally {
      setIsGenerating(false);
    }
  };

  const playTTS = (text: string) => {
    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-US";
      window.speechSynthesis.speak(utterance);
    }
  };

  // Helper to highlight interactive vocabulary in paragraph text
  const renderInteractivePassage = (content: string) => {
    const paragraphs = content.split("\n\n");
    return paragraphs.map((para, pIdx) => {
      // Split words and check if they match any target vocab
      const words = para.split(" ");
      return (
        <p key={pIdx} className="mb-5 leading-relaxed text-slate-800 text-sm sm:text-base font-sans">
          {words.map((w, wIdx) => {
            const clean = w.toLowerCase().replace(/[^a-z]/g, "");
            const isTarget = passage.vocabWords.some((vw) => vw.toLowerCase() === clean);
            const isSelected = selectedWord.toLowerCase() === clean;

            if (isTarget) {
              return (
                <span
                  key={wIdx}
                  onClick={() => handleWordClick(clean)}
                  className={`px-1 py-0.5 rounded cursor-pointer transition-all duration-150 font-semibold border-b-2 ${
                    isSelected
                      ? "bg-amber-300 text-amber-950 border-amber-600 shadow-xs scale-105 inline-block"
                      : "bg-indigo-100/80 hover:bg-indigo-200 text-indigo-900 border-indigo-400"
                  }`}
                  title="Click for AI Word Breakdown"
                >
                  {w}{" "}
                </span>
              );
            }
            return w + " ";
          })}
        </p>
      );
    });
  };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Top Header Controls Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 bg-white rounded-3xl border border-slate-200/80 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-indigo-50 text-indigo-600 rounded-2xl border border-indigo-200/60">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              Reading & Vocabulary Studio
            </span>
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              {passage.title}
              <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full bg-indigo-600 text-white">
                {storyLevel} Level
              </span>
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Skim & Scan Timer */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs font-bold">
            <Timer className="w-4 h-4 text-amber-600" />
            <span>Skim Timer: {formatTime(secondsLeft)}</span>
            <button
              onClick={() => setIsTimerRunning(!isTimerRunning)}
              className="p-1 rounded hover:bg-amber-200/60 text-amber-800 transition-colors cursor-pointer"
            >
              {isTimerRunning ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-amber-800" />}
            </button>
          </div>

          <button
            onClick={() => setIsGeneratorOpen(true)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-md shadow-indigo-200 flex items-center gap-1.5 transition-all cursor-pointer active:scale-95"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-300" /> Generate AI Story
          </button>
        </div>
      </div>

      {/* Main Grid: Reading Passage (60%) vs AI Word Lookup Panel (40%) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Pane: Reading Passage */}
        <div className="lg:col-span-7 bg-white rounded-3xl border border-slate-200/80 p-6 md:p-8 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 mb-6 border-b border-slate-100 text-xs text-slate-500">
              <span className="font-medium text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full font-bold">
                {passage.category}
              </span>
              <span>{passage.readTime} • {passage.wordCount}</span>
            </div>

            {/* Passage Body */}
            <div className="select-text">
              {renderInteractivePassage(passage.content)}
            </div>

            {/* Comprehension Check */}
            <div className="mt-8 p-6 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-4">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-900 uppercase tracking-wide">
                <HelpCircle className="w-4 h-4 text-indigo-600" /> Comprehension Check
              </div>
              <p className="text-sm font-semibold text-slate-800">
                {passage.comprehensionQuestion}
              </p>

              <div className="space-y-2">
                {passage.comprehensionOptions.map((opt, idx) => {
                  const isSelected = userQuizChoice === idx;
                  const isCorrect = idx === passage.correctOptionIndex;

                  return (
                    <button
                      key={idx}
                      onClick={() => setUserQuizChoice(idx)}
                      className={`w-full p-3 rounded-xl text-xs font-medium text-left flex items-center justify-between transition-all cursor-pointer ${
                        isSelected
                          ? isCorrect
                            ? "bg-emerald-100 text-emerald-950 border-2 border-emerald-500 font-bold"
                            : "bg-rose-100 text-rose-950 border-2 border-rose-500 font-bold"
                          : "bg-white border border-slate-200 hover:border-indigo-300 text-slate-700"
                      }`}
                    >
                      <span>{opt}</span>
                      {isSelected && (
                        isCorrect ? (
                          <span className="text-xs font-bold text-emerald-700 flex items-center gap-1">
                            <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Correct!
                          </span>
                        ) : (
                          <span className="text-xs font-bold text-rose-600">Incorrect</span>
                        )
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
            <span>Tip: Click any highlighted word to inspect its AI breakdown.</span>
            <span className="font-semibold text-indigo-600">6 Target Words</span>
          </div>
        </div>

        {/* Right Pane: AI Word Lookup Panel */}
        <div className="lg:col-span-5 bg-white rounded-3xl border border-slate-200/80 p-6 shadow-xs flex flex-col justify-between">
          {isLoadingWord ? (
            <div className="flex flex-col items-center justify-center py-20 space-y-3">
              <Sparkles className="w-8 h-8 text-indigo-600 animate-spin" />
              <p className="text-xs font-bold text-slate-500">Generating AI Word Lookup for "{selectedWord}"...</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Header Word Title */}
              <div className="flex items-start justify-between pb-4 border-b border-slate-100">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded uppercase">
                      {wordData.partOfSpeech}
                    </span>
                    <span className="text-xs font-mono text-slate-500">{wordData.phonetics}</span>
                  </div>
                  <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight capitalize">
                    {wordData.word}
                  </h2>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => playTTS(wordData.word)}
                    className="p-2.5 rounded-2xl bg-indigo-50 hover:bg-indigo-100 text-indigo-600 transition-colors cursor-pointer"
                    title="Audio Pronunciation"
                  >
                    <Volume2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setIsSavedWord(!isSavedWord)}
                    className={`p-2.5 rounded-2xl transition-colors cursor-pointer ${
                      isSavedWord ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                    }`}
                    title="Save to Notebook"
                  >
                    {isSavedWord ? <Check className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Meaning & Definition */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
                  Definition & Meaning
                </h4>
                <p className="text-sm font-medium text-slate-800 leading-relaxed">
                  {wordData.meaning}
                </p>
              </div>

              {/* Context Quote */}
              <div className="p-3.5 rounded-2xl bg-indigo-50/70 border border-indigo-100 text-xs text-indigo-950 space-y-1">
                <span className="font-bold text-indigo-800 block text-[11px] uppercase tracking-wide">
                  Used In Article Context:
                </span>
                <p className="italic leading-relaxed">"{wordData.contextQuote}"</p>
              </div>

              {/* Synonyms & Antonyms */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="font-bold text-slate-400 block mb-1">Synonyms:</span>
                  <div className="flex flex-wrap gap-1">
                    {wordData.synonyms.map((s, i) => (
                      <span key={i} className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 font-semibold">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="font-bold text-slate-400 block mb-1">Antonyms:</span>
                  <div className="flex flex-wrap gap-1">
                    {wordData.antonyms.map((a, i) => (
                      <span key={i} className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600">
                        {a}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Mini Challenge Quiz */}
              <div className="p-4 rounded-2xl bg-amber-50/60 border border-amber-200/80 space-y-3">
                <div className="flex items-center gap-1.5 text-xs font-bold text-amber-900">
                  <Zap className="w-4 h-4 text-amber-600 fill-amber-500" />
                  <span>Guess the Context Challenge</span>
                </div>
                <p className="text-xs text-slate-700 italic">
                  "{wordData.challengeSentence}"
                </p>

                <div className="grid grid-cols-3 gap-2">
                  {wordData.challengeOptions.map((opt, idx) => {
                    const isSelected = userChallengeChoice === idx;
                    const isCorrect = idx === wordData.challengeCorrectIndex;

                    return (
                      <button
                        key={idx}
                        onClick={() => setUserChallengeChoice(idx)}
                        className={`py-2 px-1 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                          isSelected
                            ? isCorrect
                              ? "bg-emerald-600 text-white shadow-xs"
                              : "bg-rose-600 text-white"
                            : "bg-white text-slate-800 border border-amber-200 hover:border-amber-400"
                        }`}
                      >
                        {opt}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Other Words in this Story */}
              <div>
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-2">
                  Other Target Words in Passage:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {passage.vocabWords.map((vw, i) => (
                    <button
                      key={i}
                      onClick={() => handleWordClick(vw)}
                      className={`px-2.5 py-1 rounded-xl text-xs font-semibold capitalize transition-all cursor-pointer ${
                        vw.toLowerCase() === selectedWord.toLowerCase()
                          ? "bg-indigo-600 text-white font-bold shadow-xs"
                          : "bg-slate-100 hover:bg-slate-200 text-slate-700"
                      }`}
                    >
                      {vw}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* AI Story Generator Modal */}
      {isGeneratorOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-200 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="font-bold text-base text-slate-900 flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-600" /> Generate AI Reading Story
              </h3>
              <button onClick={() => setIsGeneratorOpen(false)} className="text-slate-400 hover:text-slate-600">
                ×
              </button>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Topic or Subject</label>
              <select
                value={storyTopic}
                onChange={(e) => setStoryTopic(e.target.value)}
                className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 font-medium"
              >
                <option value="Technology & Society">Technology & Society</option>
                <option value="Environmental Science">Environmental Science</option>
                <option value="Business & Modern Economics">Business & Modern Economics</option>
                <option value="Psychology & Human Behavior">Psychology & Human Behavior</option>
                <option value="Art, Film & Culture">Art, Film & Culture</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">CEFR Target Level</label>
              <div className="grid grid-cols-4 gap-2">
                {["B1", "B2", "C1", "C2"].map((lvl) => (
                  <button
                    key={lvl}
                    onClick={() => setStoryLevel(lvl)}
                    className={`py-2 text-xs font-bold rounded-xl transition-colors cursor-pointer ${
                      storyLevel === lvl
                        ? "bg-indigo-600 text-white shadow-xs"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            <div className="pt-2 flex items-center justify-end gap-2">
              <button
                onClick={() => setIsGeneratorOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Cancel
              </button>
              <button
                onClick={handleGenerateStory}
                disabled={isGenerating}
                className="px-4 py-2 text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl shadow-xs flex items-center gap-1.5"
              >
                {isGenerating ? <Sparkles className="w-3.5 h-3.5 animate-spin" /> : "Generate Passage"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
