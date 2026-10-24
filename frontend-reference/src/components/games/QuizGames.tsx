// Mini-game đố/đối kháng: Grammar Detective (tìm lỗi ngữ pháp ẩn) và 1v1 Speed Quiz (WebSocket, ghép cặp online).
import React, { useEffect, useRef, useState } from "react";
import { DetectivePassage, DetectiveResult, checkGrammarDetective, getGrammarDetective, speedQuizUrl } from "../../api";

const BTN = "btn-primary";

export const GrammarDetective: React.FC = () => {
  const [passage, setPassage] = useState<DetectivePassage | null>(null);
  const [picks, setPicks] = useState<Set<number>>(new Set());
  const [result, setResult] = useState<DetectiveResult | null>(null);
  const [err, setErr] = useState("");

  const load = async (exclude?: number) => {
    setErr("");
    setResult(null);
    setPicks(new Set());
    try {
      setPassage(await getGrammarDetective(exclude));
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  useEffect(() => {
    void load();
  }, []);

  const toggle = (index: number) => {
    if (result) return;
    setPicks((p) => {
      const next = new Set(p);
      if (!next.delete(index)) next.add(index);
      return next;
    });
  };

  const check = async () => {
    if (!passage) return;
    try {
      setResult(await checkGrammarDetective(passage.passage_id, [...picks]));
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  if (!passage) return err ? <p className="text-sm text-rose-700" role="alert">{err}</p> : <p className="text-sm text-slate-500">Loading…</p>;
  const wrongIndexes = new Set(result?.answers.map((a) => a.index));
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">
        This text hides <b>{passage.error_count}</b> grammar mistakes. Click the wrong words, then check. Find 60% with at most one wrong click for XP.
      </p>
      <p className="leading-loose" aria-label="Passage">
        {passage.tokens.map((token, i) => {
          const selected = picks.has(i);
          const style = result
            ? wrongIndexes.has(i)
              ? selected ? "bg-emerald-200" : "bg-rose-200"
              : selected ? "bg-amber-200 line-through" : ""
            : selected ? "bg-amber-200" : "hover:bg-slate-200";
          return (
            <React.Fragment key={i}>
              <span role="button" aria-pressed={selected} onClick={() => toggle(i)} className={`cursor-pointer rounded px-0.5 ${style}`}>
                {token}
              </span>{" "}
            </React.Fragment>
          );
        })}
      </p>
      {result ? (
        <div className="space-y-1" role="status">
          <p className="text-sm font-medium">
            Found {result.found}/{result.total}, wrong clicks {result.false_positives}.{" "}
            {result.xp_awarded ? `+${result.xp_awarded} XP!` : "Try again for XP."}
          </p>
          <ul className="text-sm list-disc ml-5">
            {result.answers.map((a) => (
              <li key={a.index}>
                <s>{a.wrong}</s> → <b>{a.correct}</b>
              </li>
            ))}
          </ul>
          <button onClick={() => load(passage.passage_id)} className={BTN}>Next text</button>
        </div>
      ) : (
        <button onClick={check} disabled={picks.size === 0} className={BTN}>Check my answers</button>
      )}
      {err && <p className="text-sm text-rose-700" role="alert">{err}</p>}
    </div>
  );
};

interface QuizQuestion { prompt: string; options: string[] }
type Phase = "idle" | "waiting" | "playing" | "done";

export const SpeedQuiz: React.FC = () => {
  const [phase, setPhase] = useState<Phase>("idle");
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [i, setI] = useState(0);
  const [feedback, setFeedback] = useState<{ correct: boolean; answer: string } | null>(null);
  const [opponent, setOpponent] = useState({ answered: 0, score: 0 });
  const [myScore, setMyScore] = useState(0);
  const [result, setResult] = useState<{ result: string; you: number; opponent: number; xp_awarded: number; forfeit: boolean } | null>(null);
  const [err, setErr] = useState("");
  const socket = useRef<WebSocket | null>(null);

  useEffect(() => () => socket.current?.close(), []);

  const join = () => {
    setErr("");
    setResult(null);
    setI(0);
    setMyScore(0);
    setOpponent({ answered: 0, score: 0 });
    setFeedback(null);
    const ws = new WebSocket(speedQuizUrl());
    socket.current = ws;
    setPhase("waiting");
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "start") {
        setQuestions(msg.questions);
        setPhase("playing");
      } else if (msg.type === "feedback") {
        setFeedback({ correct: msg.correct, answer: msg.answer });
        if (msg.correct) setMyScore((s) => s + 1);
        window.setTimeout(() => {
          setFeedback(null);
          setI((n) => n + 1);
        }, 700);
      } else if (msg.type === "opponent_progress") {
        setOpponent({ answered: msg.answered, score: msg.score });
      } else if (msg.type === "result") {
        setResult(msg);
        setPhase("done");
      } else if (msg.type === "error") {
        setErr(msg.code === "already_in_queue" ? "You are already in a match or queue (another tab?)." : msg.code);
        setPhase("idle");
      }
    };
    ws.onerror = () => {
      setErr("Could not connect to the match server.");
      setPhase("idle");
    };
    ws.onclose = () => setPhase((p) => (p === "waiting" ? "idle" : p));
  };

  const answer = (choice: string) => {
    if (feedback) return;
    socket.current?.send(JSON.stringify({ type: "answer", q: i, choice }));
  };

  const leave = () => {
    socket.current?.close();
    setPhase("idle");
  };

  const finishedAll = phase === "playing" && i >= questions.length;
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">Race another learner on 5 vocabulary questions. Most correct answers wins (+12 XP, +6 for playing).</p>
      {phase === "idle" && <button onClick={join} className={BTN}>Find an opponent</button>}
      {phase === "waiting" && (
        <div className="space-y-2" role="status">
          <p className="text-sm">Waiting for an opponent… (open Lumina in another browser/account to match)</p>
          <button onClick={leave} className="text-sm underline text-slate-600">Cancel</button>
        </div>
      )}
      {phase === "playing" && !finishedAll && (
        <div className="space-y-2">
          <p className="text-xs text-slate-500">
            Question {i + 1}/{questions.length} · You {myScore} · Opponent {opponent.score} ({opponent.answered}/{questions.length} answered)
          </p>
          <p className="text-xl font-bold font-display" aria-label="Word to match">{questions[i].prompt}</p>
          <div className="grid grid-cols-2 gap-2">
            {questions[i].options.map((o) => (
              <button
                key={o}
                onClick={() => answer(o)}
                className={`min-h-14 px-3 py-2 rounded-xl border-2 text-sm font-semibold ${
                  feedback ? (o === feedback.answer ? "bg-emerald-100 border-emerald-500" : "opacity-60 border-slate-200") : "bg-white border-slate-300 hover:bg-slate-50"
                }`}
              >
                {o}
              </button>
            ))}
          </div>
        </div>
      )}
      {finishedAll && <p className="text-sm" role="status">All answered. Waiting for your opponent to finish…</p>}
      {phase === "done" && result && (
        <div className="space-y-2" role="status">
          <p className="text-lg font-bold">{result.result === "win" ? "You win! 🎉" : result.result === "draw" ? "Draw" : "You lose"}</p>
          <p className="text-sm">
            {result.you} - {result.opponent}
            {result.forfeit ? " (opponent left)" : ""} · {result.xp_awarded ? `+${result.xp_awarded} XP` : "no XP (daily limit)"}
          </p>
          <button onClick={join} className={BTN}>Play again</button>
        </div>
      )}
      {err && <p className="text-sm text-rose-700" role="alert">{err}</p>}
    </div>
  );
};
