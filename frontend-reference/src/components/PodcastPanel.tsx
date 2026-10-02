// Podcast thật từ tài liệu Notebook: tạo podcast, phát audio, transcript đồng bộ theo từ (click
// tra nghĩa) và Dictation (feature-listening.md mục 1-3). Gọi backend FastAPI thật.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Headphones, ListChecks, Loader2, PenLine, Plus, XCircle } from "lucide-react";
import { useStudyTimer } from "../useStudyTimer";
import {
  ComprehensionQuestion,
  createComprehension,
  createDictation,
  createPodcast,
  DictationResult,
  fetchAudioObjectUrl,
  getPodcastTranscript,
  listDocuments,
  listPodcasts,
  listQuizzes,
  lookupWord,
  LookupResult,
  NotebookDocument,
  PodcastItem,
  QuizHistoryItem,
  QuizResult,
  submitQuiz,
  submitDictation,
  TranscriptWord,
} from "../api";

const SPEEDS = [0.75, 1, 1.25, 1.5];

export const PodcastPanel: React.FC = () => {
  const studyTimer = useStudyTimer();
  const [podcasts, setPodcasts] = useState<PodcastItem[]>([]);
  const [documents, setDocuments] = useState<NotebookDocument[]>([]);
  const [documentToUse, setDocumentToUse] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [activeId, setActiveId] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [words, setWords] = useState<TranscriptWord[]>([]);
  const [currentMs, setCurrentMs] = useState(0);
  const [speed, setSpeed] = useState(1);
  const audioRef = useRef<HTMLAudioElement>(null);

  const [lookup, setLookup] = useState<{ term: string; result: LookupResult | null; loading: boolean } | null>(null);

  const [dictationId, setDictationId] = useState<string | null>(null);
  const [dictationAudio, setDictationAudio] = useState<string | null>(null);
  const [dictationText, setDictationText] = useState("");
  const [dictationResult, setDictationResult] = useState<DictationResult | null>(null);
  const [isDictationBusy, setIsDictationBusy] = useState(false);

  // Quiz nghe hiểu (backlog 2.2): chọn đáp án -> hiện đáp án đúng, bẫy và tô đoạn căn cứ trong transcript.
  const [quiz, setQuiz] = useState<ComprehensionQuestion[]>([]);
  const [picked, setPicked] = useState<Record<number, number>>({});
  const [evidence, setEvidence] = useState<{ start: number; end: number } | null>(null);
  const [isQuizBusy, setIsQuizBusy] = useState(false);
  const [quizAttemptId, setQuizAttemptId] = useState<string | null>(null);
  const [quizResult, setQuizResult] = useState<QuizResult | null>(null);
  const [quizHistory, setQuizHistory] = useState<QuizHistoryItem[]>([]);
  const loadQuizHistory = useCallback(() => {
    listQuizzes().then(setQuizHistory).catch(() => undefined);
  }, []);
  useEffect(loadQuizHistory, [loadQuizHistory]);

  const refresh = useCallback(async () => {
    try {
      const [items, docs] = await Promise.all([listPodcasts(), listDocuments()]);
      setPodcasts(items);
      const ready = docs.items.filter((doc) => doc.status === "ready");
      setDocuments(ready);
      setDocumentToUse((current) => current || ready[0]?.id || "");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load podcasts.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Giải phóng object URL cũ khi đổi podcast/đoạn dictation.
  useEffect(() => () => { if (audioUrl) URL.revokeObjectURL(audioUrl); }, [audioUrl]);
  useEffect(() => () => { if (dictationAudio) URL.revokeObjectURL(dictationAudio); }, [dictationAudio]);

  const openPodcast = async (podcastId: string) => {
    setActiveId(podcastId);
    setError(null);
    setLookup(null);
    setDictationId(null);
    setDictationAudio(null);
    setDictationResult(null);
    setDictationText("");
    setQuiz([]);
    setPicked({});
    setQuizResult(null);
    setEvidence(null);
    try {
      const [url, transcript] = await Promise.all([
        fetchAudioObjectUrl(`/api/listening/podcasts/${podcastId}/audio`),
        getPodcastTranscript(podcastId),
      ]);
      setAudioUrl(url);
      setWords(transcript.segments);
      setCurrentMs(0);
    } catch (openError) {
      setError(openError instanceof Error ? openError.message : "Could not open podcast.");
    }
  };

  const handleCreate = async () => {
    if (!documentToUse || isCreating) return;
    setIsCreating(true);
    setError(null);
    try {
      const created = await createPodcast(documentToUse);
      await refresh();
      await openPodcast(created.id);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Could not create podcast.");
    } finally {
      setIsCreating(false);
    }
  };

  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = speed;
  }, [speed, audioUrl]);

  const activeIndex = words.findIndex((word) => currentMs >= word.start_ms && currentMs < word.end_ms + 120);

  const handleWordClick = async (index: number) => {
    const word = words[index];
    const term = word.text.replace(/[^\p{L}'-]/gu, "");
    if (!term) return;
    const context = words.slice(Math.max(0, index - 8), index + 9).map((item) => item.text).join(" ");
    setLookup({ term, result: null, loading: true });
    try {
      setLookup({ term, result: await lookupWord(term, context), loading: false });
    } catch {
      setLookup({ term, result: null, loading: false });
    }
  };

  const startQuiz = async () => {
    if (!activeId) return;
    setIsQuizBusy(true);
    setError(null);
    setPicked({});
    setQuizResult(null);
    setEvidence(null);
    try {
      const created = await createComprehension(activeId);
      setQuizAttemptId(created.attempt_id);
      setQuiz(created.questions);
      studyTimer.start();
    } catch (quizError) {
      setError(quizError instanceof Error ? quizError.message : "Could not create questions.");
    } finally {
      setIsQuizBusy(false);
    }
  };

  const pickAnswer = async (questionIndex: number, optionIndex: number) => {
    if (picked[questionIndex] !== undefined) return;
    const nextPicked = { ...picked, [questionIndex]: optionIndex };
    setPicked(nextPicked);
    // Trả lời đủ mọi câu -> tự nộp để server chấm, ghi lỗi và lưu lịch sử.
    if (quizAttemptId && Object.keys(nextPicked).length === quiz.length) {
      try {
        setQuizResult(await submitQuiz(quizAttemptId, quiz.map((_, index) => nextPicked[index] ?? null), studyTimer.lap()));
        loadQuizHistory();
      } catch (submitError) {
        setError(submitError instanceof Error ? submitError.message : "Could not submit the quiz.");
      }
    }
    const item = quiz[questionIndex];
    if (item.evidence_start_ms !== null && item.evidence_end_ms !== null) {
      setEvidence({ start: item.evidence_start_ms, end: item.evidence_end_ms });
    }
  };

  const playEvidence = (startMs: number) => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = startMs / 1000;
    void audioRef.current.play();
  };

  const startDictation = async () => {
    if (!activeId) return;
    setIsDictationBusy(true);
    setDictationResult(null);
    setDictationText("");
    setError(null);
    try {
      const attempt = await createDictation(activeId);
      studyTimer.start();
      setDictationId(attempt.attempt_id);
      setDictationAudio(await fetchAudioObjectUrl(`/api/listening/dictation/${attempt.attempt_id}/audio`));
    } catch (dictationError) {
      setError(dictationError instanceof Error ? dictationError.message : "Could not start dictation.");
    } finally {
      setIsDictationBusy(false);
    }
  };

  const checkDictation = async () => {
    if (!dictationId) return;
    setIsDictationBusy(true);
    try {
      setDictationResult(await submitDictation(dictationId, dictationText, studyTimer.lap()));
    } catch (checkError) {
      setError(checkError instanceof Error ? checkError.message : "Could not check dictation.");
    } finally {
      setIsDictationBusy(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Danh sách + tạo podcast */}
      <div className="lg:col-span-4 space-y-4">
        <div className="surface p-6 space-y-3">
          <h3 className="font-display text-xl font-bold text-slate-900 flex items-center gap-2">
            <Plus className="w-5 h-5 text-indigo-600" /> New podcast from a document
          </h3>
          {documents.length === 0 ? (
            <p className="text-xs text-slate-500">Upload a .docx or audio file in Knowledge Space first.</p>
          ) : (
            <>
              <select
                value={documentToUse}
                onChange={(event) => setDocumentToUse(event.target.value)}
                aria-label="Source document"
                className="w-full px-3 py-2.5 text-sm bg-white ring-1 ring-slate-900/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
              >
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.title} ({doc.source_type})
                  </option>
                ))}
              </select>
              <button
                onClick={handleCreate}
                disabled={isCreating}
                className="w-full py-3 bg-indigo-700 hover:bg-indigo-800 text-white text-sm font-bold rounded-xl disabled:opacity-50 flex items-center justify-center gap-2 transition-all active:scale-[0.98]"
              >
                {isCreating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating audio & transcript...</> : "Generate podcast"}
              </button>
              <p className="text-[10px] text-slate-400">.docx is rewritten into spoken style and read aloud; audio files keep the original voice and only gain a transcript.</p>
            </>
          )}
        </div>

        <div className="surface p-6 space-y-2">
          <h3 className="font-display text-xl font-bold text-slate-900 flex items-center gap-2">
            <Headphones className="w-5 h-5 text-indigo-600" /> My podcasts
          </h3>
          {podcasts.length === 0 && <p className="text-xs text-slate-500">No podcasts yet.</p>}
          {podcasts.map((podcast) => (
            <button
              key={podcast.id}
              onClick={() => podcast.status === "ready" && openPodcast(podcast.id)}
              disabled={podcast.status !== "ready"}
              className={`w-full text-left p-3.5 rounded-2xl text-xs transition-all ${
                activeId === podcast.id ? "bg-indigo-700 text-white shadow-[0_12px_20px_-12px_rgba(31,87,73,0.9)]" : "bg-paper-deep/70 hover:bg-paper-deep hover:-translate-y-px"
              } disabled:opacity-50`}
            >
              <span className={`font-bold block truncate text-sm ${activeId === podcast.id ? "text-white" : "text-slate-900"}`}>{podcast.title}</span>
              <span className={activeId === podcast.id ? "text-indigo-200" : "text-slate-500"}>
                {podcast.status === "ready" ? `${podcast.duration_seconds ?? 0}s` : podcast.status}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Player + transcript + dictation */}
      <div className="lg:col-span-8 space-y-4">
        {error && <p className="text-xs text-red-600 bg-red-50 rounded-xl px-3 py-2">{error}</p>}

        {!activeId ? (
          <div className="rounded-3xl border-2 border-dashed border-slate-300 p-14 text-center text-base text-slate-500 font-serif italic">
            Select or generate a podcast to start listening.
          </div>
        ) : (
          <>
            <div className="surface p-7 space-y-5">
              {audioUrl && (
                <audio
                  ref={audioRef}
                  src={audioUrl}
                  controls
                  className="w-full"
                  onTimeUpdate={(event) => setCurrentMs(event.currentTarget.currentTime * 1000)}
                />
              )}
              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-500 italic">Speed</span>
                {SPEEDS.map((value) => (
                  <button
                    key={value}
                    onClick={() => setSpeed(value)}
                    className={`num px-3 py-1 rounded-full font-bold transition-colors ${speed === value ? "bg-indigo-700 text-white" : "bg-paper-deep text-slate-600 hover:bg-indigo-100"}`}
                  >
                    {value}x
                  </button>
                ))}
              </div>
              <p className="text-lg leading-9 text-slate-700 font-serif">
                {words.map((word, index) => (
                  <span
                    key={`${word.start_ms}-${index}`}
                    onClick={() => handleWordClick(index)}
                    className={`cursor-pointer rounded px-0.5 ${
                      evidence && word.start_ms >= evidence.start && word.end_ms <= evidence.end
                        ? "bg-emerald-200 text-slate-900"
                        : index === activeIndex ? "bg-amber-300 text-slate-900 shadow-[0_2px_0_0_rgba(217,119,6,0.9)]" : "hover:bg-purple-100"
                    }`}
                  >
                    {word.text}{" "}
                  </span>
                ))}
              </p>
              {lookup && (
                <div className="p-4 rounded-2xl bg-indigo-50 border-l-4 border-indigo-400 text-sm space-y-1 animate-rise">
                  <p className="font-bold text-indigo-800">{lookup.term}</p>
                  {lookup.loading && <p className="text-slate-500">Looking up...</p>}
                  {lookup.result && (
                    <>
                      <p className="text-slate-700">{lookup.result.definition}</p>
                      {lookup.result.example_sentence && (
                        <p className="italic text-slate-500">“{lookup.result.example_sentence}”</p>
                      )}
                    </>
                  )}
                  {!lookup.loading && !lookup.result && <p className="text-red-600">Could not look this word up.</p>}
                </div>
              )}
            </div>

            <div className="surface p-7 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-display text-xl font-bold text-slate-900 flex items-center gap-2">
                  <ListChecks className="w-5 h-5 text-emerald-600" /> Comprehension quiz
                </h3>
                <button
                  onClick={startQuiz}
                  disabled={isQuizBusy}
                  className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl disabled:opacity-50 transition-all active:scale-95 flex items-center gap-1.5"
                >
                  {isQuizBusy && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  {quiz.length ? "New questions" : "Generate questions"}
                </button>
              </div>
              {quiz.map((item, questionIndex) => {
                const chosen = picked[questionIndex];
                return (
                  <div key={questionIndex} className="space-y-2">
                    <p className="text-sm font-bold text-slate-900">{questionIndex + 1}. {item.question}</p>
                    {item.options.map((option, optionIndex) => {
                      const reveal = chosen !== undefined;
                      const tone = !reveal
                        ? "bg-paper-deep/70 hover:bg-paper-deep"
                        : optionIndex === item.correct_index
                          ? "bg-emerald-100 text-emerald-900"
                          : optionIndex === chosen
                            ? "bg-red-100 text-red-800"
                            : "bg-paper-deep/40 text-slate-500";
                      return (
                        <button
                          key={optionIndex}
                          onClick={() => pickAnswer(questionIndex, optionIndex)}
                          className={`w-full text-left px-3.5 py-2 rounded-xl text-sm transition-colors ${tone}`}
                        >
                          {option}
                        </button>
                      );
                    })}
                    {chosen !== undefined && (
                      <div className="p-3 rounded-xl bg-emerald-50 border-l-4 border-emerald-400 text-xs space-y-1 animate-rise">
                        <p className="italic text-slate-700">“{item.evidence_text}”</p>
                        <p className="text-slate-600"><span className="font-bold">Trap:</span> {item.trap_note}</p>
                        {item.evidence_start_ms !== null && (
                          <button
                            onClick={() => playEvidence(item.evidence_start_ms as number)}
                            className="font-bold text-emerald-700 hover:underline"
                          >
                            ▶ Play this part
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
              {quizResult && (
                <p className="text-sm font-bold text-slate-900 animate-rise">
                  Score: {quizResult.correct_count}/{quizResult.total} ({Math.round(quizResult.score)}%) — wrong answers were added to your mistake notebook.
                </p>
              )}
              {quizHistory.length > 0 && (
                <details className="text-xs text-slate-600">
                  <summary className="cursor-pointer italic text-slate-500">Past quizzes</summary>
                  <ul className="mt-2 space-y-1">
                    {quizHistory.map((item) => (
                      <li key={item.id} className="flex justify-between gap-3">
                        <span className="truncate">{new Date(item.created_at).toLocaleDateString()} · {item.podcast_title}</span>
                        <span className="num font-bold">{item.correct_count}/{item.total}</span>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>

            <div className="surface p-7 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-display text-xl font-bold text-slate-900 flex items-center gap-2">
                  <PenLine className="w-5 h-5 text-purple-500" /> Dictation
                </h3>
                <button
                  onClick={startDictation}
                  disabled={isDictationBusy}
                  className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl disabled:opacity-50 transition-all active:scale-95"
                >
                  {dictationId ? "New segment" : "Start dictation"}
                </button>
              </div>
              {dictationAudio && (
                <>
                  <audio src={dictationAudio} controls className="w-full" />
                  <textarea
                    value={dictationText}
                    onChange={(event) => setDictationText(event.target.value)}
                    placeholder="Type what you hear..."
                    rows={3}
                    className="w-full px-4 py-3 text-base font-serif bg-white ring-1 ring-slate-900/10 rounded-2xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
                  />
                  <button
                    onClick={checkDictation}
                    disabled={isDictationBusy || dictationResult !== null}
                    className="px-5 py-2.5 bg-indigo-700 hover:bg-indigo-800 text-white text-xs font-bold rounded-xl disabled:opacity-50 transition-all active:scale-95"
                  >
                    Check answer
                  </button>
                </>
              )}
              {dictationResult && (
                <div className="p-4 rounded-2xl bg-paper-deep/70 text-sm space-y-2 animate-rise">
                  <p className="font-bold text-slate-900 flex items-center gap-1.5">
                    {dictationResult.score >= 90 ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    ) : (
                      <XCircle className="w-4 h-4 text-amber-600" />
                    )}
                    Accuracy: {Math.round(dictationResult.score)}%
                  </p>
                  {dictationResult.errors.length === 0 ? (
                    <p className="text-emerald-700">Perfect — no mistakes!</p>
                  ) : (
                    <ul className="space-y-0.5 text-slate-600">
                      {dictationResult.errors.map((item, index) => (
                        <li key={index}>
                          <span className="font-bold">{item.type}</span>: {item.word}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
