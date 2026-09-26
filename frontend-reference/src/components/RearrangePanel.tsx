// Rearrange the Block: sắp xếp lại các khối câu (Reading) hoặc cụm ngữ pháp (Writing) bị xáo
// trộn. Kéo-thả hoặc dùng nút ▲▼ (bàn phím được) để đổi chỗ; thứ tự chuẩn chỉ hiện sau khi nộp.
// Sinh đề và chấm điểm chạy trên Ollama local nên có thể mất vài giây (lần đầu tới ~1 phút khi model
// đang nạp): panel hiện tiến trình + số giây thay vì im lặng, và mọi lỗi đều có nút thử lại.
import React, { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Bot, CheckCircle2, GripVertical, Loader2, Shuffle, XCircle } from "lucide-react";
import {
  RearrangeAttempt,
  RearrangeBlock,
  RearrangeResult,
  RearrangeSkill,
  createRearrange,
  submitRearrange,
} from "../api";
import { ErrorNotice } from "./ErrorNotice";

const COPY: Record<RearrangeSkill, { title: string; hint: string }> = {
  reading: {
    title: "Rearrange the paragraph",
    hint: "Put the sentences back in a logical order. Built from passages and mistakes from your reading.",
  },
  writing: {
    title: "Rearrange the sentence",
    hint: "Put the phrases back into a correct English sentence. Built from your grammar mistakes.",
  },
};

type Action = "start" | "submit";

// Đếm giây kể từ khi bắt đầu chờ (0 khi không bận) để người dùng biết hệ thống vẫn đang chạy.
function useElapsedSeconds(active: boolean) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!active) {
      setSeconds(0);
      return;
    }
    const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  return seconds;
}

interface RearrangePanelProps {
  skill: RearrangeSkill;
}

export const RearrangePanel: React.FC<RearrangePanelProps> = ({ skill }) => {
  const [attempt, setAttempt] = useState<RearrangeAttempt | null>(null);
  const [order, setOrder] = useState<RearrangeBlock[]>([]);
  const [result, setResult] = useState<RearrangeResult | null>(null);
  const [busyAction, setBusyAction] = useState<Action | null>(null);
  const [error, setError] = useState<{ cause: unknown; action: Action } | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const waited = useElapsedSeconds(busyAction !== null);

  const busy = busyAction !== null;

  const start = async () => {
    setBusyAction("start");
    setError(null);
    // Bỏ bài cũ ngay: nếu lần sinh này lỗi, bài đã nộp không được hiện lại như thể còn làm được.
    setAttempt(null);
    setOrder([]);
    setResult(null);
    try {
      const created = await createRearrange(skill);
      setAttempt(created);
      setOrder(created.blocks);
    } catch (cause) {
      setError({ cause, action: "start" });
    } finally {
      setBusyAction(null);
    }
  };

  const submit = async () => {
    if (!attempt) return;
    setBusyAction("submit");
    setError(null);
    try {
      setResult(await submitRearrange(skill, attempt.attempt_id, order.map((block) => block.id)));
    } catch (cause) {
      setError({ cause, action: "submit" });
    } finally {
      setBusyAction(null);
    }
  };

  const move = (from: number, to: number) => {
    if (result || busy || to < 0 || to >= order.length || from === to) return;
    const next = [...order];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    setOrder(next);
  };

  const locked = busy || result !== null;
  // Sau khi nộp: đối chiếu từng vị trí với thứ tự chuẩn (hoặc thứ tự Ollama đã chấp nhận).
  const isPlacedRight = (index: number) => result !== null && result.correct_order[index] === order[index].id;
  const textById = new Map(order.map((block) => [block.id, block.text]));

  return (
    <div className="surface p-7 space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-display text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Shuffle className="w-6 h-6 text-indigo-600" /> {COPY[skill].title}
        </h3>
        <button
          onClick={start}
          disabled={busy}
          className="px-4 py-2 bg-indigo-700 hover:bg-indigo-800 disabled:opacity-60 text-white font-bold text-sm rounded-2xl flex items-center gap-2 cursor-pointer"
        >
          {busyAction === "start" ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          {attempt ? "New exercise" : "Start exercise"}
        </button>
      </div>

      {busyAction === "start" && (
        <p role="status" className="text-sm text-slate-600 flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
          Preparing your exercise… <span className="num">{waited}s</span>
          {waited >= 10 && (
            <span className="text-slate-500">The local AI may be waking up — the first exercise can take up to a minute.</span>
          )}
        </p>
      )}

      {error && (
        <ErrorNotice
          error={error.cause}
          onRetry={error.action === "start" ? start : submit}
          retryLabel={error.action === "start" ? "Try again" : "Check again"}
        />
      )}

      {!attempt && !error && !busy && <p className="text-sm text-slate-500">{COPY[skill].hint}</p>}

      {attempt && (
        <div className="space-y-4">
          <ol className="space-y-2" aria-label="Blocks to arrange">
            {order.map((block, index) => (
              <li
                key={block.id}
                draggable={!locked}
                onDragStart={() => setDragIndex(index)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => {
                  if (dragIndex !== null) move(dragIndex, index);
                  setDragIndex(null);
                }}
                onDragEnd={() => setDragIndex(null)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl border text-sm transition-colors ${
                  result
                    ? isPlacedRight(index)
                      ? "border-emerald-400 bg-emerald-50 text-emerald-900"
                      : "border-rose-400 bg-rose-50 text-rose-900"
                    : dragIndex === index
                      ? "border-indigo-500 bg-indigo-50 opacity-60"
                      : "border-slate-200 bg-white"
                }`}
              >
                <GripVertical className={`w-4 h-4 shrink-0 ${locked ? "text-slate-200" : "text-slate-400 cursor-grab"}`} />
                <span className="num text-slate-400 w-5 shrink-0">{index + 1}.</span>
                <span className="flex-1">{block.text}</span>
                {result ? (
                  isPlacedRight(index) ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
                  ) : (
                    <XCircle className="w-4 h-4 shrink-0 text-rose-600" />
                  )
                ) : (
                  <span className="flex gap-1 shrink-0">
                    <button
                      onClick={() => move(index, index - 1)}
                      disabled={locked || index === 0}
                      aria-label={`Move block ${index + 1} up`}
                      className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-30 cursor-pointer"
                    >
                      <ArrowUp className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => move(index, index + 1)}
                      disabled={locked || index === order.length - 1}
                      aria-label={`Move block ${index + 1} down`}
                      className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-30 cursor-pointer"
                    >
                      <ArrowDown className="w-4 h-4" />
                    </button>
                  </span>
                )}
              </li>
            ))}
          </ol>

          {result ? (
            <div className="space-y-3">
              <p className="text-sm font-bold text-slate-900">
                Score: <span className="num">{Math.round(result.score * 100)}%</span>
                {result.graded_by === "ollama" && (
                  <span className="tag bg-violet-100 text-violet-700 ml-2 inline-flex items-center gap-1">
                    <Bot className="w-3 h-3" /> Checked by Ollama
                  </span>
                )}
              </p>
              {result.explanation && <p className="text-sm text-slate-600 italic">{result.explanation}</p>}
              {result.score < 1 && (
                <p className="text-sm text-slate-700">
                  <span className="font-semibold">Correct order: </span>
                  {result.correct_order.map((id) => textById.get(id)).join(" ")}
                </p>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <button
                onClick={submit}
                disabled={busy}
                className="px-5 py-2.5 bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-bold text-sm rounded-2xl cursor-pointer flex items-center gap-2"
              >
                {busyAction === "submit" ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {busyAction === "submit" ? "Checking…" : "Check order"}
              </button>
              {busyAction === "submit" && (
                <span role="status" className="text-xs text-slate-500">
                  Ollama is reading your answer… <span className="num">{waited}s</span>
                  {waited >= 8 && " Almost there — this can take up to half a minute."}
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
