// Mini-game (tài liệu tính năng mục V.1): Daily Wordle + Flip Memory Match. Chấm/XP ở backend (/api/games/*).
import React, { useEffect, useRef, useState } from "react";
import { BubblePop, DictationRacer, VoiceRunner, WordChain, WordRain, WordSearch } from "./games/WordGames";
import { GrammarDetective, SpeedQuiz } from "./games/QuizGames";
import { WordleCell, completeMemoryMatch, getWordleStatus, guessWordle, listVocabTopics } from "../api";

const CELL_STYLE: Record<WordleCell | "empty", string> = {
  correct: "bg-emerald-500 text-white border-emerald-500",
  present: "bg-amber-400 text-white border-amber-400",
  absent: "bg-slate-400 text-white border-slate-400",
  empty: "bg-white text-slate-900 border-slate-300",
};

interface Row { letters: string; pattern: WordleCell[] }

const Wordle: React.FC = () => {
  const [rows, setRows] = useState<Row[]>([]);
  const [input, setInput] = useState("");
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [solved, setSolved] = useState(false);
  const [solvedBefore, setSolvedBefore] = useState(false);
  const [busy, setBusy] = useState(false);
  const maxGuesses = 6;

  useEffect(() => {
    getWordleStatus().then((s) => setSolvedBefore(s.solved_today)).catch(() => {});
  }, []);

  const finished = solved || answer !== null;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy || finished || input.length !== 5) return;
    setBusy(true);
    setMessage("");
    try {
      const r = await guessWordle(input.toLowerCase(), rows.length + 1);
      setRows((prev) => [...prev, { letters: input.toLowerCase(), pattern: r.pattern }]);
      setInput("");
      setSolved(r.solved);
      setAnswer(r.answer);
      if (r.solved) setMessage(r.xp_awarded ? `Solved! +${r.xp_awarded} XP` : "Solved! (XP already earned today)");
      else if (r.answer) setMessage(`Out of guesses. The word was "${r.answer}".`);
    } catch (err) {
      setMessage((err as Error).message === "not_in_word_list" ? "Not in word list." : (err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">
        Guess today's 5-letter word in {maxGuesses} tries.{solvedBefore && " You already solved today's word."}
      </p>
      <div className="grid gap-1.5 w-fit" role="grid" aria-label="Wordle board">
        {Array.from({ length: maxGuesses }, (_, r) => (
          <div key={r} className="flex gap-1.5" role="row">
            {Array.from({ length: 5 }, (_, c) => {
              const row = rows[r];
              const style = row ? CELL_STYLE[row.pattern[c]] : CELL_STYLE.empty;
              return (
                <div
                  key={c}
                  role="gridcell"
                  aria-label={row ? `${row.letters[c]} ${row.pattern[c]}` : "empty"}
                  className={`w-11 h-11 border-2 rounded-lg flex items-center justify-center text-lg font-bold uppercase ${style}`}
                >
                  {row ? row.letters[c] : r === rows.length ? input[c] ?? "" : ""}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <input
          name="wordle_guess"
          value={input}
          onChange={(e) => setInput(e.target.value.replace(/[^a-zA-Z]/g, "").slice(0, 5))}
          disabled={finished}
          maxLength={5}
          autoComplete="off"
          aria-label="Your guess"
          className="field uppercase tracking-widest w-32"
        />
        <button type="submit" disabled={busy || finished || input.length !== 5} className="btn-primary">
          Guess
        </button>
      </form>
      {message && <p className="text-sm font-medium text-slate-800" role="status">{message}</p>}
    </div>
  );
};

interface Card { id: number; pair: number; text: string }

const shuffle = <T,>(items: T[]) => [...items].sort(() => Math.random() - 0.5);

const MemoryMatch: React.FC = () => {
  const [cards, setCards] = useState<Card[]>([]);
  const [open, setOpen] = useState<number[]>([]);
  const [matched, setMatched] = useState<Set<number>>(new Set());
  const [moves, setMoves] = useState(0);
  const [xp, setXp] = useState<number | null>(null);
  const [error, setError] = useState("");
  const lock = useRef(false);

  const start = async () => {
    setError("");
    try {
      const topics = (await listVocabTopics()).filter((t) => t.words.length >= 6);
      const topic = topics[Math.floor(Math.random() * topics.length)];
      const words = shuffle(topic.words).slice(0, 6);
      setCards(shuffle(words.flatMap((w, i) => [{ id: i * 2, pair: i, text: w.term }, { id: i * 2 + 1, pair: i, text: w.meaning_vi }])));
      setOpen([]);
      setMatched(new Set());
      setMoves(0);
      setXp(null);
    } catch (err) {
      setError((err as Error).message);
    }
  };
  useEffect(() => {
    void start();
  }, []);

  const flip = (index: number) => {
    const card = cards[index];
    if (lock.current || open.includes(index) || matched.has(card.pair)) return;
    const next = [...open, index];
    setOpen(next);
    if (next.length < 2) return;
    const total = moves + 1;
    setMoves(total);
    const [a, b] = next.map((i) => cards[i]);
    if (a.pair === b.pair) {
      const done = new Set(matched).add(a.pair);
      setMatched(done);
      setOpen([]);
      if (done.size === cards.length / 2) {
        completeMemoryMatch(done.size, total)
          .then((r) => setXp(r.xp_awarded))
          .catch((err) => setError((err as Error).message));
      }
    } else {
      lock.current = true;
      setTimeout(() => {
        setOpen([]);
        lock.current = false;
      }, 800);
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">Match each English word with its Vietnamese meaning. Moves: <b>{moves}</b></p>
      <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
        {cards.map((card, i) => {
          const faceUp = open.includes(i) || matched.has(card.pair);
          return (
            <button
              key={card.id}
              onClick={() => flip(i)}
              aria-label={faceUp ? card.text : "Hidden card"}
              className={`h-16 px-1 rounded-xl border-2 text-sm font-semibold transition-colors ${
                matched.has(card.pair)
                  ? "bg-emerald-100 border-emerald-400 text-emerald-800"
                  : faceUp
                  ? "bg-white border-indigo-400 text-slate-900"
                  : "bg-indigo-600 border-indigo-700 text-white hover:bg-indigo-500"
              }`}
            >
              {faceUp ? card.text : "?"}
            </button>
          );
        })}
      </div>
      {xp !== null && (
        <p className="text-sm font-medium text-emerald-700" role="status">
          All pairs found in {moves} moves! {xp ? `+${xp} XP` : "(daily XP limit reached)"}
        </p>
      )}
      {error && <p className="text-sm text-rose-700" role="alert">{error}</p>}
      <button onClick={start} className="btn-primary">New game</button>
    </div>
  );
};

const GAMES = [
  { id: "wordle", label: "Daily Wordle", Component: Wordle },
  { id: "memory", label: "Memory Match", Component: MemoryMatch },
  { id: "rain", label: "Word Rain", Component: WordRain },
  { id: "bubble", label: "Bubble Pop", Component: BubblePop },
  { id: "search", label: "Word Search", Component: WordSearch },
  { id: "chain", label: "Word Chain", Component: WordChain },
  { id: "detective", label: "Grammar Detective", Component: GrammarDetective },
  { id: "racer", label: "Dictation Racer", Component: DictationRacer },
  { id: "voice", label: "Voice Runner", Component: VoiceRunner },
  { id: "duel", label: "1v1 Speed Quiz", Component: SpeedQuiz },
] as const;

export const MiniGamesCard: React.FC = () => {
  const [game, setGame] = useState<(typeof GAMES)[number]["id"]>("wordle");
  const Active = GAMES.find((g) => g.id === game)!.Component;
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return (
    <section className="pop-in surface p-6 space-y-4 h-full" aria-label="Mini-games">
      <h3 className="font-display text-xl font-bold text-slate-900">Mini-games</h3>
      {!online && (
        <p className="text-sm text-amber-800 bg-amber-50 rounded-lg px-3 py-2" role="status">
          You are offline. Games that use saved words still work; XP and coins sync only when you are back online.
        </p>
      )}
      <div className="flex flex-wrap gap-1.5" role="tablist">
        {GAMES.map((g) => (
          <button
            key={g.id}
            role="tab"
            aria-selected={game === g.id}
            onClick={() => setGame(g.id)}
            className={`tag cursor-pointer ${game === g.id ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600"}`}
          >
            {g.label}
          </button>
        ))}
      </div>
      <Active key={game} />
    </section>
  );
};
