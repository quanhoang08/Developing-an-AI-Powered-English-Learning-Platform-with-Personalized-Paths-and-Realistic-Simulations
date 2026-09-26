// Đề luyện tập động do Adaptive Learning Engine sinh từ lỗi của user: sinh đề -> chọn đáp án
// -> nộp -> xem đáp án đúng/giải thích. Đáp án đúng chỉ được backend trả SAU khi nộp bài.
import React, { useState } from "react";
import { CheckCircle2, Loader2, Sparkles, XCircle } from "lucide-react";
import {
  AdaptiveQuiz,
  AdaptiveQuizResult,
  generateAdaptiveQuiz,
  submitAdaptiveQuiz,
} from "../api";

// Backend trả mã lỗi ngắn gọn (detail); đổi sang câu người học đọc được.
const ERROR_MESSAGES: Record<string, string> = {
  no_errors_to_practice: "No mistakes recorded yet — write an essay or try a dictation first.",
};

interface AdaptiveQuizPanelProps {
  // Gọi sau khi nộp bài để cha tải lại nhật ký lỗi (lỗi mới/level mới).
  onCompleted: () => void;
}

export const AdaptiveQuizPanel: React.FC<AdaptiveQuizPanelProps> = ({ onCompleted }) => {
  const [quiz, setQuiz] = useState<AdaptiveQuiz | null>(null);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [result, setResult] = useState<AdaptiveQuizResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const showError = (caught: unknown) => {
    const message = caught instanceof Error ? caught.message : "";
    setError(ERROR_MESSAGES[message] ?? (message || "Something went wrong."));
  };

  const start = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const created = await generateAdaptiveQuiz(null, 5);
      setQuiz(created);
      setAnswers(created.questions.map(() => null));
    } catch (caught) {
      showError(caught);
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    if (!quiz || answers.some((answer) => answer === null)) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await submitAdaptiveQuiz(quiz.quiz_id, answers as number[]));
      onCompleted();
    } catch (caught) {
      showError(caught);
    } finally {
      setBusy(false);
    }
  };

  const allAnswered = answers.length > 0 && answers.every((answer) => answer !== null);

  return (
    <div className="surface p-7 space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-display text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-amber-500" /> Practice your weak spots
        </h3>
        <button
          onClick={start}
          disabled={busy}
          className="px-4 py-2 bg-indigo-700 hover:bg-indigo-800 disabled:opacity-60 text-white font-bold text-sm rounded-2xl flex items-center gap-2 cursor-pointer"
        >
          {busy && !quiz ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          {quiz ? "New quiz" : "Generate quiz"}
        </button>
      </div>

      {error && (
        <p role="alert" className="text-sm text-rose-700 bg-rose-50 rounded-xl px-4 py-3">
          {error}
        </p>
      )}

      {!quiz && !error && (
        <p className="text-sm text-slate-500">
          A short quiz built from the mistakes you made most often and most recently.
        </p>
      )}

      {quiz && (
        <div className="space-y-6">
          {quiz.questions.map((question, index) => {
            const graded = result?.results[index];
            return (
              <fieldset key={index} className="space-y-2" disabled={busy || result !== null}>
                <legend className="text-sm font-semibold text-slate-800 flex items-start gap-2">
                  <span className="num text-slate-400">{index + 1}.</span>
                  <span>{question.question_text}</span>
                  <span className="tag bg-rose-100 text-rose-700 ml-auto shrink-0">{question.error_type}</span>
                </legend>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {question.options.map((option, optionIndex) => {
                    const chosen = answers[index] === optionIndex;
                    const isCorrect = graded && graded.correct_option_index === optionIndex;
                    const isWrongChoice = graded && chosen && !graded.is_correct;
                    return (
                      <label
                        key={optionIndex}
                        className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm cursor-pointer transition-colors ${
                          isCorrect
                            ? "border-emerald-400 bg-emerald-50 text-emerald-900"
                            : isWrongChoice
                              ? "border-rose-400 bg-rose-50 text-rose-900"
                              : chosen
                                ? "border-indigo-500 bg-indigo-50"
                                : "border-slate-200 hover:bg-slate-50"
                        }`}
                      >
                        <input
                          type="radio"
                          name={`question-${index}`}
                          checked={chosen}
                          onChange={() => setAnswers(answers.map((value, i) => (i === index ? optionIndex : value)))}
                          className="accent-indigo-700"
                        />
                        {option}
                      </label>
                    );
                  })}
                </div>
                {graded && (
                  <p className={`text-xs flex items-start gap-1.5 ${graded.is_correct ? "text-emerald-700" : "text-rose-700"}`}>
                    {graded.is_correct ? (
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 shrink-0" />
                    )}
                    {graded.explanation}
                  </p>
                )}
              </fieldset>
            );
          })}

          {result ? (
            <p className="text-sm font-bold text-slate-900">
              Score: <span className="num">{Math.round(result.score)}%</span>
            </p>
          ) : (
            <button
              onClick={submit}
              disabled={!allAnswered || busy}
              className="px-5 py-2.5 bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl cursor-pointer"
            >
              {busy ? "Checking…" : "Submit answers"}
            </button>
          )}
        </div>
      )}
    </div>
  );
};
