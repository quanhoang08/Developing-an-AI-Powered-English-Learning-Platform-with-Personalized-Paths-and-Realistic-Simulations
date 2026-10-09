// Ba bài luyện từ vựng của Reading nối API thật: Guess the Context (POST /api/reading/guess-context)
// và Story từ từ đã lưu (POST /api/stories), Use it in a sentence (POST /api/vocab/{id}/check-sentence). Cả ba chạy LLM nên có trạng thái chờ + ErrorNotice.
import React, { useState } from "react";
import { BookMarked, CheckCircle2, Loader2, XCircle } from "lucide-react";
import {
  ConfusableQuestion,
  DueVocabulary,
  GuessContextAttempt,
  SentenceVerdict,
  WordFamily,
  checkVocabSentence,
  createGuessContext,
  createStory,
  getConfusableQuiz,
  getWordFamily,
  listDueVocabulary,
  submitConfusableQuiz,
  submitGuessContext,
} from "../api";
import { ErrorNotice } from "./ErrorNotice";
import { MnemonicsPanel } from "./MnemonicsPanel";
import { WordlistPanel } from "./WordlistPanel";
import { AdaptTextPanel } from "./AdaptTextPanel";

// Chọn từ khi có hàng trăm từ đến hạn: ô tìm kiếm + danh sách cuộn giới hạn, từ đã chọn hiện thành hàng riêng phía trên.
const SHOW = 40;
const WordPicker: React.FC<{
  items: DueVocabulary[];
  selected: string[];
  onToggle: (id: string) => void;
  multi?: boolean;
  limit?: number;
  onRandom?: () => void;
}> = ({ items, selected, onToggle, multi, limit, onRandom }) => {
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const matches = items.filter((i) => !needle || i.term.toLowerCase().includes(needle) || (i.definition ?? "").toLowerCase().includes(needle));
  const chosen = items.filter((i) => selected.includes(i.id));
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search your words" placeholder={`Search ${items.length} words…`}
          className="flex-1 px-3 py-2 rounded-xl ring-1 ring-slate-900/10 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/60" />
        {multi && onRandom && (
          <button onClick={onRandom} className="px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-xs font-bold text-slate-700 cursor-pointer">Random 8</button>
        )}
      </div>
      {chosen.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {multi && <span className="text-xs text-slate-500">Selected {chosen.length}{limit ? `/${limit}` : ""}:</span>}
          {chosen.map((i) => (
            <button key={i.id} onClick={() => onToggle(i.id)} aria-label={`Remove ${i.term}`} className="px-2.5 py-1 rounded-full bg-indigo-700 text-white text-xs font-bold cursor-pointer">{i.term} ×</button>
          ))}
        </div>
      )}
      <div className="max-h-48 overflow-y-auto rounded-xl bg-slate-50 p-2 flex flex-wrap gap-1.5">
        {matches.slice(0, SHOW).map((i) => (
          <button key={i.id} onClick={() => onToggle(i.id)} aria-pressed={selected.includes(i.id)}
            className={`px-2.5 py-1 rounded-full text-xs font-bold cursor-pointer ${selected.includes(i.id) ? "bg-indigo-700 text-white" : "bg-white ring-1 ring-slate-900/10 text-slate-700 hover:bg-slate-100"}`}>
            {i.term}
          </button>
        ))}
        {matches.length === 0 && <p className="text-xs text-slate-500 px-1">No word matches "{q}".</p>}
        {matches.length > SHOW && <p className="w-full text-xs text-slate-500 px-1 pt-1">Showing {SHOW} of {matches.length} — type to narrow down.</p>}
      </div>
    </div>
  );
};

export const ReadingExtrasPanel: React.FC = () => {
  const [term, setTerm] = useState("");
  const [attempt, setAttempt] = useState<GuessContextAttempt | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  const [answer, setAnswer] = useState<{ correct: boolean; correct_option_index: number } | null>(null);

  const [vocab, setVocab] = useState<DueVocabulary[] | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [story, setStory] = useState<{ content: string; missing_terms: string[] } | null>(null);

  const [sentenceWordId, setSentenceWordId] = useState<string | null>(null);
  const [sentence, setSentence] = useState("");
  const [verdict, setVerdict] = useState<SentenceVerdict | null>(null);

  const [family, setFamily] = useState<WordFamily | null>(null);

  const [confQuiz, setConfQuiz] = useState<ConfusableQuestion[] | null>(null);
  const [confPicks, setConfPicks] = useState<Record<string, string>>({});
  const [confResult, setConfResult] = useState<Awaited<ReturnType<typeof submitConfusableQuiz>> | null>(null);

  const [busy, setBusy] = useState<"guess" | "answer" | "vocab" | "story" | "sentence" | "family" | "confusable" | null>(null);
  const [error, setError] = useState<{ cause: unknown; retry: () => void } | null>(null);

  // Bọc mọi thao tác: bật busy, xóa lỗi cũ, và gắn nút "Try again" chạy lại đúng thao tác vừa lỗi.
  const run = async (kind: NonNullable<typeof busy>, action: () => Promise<void>) => {
    setBusy(kind);
    setError(null);
    try {
      await action();
    } catch (cause) {
      setError({ cause, retry: () => run(kind, action) });
    } finally {
      setBusy(null);
    }
  };

  const startGuess = () =>
    run("guess", async () => {
      setAttempt(null);
      setAnswer(null);
      setPicked(null);
      setAttempt(await createGuessContext({ term: term.trim() }));
    });

  const choose = (index: number) => {
    if (!attempt || answer) return;
    setPicked(index);
    run("answer", async () => setAnswer(await submitGuessContext(attempt.attempt_id, index)));
  };

  const loadVocab = () => run("vocab", async () => setVocab(await listDueVocabulary()));

  const makeStory = () =>
    run("story", async () => {
      setStory(null);
      setStory(await createStory(selected));
    });

  const sentenceTerm = vocab?.find((item) => item.id === sentenceWordId)?.term ?? "";
  // Khớp đầu từ như backend (find_missing_terms) để "run" vẫn khớp "running".
  const sentenceMissingTerm =
    sentence.trim().length >= 3 &&
    !new RegExp(`\\b${sentenceTerm.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`, "i").test(sentence);

  const checkSentence = () =>
    run("sentence", async () => {
      setVerdict(null);
      setVerdict(await checkVocabSentence(sentenceWordId!, sentence.trim()));
    });

  const loadFamily = () =>
    run("family", async () => {
      setFamily(null);
      setFamily(await getWordFamily(sentenceWordId!));
    });

  const startConfusables = () =>
    run("confusable", async () => {
      setConfResult(null);
      setConfPicks({});
      setConfQuiz(await getConfusableQuiz(8));
    });

  const submitConfusables = () =>
    run("confusable", async () =>
      setConfResult(await submitConfusableQuiz(Object.entries<string>(confPicks).map(([question_id, choice]) => ({ question_id, choice })))),
    );

  const toggle = (id: string) =>
    setSelected((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id].slice(0, 15)));

  return (
    <div className="surface p-7 space-y-8">
      <section className="space-y-4">
        <h3 className="font-display text-2xl font-bold text-slate-900 flex items-center gap-2">
          <BookMarked className="w-6 h-6 text-indigo-600" /> Guess the context
        </h3>
        <div className="flex gap-2">
          <input
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            placeholder="A word you want to practise…"
            maxLength={100}
            className="flex-1 px-4 py-2.5 rounded-xl ring-1 ring-slate-900/10 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
          />
          <button
            onClick={startGuess}
            disabled={busy !== null || !term.trim()}
            className="px-4 py-2 bg-indigo-700 hover:bg-indigo-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl flex items-center gap-2 cursor-pointer"
          >
            {busy === "guess" && <Loader2 className="w-4 h-4 animate-spin" />} Challenge me
          </button>
        </div>
        {attempt && (
          <div className="space-y-3">
            <p className="font-serif text-lg text-slate-800">{attempt.challenge_sentence}</p>
            <ul className="grid sm:grid-cols-2 gap-2">
              {attempt.options.map((option, index) => {
                const right = answer?.correct_option_index === index;
                const wrong = answer !== null && picked === index && !right;
                return (
                  <li key={index}>
                    <button
                      onClick={() => choose(index)}
                      disabled={busy !== null || answer !== null}
                      className={`w-full text-left px-4 py-2.5 rounded-xl border text-sm flex items-center gap-2 cursor-pointer ${
                        right
                          ? "border-emerald-400 bg-emerald-50 text-emerald-900"
                          : wrong
                            ? "border-rose-400 bg-rose-50 text-rose-900"
                            : "border-slate-200 bg-white hover:bg-slate-50"
                      }`}
                    >
                      <span className="flex-1">{option}</span>
                      {right && <CheckCircle2 className="w-4 h-4 text-emerald-600" />}
                      {wrong && <XCircle className="w-4 h-4 text-rose-600" />}
                    </button>
                  </li>
                );
              })}
            </ul>
            {answer && (
              <p className="text-sm font-bold text-slate-900">
                {answer.correct ? "Correct!" : "Not quite — the right answer is highlighted."}
              </p>
            )}
          </div>
        )}
      </section>

      <section className="space-y-4 border-t border-dashed border-slate-200 pt-6">
        <h3 className="font-display text-2xl font-bold text-slate-900">Story from your words</h3>
        {vocab === null ? (
          <button
            onClick={loadVocab}
            disabled={busy !== null}
            className="px-4 py-2 bg-indigo-700 hover:bg-indigo-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl flex items-center gap-2 cursor-pointer"
          >
            {busy === "vocab" && <Loader2 className="w-4 h-4 animate-spin" />} Pick words to review
          </button>
        ) : vocab.length === 0 ? (
          <p className="text-sm text-slate-500">No words due for review — save some words while reading first.</p>
        ) : (
          <>
            <WordPicker items={vocab} selected={selected} onToggle={toggle} multi limit={15}
              onRandom={() => setSelected([...vocab].sort(() => Math.random() - 0.5).slice(0, 8).map((x) => x.id))} />
            <button
              onClick={makeStory}
              disabled={busy !== null || selected.length === 0}
              className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl flex items-center gap-2 cursor-pointer"
            >
              {busy === "story" && <Loader2 className="w-4 h-4 animate-spin" />} Write my story
            </button>
          </>
        )}
        {story && (
          <div className="space-y-2">
            <p className="whitespace-pre-wrap font-serif text-[17px] leading-8 text-slate-800">{story.content}</p>
            {story.missing_terms.length > 0 && (
              <p className="text-xs text-slate-500">Not used by the AI: {story.missing_terms.join(", ")}</p>
            )}
          </div>
        )}
      </section>

      <section className="space-y-4 border-t border-dashed border-slate-200 pt-6">
        <h3 className="font-display text-2xl font-bold text-slate-900">Use it in a sentence</h3>
        {vocab === null ? (
          <button
            onClick={loadVocab}
            disabled={busy !== null}
            className="px-4 py-2 bg-indigo-700 hover:bg-indigo-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl flex items-center gap-2 cursor-pointer"
          >
            {busy === "vocab" && <Loader2 className="w-4 h-4 animate-spin" />} Pick a word
          </button>
        ) : vocab.length === 0 ? (
          <p className="text-sm text-slate-500">No words due for review — save some words while reading first.</p>
        ) : (
          <>
            <WordPicker items={vocab} selected={sentenceWordId ? [sentenceWordId] : []}
              onToggle={(id) => { setSentenceWordId(id === sentenceWordId ? null : id); setVerdict(null); setFamily(null); }} />
            {sentenceWordId && (
              <div className="space-y-3">
                <button
                  onClick={loadFamily}
                  disabled={busy !== null}
                  className="px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl flex items-center gap-2 cursor-pointer"
                >
                  {busy === "family" && <Loader2 className="w-4 h-4 animate-spin" />} Word family &amp; collocations
                </button>
                {family && (
                  <div className="rounded-2xl bg-slate-50 p-4 space-y-3 text-sm" role="status">
                    <div className="flex flex-wrap gap-2">
                      {family.word_family.map((entry) => (
                        <span key={entry.word} className="px-3 py-1 rounded-full bg-white ring-1 ring-slate-900/10 text-xs">
                          <b>{entry.word}</b> <span className="text-slate-500">{entry.part_of_speech}</span>
                        </span>
                      ))}
                    </div>
                    <ul className="list-disc ml-5 text-slate-700 font-serif">
                      {family.collocations.map((phrase) => <li key={phrase}>{phrase}</li>)}
                    </ul>
                  </div>
                )}
                <MnemonicsPanel term={sentenceTerm} />
                <textarea
                  value={sentence}
                  onChange={(e) => setSentence(e.target.value)}
                  placeholder="Write your own sentence with this word…"
                  maxLength={300}
                  rows={2}
                  className="w-full px-4 py-2.5 rounded-xl ring-1 ring-slate-900/10 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
                />
                <button
                  onClick={checkSentence}
                  disabled={busy !== null || sentence.trim().length < 3 || sentenceMissingTerm}
                  className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl flex items-center gap-2 cursor-pointer"
                >
                  {busy === "sentence" && <Loader2 className="w-4 h-4 animate-spin" />} Check my sentence
                </button>
                {sentenceMissingTerm && (
                  <p className="text-xs text-rose-700" role="alert">
                    Your sentence must include “{sentenceTerm}”.
                  </p>
                )}
              </div>
            )}
            {verdict && (
              <div className="rounded-2xl bg-slate-50 p-4 space-y-2 text-sm" role="status">
                <p className="flex items-center gap-2 font-bold text-slate-900">
                  {verdict.meaning_fits && verdict.grammar_ok ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-600" />
                  )}
                  {verdict.meaning_fits ? "Word used correctly" : "Check the word's meaning"} ·{" "}
                  {verdict.grammar_ok ? "grammar OK" : "grammar needs a fix"}
                </p>
                {!verdict.grammar_ok && (
                  <p className="font-serif text-slate-800">Suggested: {verdict.corrected_sentence}</p>
                )}
                <p className="text-slate-600">{verdict.feedback_vi}</p>
              </div>
            )}
          </>
        )}
      </section>

      <section className="space-y-4 border-t border-dashed border-slate-200 pt-6">
        <h3 className="font-display text-2xl font-bold text-slate-900">Confusing word pairs</h3>
        {confQuiz === null ? (
          <button
            onClick={startConfusables}
            disabled={busy !== null}
            className="px-4 py-2 bg-indigo-700 hover:bg-indigo-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl flex items-center gap-2 cursor-pointer"
          >
            {busy === "confusable" && <Loader2 className="w-4 h-4 animate-spin" />} Start 8 questions
          </button>
        ) : (
          <>
            <ol className="space-y-4">
              {confQuiz.map((question, index) => {
                const result = confResult?.results.find((r) => r.question_id === question.question_id);
                return (
                  <li key={question.question_id} className="space-y-2">
                    <p className="font-serif text-lg text-slate-800">{index + 1}. {question.sentence}</p>
                    <div className="flex gap-2">
                      {question.options.map((option) => (
                        <button
                          key={option}
                          onClick={() => setConfPicks((c) => ({ ...c, [question.question_id]: option }))}
                          disabled={confResult !== null}
                          aria-pressed={confPicks[question.question_id] === option}
                          className={`px-4 py-1.5 rounded-xl border text-sm cursor-pointer ${
                            result && option === result.correct_answer
                              ? "border-emerald-400 bg-emerald-50 text-emerald-900"
                              : result && confPicks[question.question_id] === option
                                ? "border-rose-400 bg-rose-50 text-rose-900"
                                : confPicks[question.question_id] === option
                                  ? "border-indigo-500 bg-indigo-50"
                                  : "border-slate-200 bg-white hover:bg-slate-50"
                          }`}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                    {result && !result.is_correct && (
                      <div className="text-sm text-slate-600 space-y-1">
                        <p>{result.explanation_vi}</p>
                        {result.contrast_vi && <p className="text-indigo-700">Tiếng Việt vs English: {result.contrast_vi}</p>}
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
            {confResult ? (
              <p className="text-sm font-bold text-slate-900" role="status">
                Score: {confResult.score}/{confResult.total}
              </p>
            ) : (
              <button
                onClick={submitConfusables}
                disabled={busy !== null || Object.keys(confPicks).length < confQuiz.length}
                className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl flex items-center gap-2 cursor-pointer"
              >
                {busy === "confusable" && <Loader2 className="w-4 h-4 animate-spin" />} Check answers
              </button>
            )}
            {confResult && (
              <button onClick={startConfusables} className="text-sm font-bold text-indigo-700 cursor-pointer">
                Try another set
              </button>
            )}
          </>
        )}
      </section>

      <WordlistPanel />

      <AdaptTextPanel />

      {error && <ErrorNotice error={error.cause} onRetry={error.retry} retryLabel="Try again" />}
    </div>
  );
};
