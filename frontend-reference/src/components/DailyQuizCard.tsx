// Quiz nhanh 1 câu từ - nghĩa (cùng backend với quiz trong popup extension): đúng +3 XP, tối đa 5 câu đúng/ngày có XP.
import React, { useCallback, useEffect, useState } from "react";
import { answerMicroQuiz, getMicroQuiz } from "../api";

export const DailyQuizCard: React.FC = () => {
  const [quiz, setQuiz] = useState<{ prompt: string; options: string[] } | null>(null);
  const [result, setResult] = useState<{ correct: boolean; answer: string; xp_awarded: number } | null>(null);
  const [streak, setStreak] = useState(0);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setResult(null);
    setError("");
    try {
      setQuiz(await getMicroQuiz());
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const answer = async (choice: string) => {
    if (!quiz || result) return;
    try {
      const r = await answerMicroQuiz(quiz.prompt, choice);
      setResult(r);
      setStreak((s) => (r.correct ? s + 1 : 0));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <section className="pop-in surface p-6 space-y-4" aria-label="Quick quiz">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-xl font-bold text-slate-900">Quick quiz</h3>
        <span className="tag bg-purple-100 text-purple-700 shrink-0">+3 XP per correct answer</span>
      </div>
      {quiz && (
        <>
          <p className="text-2xl font-bold font-display" aria-label="Word to match">{quiz.prompt}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {quiz.options.map((option) => (
              <button
                key={option}
                onClick={() => answer(option)}
                disabled={!!result}
                className={`px-3 py-2.5 rounded-xl border-2 text-sm font-semibold text-left transition-colors ${
                  result
                    ? option === result.answer
                      ? "bg-emerald-100 border-emerald-500"
                      : "opacity-60 border-slate-200"
                    : "bg-white border-slate-300 hover:bg-slate-50"
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </>
      )}
      {result && (
        <div className="flex flex-wrap items-center gap-3" role="status">
          <p className="text-sm font-medium">
            {result.correct ? `Correct! ${result.xp_awarded ? `+${result.xp_awarded} XP` : "(daily XP limit reached)"}` : `Not quite. Answer: ${result.answer}`}
            {streak > 1 && ` · ${streak} in a row`}
          </p>
          <button onClick={load} className="btn-primary">Next question</button>
        </div>
      )}
      {error && <p className="text-sm text-rose-700" role="alert">{error}</p>}
    </section>
  );
};
