// Giả lập IELTS Speaking 3 phần (backlog 2.3): Part 1 hỏi nhanh, Part 2 cue card (1 phút chuẩn bị,
// tối đa 2 phút nói), Part 3 thảo luận. Mỗi câu ghi âm -> STT + phát âm; cuối bài ước lượng band.
import React, { useEffect, useRef, useState } from "react";
import { Loader2, Mic, Square } from "lucide-react";
import {
  createIeltsExam,
  estimateIelts,
  listIeltsAttempts,
  IeltsAnswer,
  IeltsAttempt,
  IeltsEstimate,
  IeltsExam,
  sendIeltsAnswer,
} from "../api";
import { startWavRecording, WavRecording } from "../wavRecorder";

interface Step {
  part: 1 | 2 | 3;
  question: string;
  bullets?: string[];
}

type Answered = Step & IeltsAnswer;

const buildSteps = (exam: IeltsExam): Step[] => [
  ...exam.part1_questions.map((question) => ({ part: 1 as const, question })),
  { part: 2, question: exam.cue_card.topic, bullets: exam.cue_card.bullets },
  ...exam.part3_questions.map((question) => ({ part: 3 as const, question })),
];

const BANDS: Array<[keyof IeltsEstimate, string]> = [
  ["fluency_coherence", "Fluency & Coherence"],
  ["lexical_resource", "Lexical Resource"],
  ["grammatical_range", "Grammatical Range"],
  ["pronunciation", "Pronunciation"],
];

export const IeltsPanel: React.FC = () => {
  const [topic, setTopic] = useState("");
  const [steps, setSteps] = useState<Step[]>([]);
  const [prepSeconds, setPrepSeconds] = useState(60);
  const [speakSeconds, setSpeakSeconds] = useState(120);
  const [answers, setAnswers] = useState<Answered[]>([]);
  const [prepLeft, setPrepLeft] = useState(0);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState(false);
  const [estimate, setEstimate] = useState<IeltsEstimate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<IeltsAttempt[]>([]);
  const recordingRef = useRef<WavRecording | null>(null);
  const startedAtRef = useRef(0);

  const current = steps[answers.length];
  const isPart2 = current?.part === 2;

  // Vào Part 2 -> bắt đầu đếm ngược chuẩn bị.
  useEffect(() => {
    if (isPart2) setPrepLeft(prepSeconds);
  }, [isPart2, prepSeconds]);

  useEffect(() => {
    if (prepLeft <= 0) return;
    const id = window.setTimeout(() => setPrepLeft((value) => value - 1), 1000);
    return () => window.clearTimeout(id);
  }, [prepLeft]);

  useEffect(() => {
    if (!recording) return;
    const id = window.setInterval(() => setElapsed(Math.round((Date.now() - startedAtRef.current) / 1000)), 500);
    return () => window.clearInterval(id);
  }, [recording]);

  // Part 2 tự dừng khi hết thời gian nói.
  useEffect(() => {
    if (recording && isPart2 && elapsed >= speakSeconds) void toggleRecording();
  }, [elapsed]);

  useEffect(() => () => recordingRef.current?.cancel(), []);

  const loadHistory = () => {
    listIeltsAttempts().then(setHistory).catch(() => undefined);
  };
  useEffect(loadHistory, []);

  const startExam = async () => {
    setBusy(true);
    setError(null);
    setEstimate(null);
    setAnswers([]);
    try {
      const exam = await createIeltsExam(topic.trim());
      setSteps(buildSteps(exam));
      setPrepSeconds(exam.part2_prep_seconds);
      setSpeakSeconds(exam.part2_speak_seconds);
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Could not create the exam.");
    } finally {
      setBusy(false);
    }
  };

  const finish = async (all: Answered[]) => {
    try {
      setEstimate(
        await estimateIelts(
          all.map(({ part, question, transcript, pronunciation_score, words_per_minute }) => ({
            part,
            question,
            transcript,
            pronunciation_score,
            words_per_minute,
          })),
          topic.trim(),
        ),
      );
      loadHistory();
    } catch (estimateError) {
      setError(estimateError instanceof Error ? estimateError.message : "Could not estimate your band.");
    }
  };

  const toggleRecording = async () => {
    if (recording) {
      const recorder = recordingRef.current;
      recordingRef.current = null;
      setRecording(false);
      const blob = await recorder?.stop();
      if (!blob || !current) return;
      const seconds = Math.round((Date.now() - startedAtRef.current) / 1000);
      setBusy(true);
      try {
        const result = await sendIeltsAnswer(blob, seconds);
        const next = [...answers, { ...current, ...result }];
        setAnswers(next);
        if (next.length === steps.length) await finish(next);
      } catch (sendError) {
        const message = sendError instanceof Error ? sendError.message : "";
        setError(message.includes("empty_transcription") ? "I could not hear any words. Record this question again." : message || "Something went wrong.");
      } finally {
        setBusy(false);
      }
      return;
    }
    if (busy || !current) return;
    setError(null);
    try {
      recordingRef.current = await startWavRecording();
      startedAtRef.current = Date.now();
      setElapsed(0);
      setRecording(true);
      setPrepLeft(0);
    } catch {
      setError("Microphone unavailable. Allow microphone access in your browser and try again.");
    }
  };

  const measured = answers.filter((item) => item.words_per_minute !== null);
  const pace = measured.length
    ? Math.round(measured.reduce((sum, item) => sum + (item.words_per_minute ?? 0), 0) / measured.length)
    : null;

  return (
    <div className="surface p-7 space-y-5">
      <div>
        <h3 className="font-display text-2xl font-bold text-slate-900">IELTS Speaking mock test</h3>
        <p className="text-sm text-slate-500">3 parts, about 10 minutes. The band is an AI estimate for practice, not an official score.</p>
      </div>
      {error && <p className="text-xs text-red-600 bg-red-50 rounded-xl px-3 py-2">{error}</p>}

      {(!current || estimate) && !busy && (
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            placeholder="Theme (optional), e.g. travel"
            maxLength={80}
            className="flex-1 px-4 py-2.5 text-sm bg-white ring-1 ring-slate-900/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
          />
          <button
            onClick={startExam}
            disabled={busy}
            className="px-5 py-2.5 bg-indigo-700 hover:bg-indigo-800 text-white text-sm font-bold rounded-xl disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {busy && <Loader2 className="w-4 h-4 animate-spin" />} {estimate ? "New test" : "Start test"}
          </button>
        </div>
      )}

      {current && !estimate && (
        <div className="space-y-4">
          <p className="text-xs font-bold text-indigo-700">
            Part {current.part} · question {answers.length + 1} of {steps.length}
          </p>
          <p className="text-lg font-serif text-slate-900">{current.question}</p>
          {current.bullets && (
            <ul className="list-disc ml-5 text-sm text-slate-700">
              {current.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}
            </ul>
          )}
          {isPart2 && !recording && prepLeft > 0 && (
            <p className="num text-sm text-amber-700">Preparation: {prepLeft}s (you can start speaking any time)</p>
          )}
          {recording && (
            <p className="num text-sm text-rose-600">
              Recording {elapsed}s{isPart2 ? ` / ${speakSeconds}s` : ""}
            </p>
          )}
          <button
            onClick={toggleRecording}
            disabled={busy}
            className={`px-5 py-3 text-sm font-bold rounded-xl text-white disabled:opacity-50 flex items-center gap-2 ${recording ? "bg-rose-600" : "bg-slate-900 hover:bg-slate-800"}`}
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : recording ? <Square className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            {busy ? "Processing..." : recording ? "Stop" : "Record answer"}
          </button>
        </div>
      )}

      {!current && steps.length > 0 && !estimate && !error && (
        <p className="text-sm text-slate-500">Estimating your band...</p>
      )}

      {estimate && (
        <div className="space-y-4 animate-rise">
          <p className="num text-5xl font-bold text-slate-900">
            Band {estimate.overall.toFixed(1)}
            {estimate.previous_overall !== null && estimate.overall !== estimate.previous_overall && (
              <span className={`ml-3 text-lg ${estimate.overall > estimate.previous_overall ? "text-emerald-600" : "text-rose-600"}`}>
                {estimate.overall > estimate.previous_overall ? "▲" : "▼"} {Math.abs(estimate.overall - estimate.previous_overall).toFixed(1)} vs last test
              </span>
            )}
          </p>
          <div className="grid grid-cols-2 gap-3">
            {BANDS.map(([key, label]) => (
              <div key={key} className="p-3 rounded-2xl bg-paper-deep/70">
                <p className="text-xs text-slate-500">{label}</p>
                <p className="num text-xl font-bold text-slate-900">
                  {estimate[key] === null ? "—" : (estimate[key] as number).toFixed(1)}
                </p>
              </div>
            ))}
          </div>
          <p className="text-sm text-slate-700 leading-relaxed">{estimate.feedback_vi}</p>
          {pace !== null && <p className="text-xs text-slate-500">Speaking pace: {pace} words/min</p>}
        </div>
      )}

      {history.length > 0 && (
        <div className="space-y-2 pt-2">
          <p className="text-sm italic text-slate-500">Your past tests</p>
          {history.map((item) => (
            <details key={item.id} className="rounded-2xl bg-paper-deep/60 px-4 py-3 text-sm">
              <summary className="cursor-pointer flex items-baseline justify-between gap-3">
                <span className="text-slate-700">
                  {new Date(item.created_at).toLocaleDateString()} {item.topic ? `· ${item.topic}` : ""}
                </span>
                <span className="num font-bold text-slate-900">Band {item.overall.toFixed(1)}</span>
              </summary>
              <p className="num text-xs text-slate-500 mt-2">
                Fluency {item.fluency_coherence.toFixed(1)} · Lexical {item.lexical_resource.toFixed(1)} · Grammar{" "}
                {item.grammatical_range.toFixed(1)}
                {item.pronunciation !== null ? ` · Pronunciation ${item.pronunciation.toFixed(1)}` : ""}
                {item.words_per_minute ? ` · ${item.words_per_minute} words/min` : ""}
              </p>
              <p className="text-slate-700 mt-2 leading-relaxed">{item.feedback_vi}</p>
            </details>
          ))}
        </div>
      )}
    </div>
  );
};
