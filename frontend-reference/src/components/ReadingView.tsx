// Trang Reading: Skim & Scan (passage thật hoặc AI-sinh) + Classic Mode (backend thật) +
// tra từ tương tác. passage/wordData khởi tạo bằng nội dung demo, được thay bằng dữ liệu
// thật ngay khi 1 trong 2 luồng trên chạy thành công.
import React, { useState } from "react";
import { VocabWord } from "../types";
import { CountdownTimer } from "./CountdownTimer";
import { AiWait } from "./AiWait";
import { WordHoverLookup } from "./WordHoverLookup";
import { RearrangePanel } from "./RearrangePanel";
import { ReadingExtrasPanel } from "./ReadingExtrasPanel";
import { useStudyTimer } from "../useStudyTimer";
import {
  createClassicSession,
  createSkimScanSession,
  getAccessToken,
  listDocuments,
  lookupWord,
  saveVocabulary,
  submitClassicAnswers,
} from "../api";
import {
  BookOpen,
  Sparkles,
  Volume2,
  CheckCircle2,
  HelpCircle,
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
  // Đo thời gian thật cho Dashboard "This week, in minutes" (chỉ gửi khi user bật chế độ bấm giờ).
  const studyTimer = useStudyTimer();

  // Mốc giờ backend trả về cho phiên Skim & Scan mới; `key` đổi để CountdownTimer nạp lại và tự chạy.
  const [timerSeed, setTimerSeed] = useState<{ seconds: number; key: number } | null>(null);

  // Skim & Scan Generator Modal — nguồn passage thật (document đã upload) hoặc AI tự sinh theo topic.
  const [isGeneratorOpen, setIsGeneratorOpen] = useState(false);
  const [storySource, setStorySource] = useState<"topic" | "document">("topic");
  const [storyTopic, setStoryTopic] = useState("Technology & Society");
  const [storyLevel, setStoryLevel] = useState("B2");
  const [isGenerating, setIsGenerating] = useState(false);
  const [readyDocuments, setReadyDocuments] = useState<{ id: string; title: string }[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [generatorError, setGeneratorError] = useState<string | null>(null);

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
  // Hover tra nghĩa chỉ bật khi passage là excerpt thật từ file người dùng upload.
  const [passageFromDocument, setPassageFromDocument] = useState(false);
  const [isLoadingWord, setIsLoadingWord] = useState(false);
  const [classicSessionId, setClassicSessionId] = useState<string | null>(null);
  const [classicQuestion, setClassicQuestion] = useState<{ id: string; text: string; options: string[] } | null>(null);
  const [classicQuestions, setClassicQuestions] = useState<Array<{ id: string; text: string; options: string[] }>>([]);
  const [classicChoices, setClassicChoices] = useState<Record<string, number>>({});
  const [classicScore, setClassicScore] = useState<number | null>(null);
  // Đáp án đúng + giải thích theo từng câu, chỉ có sau khi nộp bài.
  const [classicResults, setClassicResults] = useState<Record<string, { correct: number; explanation: string | null }>>({});
  const [questionType, setQuestionType] = useState<"multiple_choice" | "tfng">("multiple_choice");
  const [isStartingClassic, setIsStartingClassic] = useState(false);

  // Lấy document ready đầu tiên rồi tạo Classic session bằng backend thật.
  const startBackendClassic = async () => {
    if (!getAccessToken()) return;
    setIsStartingClassic(true);
    try {
      const documents = await listDocuments();
      const readyDocument = documents.items.find((document) => document.status === "ready");
      if (!readyDocument) throw new Error("No ready document available");
      const session = await createClassicSession(readyDocument.id, 5);
      studyTimer.start();
      setClassicSessionId(session.session_id);
      const questions = session.questions.map((question) => ({ id: question.id, text: question.question_text, options: question.options }));
      setClassicQuestions(questions);
      setClassicQuestion(questions[0] || null);
      setClassicChoices({});
      setClassicScore(null);
    } catch (error) {
      console.error("Classic Reading session failed", error);
    } finally {
      setIsStartingClassic(false);
    }
  };

  // Nộp toàn bộ câu trả lời Classic Mode 1 lần sau khi người học chọn xong mọi câu hỏi.
  const submitAllBackendClassic = async () => {
    if (!classicSessionId || classicScore !== null || classicQuestions.length === 0) return;
    if (Object.keys(classicChoices).length !== classicQuestions.length) return;
    try {
      const result = await submitClassicAnswers(
        classicSessionId,
        classicQuestions.map((question) => ({ question_id: question.id, selected_option_index: classicChoices[question.id] })),
        studyTimer.lap(),
      );
      setClassicScore(result.score);
      setClassicResults(
        Object.fromEntries(
          result.results.map((item) => [item.question_id, { correct: item.correct_option_index, explanation: item.explanation ?? null }]),
        ),
      );
    } catch (error) {
      console.error("Classic Reading submit failed", error);
    }
  };

  // Fetch AI Word Lookup
  const handleWordClick = async (word: string) => {
    const cleanWord = word.toLowerCase().replace(/[^a-z]/g, "");
    setSelectedWord(cleanWord);
    setIsLoadingWord(true);
    setUserChallengeChoice(null);

    try {
      const data = getAccessToken()
        ? await lookupWord(cleanWord, passage.content)
        : null;
      setWordData({
        id: Date.now().toString(),
        word: cleanWord,
        phonetics: `/${cleanWord}/`,
        partOfSpeech: "word",
        meaning: data?.definition || "Spreading or existing widely throughout an area or group of people.",
        contextQuote: data?.example_sentence || passage.content.slice(0, 150),
        synonyms: data?.synonyms || ["widespread", "common", "broad"],
        antonyms: data?.antonyms || ["rare", "limited"],
        challengeSentence: `The influence was _____ throughout the room.`,
        challengeOptions: [cleanWord, "mitigate", "atrophy"],
        challengeCorrectIndex: 0
      });
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingWord(false);
    }
  };

  // Mở modal Skim & Scan và tải sẵn danh sách document đã ready để chọn làm nguồn passage thật.
  const openGenerator = async () => {
    setIsGeneratorOpen(true);
    setGeneratorError(null);
    if (!getAccessToken()) return;
    try {
      const documents = await listDocuments();
      const ready = documents.items
        .filter((document) => document.status === "ready")
        .map((document) => ({ id: document.id, title: document.title }));
      setReadyDocuments(ready);
      if (ready.length > 0) {
        setSelectedDocumentId(ready[0].id);
        setStorySource("document");
      } else {
        setStorySource("topic");
      }
    } catch (error) {
      console.error("Failed to load documents for Skim & Scan", error);
    }
  };

  // Skim & Scan thật: document_id → passage là excerpt THẬT từ tài liệu đã upload (không AI
  // bịa nội dung); topic → LLM backend (Ollama) tự sinh đoạn văn mới. Câu hỏi luôn do AI sinh ở cả 2 nhánh.
  const handleGenerateStory = async () => {
    if (!getAccessToken()) {
      setGeneratorError("Connect your account first to use Skim & Scan.");
      return;
    }
    setIsGenerating(true);
    setGeneratorError(null);
    try {
      const session = await createSkimScanSession(
        storySource === "document"
          ? { level: storyLevel.toLowerCase(), documentId: selectedDocumentId, questionType }
          : { level: storyLevel.toLowerCase(), topic: storyTopic, questionType },
      );
      setPassage({
        title: session.title || "Skim & Scan Passage",
        category: session.source_document_id ? "From your document" : storyTopic,
        readTime: `${Math.max(1, Math.round(session.content.split(" ").length / 200))} min read`,
        wordCount: `${session.content.split(" ").length} words`,
        content: session.content,
        vocabWords: [],
        comprehensionQuestion: "",
        comprehensionOptions: [],
        correctOptionIndex: 0,
      });
      setPassageFromDocument(Boolean(session.source_document_id));
      setClassicSessionId(session.session_id);
      const questions = session.questions.map((question) => ({
        id: question.id,
        text: question.question_text,
        options: question.options,
      }));
      setClassicQuestions(questions);
      setClassicQuestion(questions[0] || null);
      setClassicChoices({});
      setClassicScore(null);
      setClassicResults({});
      setTimerSeed({ seconds: session.time_limit_seconds, key: Date.now() });
      setIsGeneratorOpen(false);
    } catch (error) {
      const raw = error instanceof Error ? error.message : "Failed to generate passage";
      setGeneratorError(raw);
    } finally {
      setIsGenerating(false);
    }
  };

  // Đọc to 1 từ bằng Web Speech API của trình duyệt (không qua backend/Azure TTS).
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
        <p key={pIdx} className="mb-6 leading-[1.9] text-slate-800 text-[17px] font-serif max-w-[62ch] first:first-letter:font-display first:first-letter:text-6xl first:first-letter:font-bold first:first-letter:float-left first:first-letter:mr-2.5 first:first-letter:leading-[0.85] first:first-letter:text-indigo-700">
          {words.map((w, wIdx) => {
            const clean = w.toLowerCase().replace(/[^a-z]/g, "");
            const isTarget = passage.vocabWords.some((vw) => vw.toLowerCase() === clean);
            const isSelected = selectedWord.toLowerCase() === clean;

            if (isTarget) {
              return (
                <span
                  key={wIdx}
                  onClick={() => handleWordClick(clean)}
                  className={`rounded-sm px-0.5 cursor-pointer transition-all duration-150 font-semibold ${
                    isSelected
                      ? "bg-amber-300 text-amber-950 shadow-[0_2px_0_0_rgba(217,119,6,0.9)]"
                      : "bg-[linear-gradient(transparent_55%,var(--color-purple-200)_55%)] hover:bg-purple-200/60 text-slate-900"
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
    <div className="p-6 md:p-10 max-w-7xl mx-auto space-y-8">
      {/* Top Header — tiêu đề kiểu tạp chí, không đóng khung thẻ */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-5">
        <div className="flex items-start gap-4 min-w-0">
          <div className="p-3 bg-indigo-100 text-indigo-700 rounded-[14px] -rotate-3 shrink-0">
            <BookOpen className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <span className="text-sm italic text-slate-500">
              Reading & Vocabulary Studio
            </span>
            <h2 className="font-display text-2xl md:text-3xl font-bold text-slate-900 leading-tight flex items-center gap-3 flex-wrap">
              {passage.title}
              <span className="tag bg-indigo-700 text-white">
                {storyLevel} Level
              </span>
            </h2>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <CountdownTimer
            key={timerSeed?.key ?? 0}
            skill="reading"
            level={storyLevel}
            initialSeconds={timerSeed?.seconds}
            autoStart={timerSeed !== null}
          />

          <button
            onClick={() => void openGenerator()}
            className="px-4 py-2.5 bg-indigo-700 hover:bg-indigo-800 text-white font-bold text-xs rounded-xl shadow-[0_12px_22px_-12px_rgba(31,87,73,0.9)] flex items-center gap-1.5 transition-all cursor-pointer hover:-translate-y-0.5 active:scale-95"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-300" /> Skim & Scan
          </button>
          <button
            onClick={startBackendClassic}
            disabled={!getAccessToken() || isStartingClassic}
            className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl flex items-center gap-1.5 transition-all disabled:opacity-40 active:scale-95"
          >
            <BookOpen className="w-3.5 h-3.5" />
            {isStartingClassic ? "Loading Classic..." : "Start Backend Classic"}
          </button>
        </div>
      </div>

      {/* Main Grid: Reading Passage (60%) vs AI Word Lookup Panel (40%) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Pane: Reading Passage */}
        <div className="surface lg:col-span-7 p-7 md:p-10 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-5 mb-7 border-b border-dashed border-slate-200 text-xs text-slate-500">
              <span className="tag bg-indigo-100 text-indigo-700">
                {passage.category}
              </span>
              <span>{passage.readTime} • {passage.wordCount}</span>
            </div>

            {/* Passage Body */}
            <WordHoverLookup enabled={passageFromDocument} className="select-text">
              {renderInteractivePassage(passage.content)}
            </WordHoverLookup>

            {/* Comprehension Check */}
            <div className="mt-10 p-6 rounded-3xl bg-paper-deep/70 space-y-4">
              <div className="flex items-center gap-2 font-display text-lg font-bold text-slate-900">
                <HelpCircle className="w-4 h-4 text-indigo-600" /> Comprehension Check
              </div>
              {classicQuestions.length > 0 ? classicQuestions.map((question, questionIndex) => (
                <div key={question.id} className="space-y-2">
                  <p className="text-sm font-semibold text-slate-800">{questionIndex + 1}. {question.text}</p>
                  {question.options.map((option, optionIndex) => {
                    const result = classicResults[question.id];
                    const feedback = result
                      ? optionIndex === result.correct
                        ? "bg-emerald-100 text-emerald-900 ring-2 ring-emerald-500 font-bold"
                        : classicChoices[question.id] === optionIndex
                          ? "bg-rose-100 text-rose-900 ring-2 ring-rose-400 font-bold"
                          : "bg-[#fffdf8] ring-1 ring-slate-900/10 text-slate-500"
                      : null;
                    return (
                      <button
                        key={optionIndex}
                        onClick={() => setClassicChoices((current) => ({ ...current, [question.id]: optionIndex }))}
                        disabled={classicScore !== null}
                        className={`w-full p-3 rounded-xl text-xs font-medium text-left transition-all cursor-pointer ${
                          feedback ??
                          (classicChoices[question.id] === optionIndex
                            ? "bg-indigo-100 text-indigo-950 ring-2 ring-indigo-500 font-bold"
                            : "bg-[#fffdf8] ring-1 ring-slate-900/10 hover:ring-indigo-400 text-slate-700")
                        }`}
                      >
                        {option}
                      </button>
                    );
                  })}
                  {classicResults[question.id]?.explanation && (
                    <p className="text-xs text-slate-600 italic bg-white/70 rounded-xl p-3">
                      {classicResults[question.id].explanation}
                    </p>
                  )}
                </div>
              )) : (
                <>
                  <p className="text-sm font-semibold text-slate-800">{passage.comprehensionQuestion}</p>
                  <div className="space-y-2">
                    {passage.comprehensionOptions.map((option, index) => (
                      <button
                        key={index}
                        onClick={() => setUserQuizChoice(index)}
                        className={`w-full p-3 rounded-xl text-xs font-medium text-left ${userQuizChoice === index ? "bg-emerald-100 border-2 border-emerald-500" : "bg-white border border-slate-200"}`}
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                </>
              )}
              {classicQuestions.length > 0 && classicScore === null && (
                <button
                  onClick={() => void submitAllBackendClassic()}
                  disabled={Object.keys(classicChoices).length !== classicQuestions.length}
                  className="w-full rounded-xl bg-indigo-700 hover:bg-indigo-800 py-3 text-xs font-bold text-white disabled:opacity-40 transition-all active:scale-[0.98]"
                >
                  Submit Classic answers
                </button>
              )}
              {classicScore !== null && (
                <p className="text-xs font-bold text-indigo-700">
                  Backend score: {Math.round(classicScore * 100)}%
                </p>
              )}
            </div>
          </div>

          <div className="mt-8 pt-4 border-t border-dashed border-slate-200 flex items-center justify-between text-xs text-slate-400">
            <span>Tip: Click any highlighted word to inspect its AI breakdown.</span>
            <span className="font-semibold text-indigo-600">6 Target Words</span>
          </div>
        </div>

        {/* Right Pane: AI Word Lookup Panel */}
        <div className="surface lg:col-span-5 p-7 flex flex-col justify-between lg:sticky lg:top-24 lg:self-start">
          {isLoadingWord ? (
            <div className="py-12">
              <AiWait active label={`AI đang tra từ "${selectedWord}"...`} expectedSeconds={12} />
            </div>
          ) : (
            <div className="space-y-6">
              {/* Header Word Title */}
              <div className="flex items-start justify-between pb-5 border-b border-dashed border-slate-200">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="tag bg-indigo-100 text-indigo-700">
                      {wordData.partOfSpeech}
                    </span>
                    <span className="text-xs font-mono text-slate-500">{wordData.phonetics}</span>
                  </div>
                  <h2 className="font-display text-4xl font-bold text-slate-900 capitalize">
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
                    onClick={async () => {
                      if (!getAccessToken()) {
                        setIsSavedWord(!isSavedWord);
                        return;
                      }
                      try {
                        await saveVocabulary({
                          term: wordData.word,
                          definition: wordData.meaning,
                          sourceUrl: "frontend-reference://reading",
                          exampleSentence: wordData.contextQuote,
                          synonyms: wordData.synonyms,
                          antonyms: wordData.antonyms,
                        });
                        setIsSavedWord(true);
                      } catch (error) {
                        console.error("Vocabulary save failed", error);
                      }
                    }}
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
                <h4 className="text-sm italic text-slate-400 mb-1">
                  Definition & meaning
                </h4>
                <p className="text-base font-medium text-slate-800 leading-relaxed">
                  {wordData.meaning}
                </p>
              </div>

              {/* Context Quote */}
              <div className="p-4 rounded-2xl bg-indigo-50 border-l-4 border-indigo-400 text-sm text-indigo-950 space-y-1">
                <span className="font-semibold italic text-indigo-800 block text-xs">
                  Used in the article
                </span>
                <p className="italic leading-relaxed font-serif">"{wordData.contextQuote}"</p>
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
              <div className="p-5 rounded-3xl bg-amber-100/70 space-y-3 -rotate-[0.6deg]">
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
                            : "bg-[#fffdf8] text-slate-800 ring-1 ring-amber-300 hover:ring-amber-500"
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

      <RearrangePanel skill="reading" />
      <ReadingExtrasPanel />

      {/* Skim & Scan Generator Modal */}
      {isGeneratorOpen && (
        <div className="fixed inset-0 bg-slate-950/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#fffdf8] rounded-3xl max-w-md w-full p-7 shadow-[0_40px_80px_-30px_rgba(32,29,24,0.6)] animate-rise space-y-4">
            <div className="flex items-center justify-between pb-1">
              <h3 className="font-display font-bold text-2xl text-slate-900 flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-600" /> New Skim & Scan Passage
              </h3>
              <button onClick={() => setIsGeneratorOpen(false)} className="text-slate-400 hover:text-slate-600">
                ×
              </button>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Passage source</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setStorySource("document")}
                  disabled={readyDocuments.length === 0}
                  className={`py-2 text-xs font-bold rounded-xl transition-colors cursor-pointer disabled:opacity-40 ${
                    storySource === "document"
                      ? "bg-indigo-700 text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  My document
                </button>
                <button
                  onClick={() => setStorySource("topic")}
                  className={`py-2 text-xs font-bold rounded-xl transition-colors cursor-pointer ${
                    storySource === "topic"
                      ? "bg-indigo-700 text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  AI topic
                </button>
              </div>
              {storySource === "document" && readyDocuments.length === 0 && (
                <p className="text-[11px] text-amber-600 mt-1">
                  No ready document yet — upload a .docx in Knowledge Space first, or use an AI topic instead.
                </p>
              )}
            </div>

            {storySource === "document" ? (
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Document</label>
                <select
                  value={selectedDocumentId}
                  onChange={(e) => setSelectedDocumentId(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-white ring-1 ring-slate-900/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60 font-medium"
                >
                  {readyDocuments.map((document) => (
                    <option key={document.id} value={document.id}>
                      {document.title}
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-slate-400 mt-1">
                  The passage will be a real excerpt from this document, not AI-generated text.
                </p>
              </div>
            ) : (
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Topic or Subject</label>
                <select
                  value={storyTopic}
                  onChange={(e) => setStoryTopic(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-white ring-1 ring-slate-900/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60 font-medium"
                >
                  <option value="Technology & Society">Technology & Society</option>
                  <option value="Environmental Science">Environmental Science</option>
                  <option value="Business & Modern Economics">Business & Modern Economics</option>
                  <option value="Psychology & Human Behavior">Psychology & Human Behavior</option>
                  <option value="Art, Film & Culture">Art, Film & Culture</option>
                </select>
              </div>
            )}

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">CEFR Target Level</label>
              <div className="grid grid-cols-4 gap-2">
                {["B1", "B2", "C1", "C2"].map((lvl) => (
                  <button
                    key={lvl}
                    onClick={() => setStoryLevel(lvl)}
                    className={`py-2 text-xs font-bold rounded-xl transition-colors cursor-pointer ${
                      storyLevel === lvl
                        ? "bg-indigo-700 text-white"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Question type</label>
              <div className="grid grid-cols-2 gap-2">
                {([["multiple_choice", "Multiple choice"], ["tfng", "True / False / Not Given"]] as const).map(([value, label]) => (
                  <button
                    key={value}
                    onClick={() => setQuestionType(value)}
                    className={`py-2 text-xs font-bold rounded-xl transition-colors cursor-pointer ${
                      questionType === value ? "bg-indigo-700 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {generatorError && <p className="text-xs text-red-600">{generatorError}</p>}

            <AiWait active={isGenerating} label="AI đang viết đoạn văn và câu hỏi..." expectedSeconds={20} />

            <div className="pt-2 flex items-center justify-end gap-2">
              <button
                onClick={() => setIsGeneratorOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Cancel
              </button>
              <button
                onClick={handleGenerateStory}
                disabled={isGenerating || (storySource === "document" && !selectedDocumentId)}
                className="px-4 py-2 text-xs font-bold bg-indigo-700 hover:bg-indigo-800 text-white rounded-xl flex items-center gap-1.5 disabled:opacity-40 active:scale-95 transition-all"
              >
                {isGenerating ? "Generating..." : "Generate Passage"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
