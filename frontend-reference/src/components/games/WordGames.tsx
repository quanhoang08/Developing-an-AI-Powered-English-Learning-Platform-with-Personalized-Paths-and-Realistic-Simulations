// Mini-game từ vựng/phát âm (tài liệu tính năng mục V.1, V.3): Word Rain, Bubble Pop, Word Search, Word Chain,
// Dictation Racer, Voice Runner. Điểm thưởng tính ở backend (/api/games/*), từ lấy từ kho chủ đề dùng chung.
import React, { useEffect, useRef, useState } from "react";
import { completeScoreGame, loseHeart, refillHearts, wordChainTurn } from "../../api";
import { GameWord, loadGameWords, pick, shuffle, useWallet } from "./shared";

const BTN = "btn-primary";

function useWords() {
  const [words, setWords] = useState<GameWord[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    loadGameWords().then(setWords).catch((e) => setError((e as Error).message));
  }, []);
  return { words, error };
}

// Gửi điểm khi ván kết thúc; trả thông điệp XP để hiển thị.
function useFinish(game: string, onError: (m: string) => void) {
  const [xp, setXp] = useState<number | null>(null);
  const finish = (score: number) => {
    completeScoreGame(game, score)
      .then((r) => setXp(r.xp_awarded))
      .catch((e) => {
        const code = (e as Error).message;
        if (code !== "score_too_low") onError(code);
      });
  };
  return { xp, finish, reset: () => setXp(null) };
}

const XpLine: React.FC<{ xp: number | null }> = ({ xp }) =>
  xp === null ? null : (
    <p className="text-sm font-medium text-emerald-700" role="status">
      {xp ? `+${xp} XP earned!` : "Nice run (no XP this time)."}
    </p>
  );

// ---- Tim: dùng chung cho game có thua (Word Rain, Bubble Pop) ----
const HeartsBar: React.FC<{ left: number; max: number }> = ({ left, max }) => (
  <span aria-label={`${left} hearts left`} className="text-rose-500 tracking-widest">
    {"♥".repeat(left)}
    <span className="text-slate-300">{"♥".repeat(Math.max(0, max - left))}</span>
  </span>
);

function useHearts() {
  const { wallet, reload } = useWallet();
  const [refillError, setRefillError] = useState("");
  const refill = async () => {
    setRefillError("");
    try {
      await refillHearts();
    } catch (e) {
      setRefillError((e as Error).message === "not_enough_coins" ? "Not enough coins." : (e as Error).message);
    }
    reload();
  };
  return {
    hearts: wallet?.hearts ?? 0,
    max: wallet?.max_hearts ?? 5,
    nextIn: wallet?.next_heart_in_seconds ?? null,
    loaded: wallet !== null,
    refill,
    refillError,
    cost: wallet?.heart_refill_cost ?? 20,
  };
}

const NoHearts: React.FC<{ h: ReturnType<typeof useHearts> }> = ({ h }) => (
  <div className="space-y-2" role="status">
    <p className="text-sm text-slate-700">
      You are out of hearts. One comes back every 30 minutes{h.nextIn !== null ? ` (next in ${Math.ceil(h.nextIn / 60)} min)` : ""}.
    </p>
    <button onClick={h.refill} className={BTN}>Refill for {h.cost} coins</button>
    {h.refillError && <p className="text-sm text-rose-700" role="alert">{h.refillError}</p>}
  </div>
);

// ---- Word Rain ----
interface Drop { id: number; text: string; left: number; top: number }

export const WordRain: React.FC = () => {
  const { words, error } = useWords();
  const h = useHearts();
  const [state, setState] = useState<"idle" | "playing" | "over">("idle");
  const [drops, setDrops] = useState<Drop[]>([]);
  const [score, setScore] = useState(0);
  const [lives, setLives] = useState(5);
  const [input, setInput] = useState("");
  const [err, setErr] = useState("");
  const fin = useFinish("word_rain", setErr);
  const ids = useRef(0);

  const start = () => {
    setDrops([]);
    setScore(0);
    setLives(h.hearts);
    setInput("");
    fin.reset();
    setState("playing");
  };

  useEffect(() => {
    if (state !== "playing" || !words) return;
    const pool = words.map((w) => w.term.toLowerCase()).filter((t) => /^[a-z]{3,8}$/.test(t));
    const spawn = window.setInterval(() => {
      setDrops((d) => [...d, { id: ++ids.current, text: pool[Math.floor(Math.random() * pool.length)], left: 5 + Math.random() * 75, top: 0 }]);
    }, 2200);
    const fall = window.setInterval(() => {
      setDrops((d) => d.map((x) => ({ ...x, top: x.top + 2.2 })));
    }, 120);
    return () => {
      window.clearInterval(spawn);
      window.clearInterval(fall);
    };
  }, [state, words]);

  // Từ chạm đáy = mất 1 tim (cả ở server); hết tim hoặc đủ 10 từ thì kết thúc.
  useEffect(() => {
    if (state !== "playing") return;
    const missed = drops.filter((d) => d.top >= 88);
    if (missed.length) {
      setDrops((d) => d.filter((x) => x.top < 88));
      missed.forEach(() => void loseHeart().catch(() => {}));
      setLives((l) => Math.max(0, l - missed.length));
    }
  }, [drops, state]);

  useEffect(() => {
    if (state === "playing" && (lives <= 0 || score >= 10)) {
      setState("over");
      fin.finish(score);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lives, score, state]);

  const type = (value: string) => {
    setInput(value);
    const hit = drops.find((d) => d.text === value.trim().toLowerCase());
    if (hit) {
      setDrops((d) => d.filter((x) => x.id !== hit.id));
      setScore((s) => s + 1);
      setInput("");
    }
  };

  if (error) return <p className="text-sm text-rose-700" role="alert">{error}</p>;
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">Type each falling word before it hits the bottom. A miss costs a heart. Score 5+ for XP.</p>
      <div className="flex items-center gap-3 text-sm">
        <HeartsBar left={state === "playing" ? lives : h.hearts} max={h.max} />
        <span>Score: <b>{score}</b></span>
      </div>
      <div className="relative h-56 rounded-xl bg-sky-50 border border-sky-200 overflow-hidden" aria-label="Word rain field">
        {drops.map((d) => (
          <span key={d.id} className="absolute px-2 py-0.5 rounded-full bg-white shadow text-sm font-semibold" style={{ left: `${d.left}%`, top: `${d.top}%` }}>
            {d.text}
          </span>
        ))}
      </div>
      {state === "playing" ? (
        <input name="rain_input" autoFocus value={input} onChange={(e) => type(e.target.value)} aria-label="Type the word" className="field w-full" autoComplete="off" />
      ) : h.loaded && h.hearts <= 0 ? (
        <NoHearts h={h} />
      ) : (
        <button onClick={start} disabled={!words || !h.loaded} className={BTN}>{state === "over" ? "Play again" : "Start"}</button>
      )}
      {state === "over" && <p className="text-sm font-medium" role="status">Game over. Score {score}.</p>}
      <XpLine xp={fin.xp} />
      {err && <p className="text-sm text-rose-700" role="alert">{err}</p>}
    </div>
  );
};

// ---- Bubble Pop (từ - nghĩa) ----
interface Round { term: string; answer: string; options: string[] }

export const BubblePop: React.FC = () => {
  const { words, error } = useWords();
  const h = useHearts();
  const [rounds, setRounds] = useState<Round[]>([]);
  const [i, setI] = useState(0);
  const [score, setScore] = useState(0);
  const [lives, setLives] = useState(5);
  const [flash, setFlash] = useState(false);
  const [over, setOver] = useState(false);
  const [err, setErr] = useState("");
  const fin = useFinish("bubble_pop", setErr);

  const start = () => {
    if (!words) return;
    setRounds(
      pick(words, 10).map((w) => ({
        term: w.term,
        answer: w.meaning_vi,
        options: shuffle([w.meaning_vi, ...pick(words.filter((x) => x.meaning_vi !== w.meaning_vi), 3).map((x) => x.meaning_vi)]),
      })),
    );
    setI(0);
    setScore(0);
    setLives(h.hearts);
    setOver(false);
    fin.reset();
  };

  const choose = (option: string) => {
    if (flash || over) return;
    const right = option === rounds[i].answer;
    setFlash(true);
    const nextLives = right ? lives : lives - 1;
    const nextScore = right ? score + 1 : score;
    if (!right) void loseHeart().catch(() => {});
    window.setTimeout(() => {
      setFlash(false);
      setScore(nextScore);
      setLives(nextLives);
      if (nextLives <= 0 || i === rounds.length - 1) {
        setOver(true);
        fin.finish(nextScore);
      } else setI(i + 1);
    }, 500);
  };

  if (error) return <p className="text-sm text-rose-700" role="alert">{error}</p>;
  const playing = rounds.length > 0 && !over;
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">Pop the bubble with the right Vietnamese meaning. A wrong pop costs a heart. 6 of 10 for XP.</p>
      <div className="flex items-center gap-3 text-sm">
        <HeartsBar left={playing ? lives : h.hearts} max={h.max} />
        <span>Score: <b>{score}</b></span>
        {playing && <span className="text-slate-500">{i + 1}/{rounds.length}</span>}
      </div>
      {playing ? (
        <>
          <p className="text-xl font-bold font-display" aria-label="Word to match">{rounds[i].term}</p>
          <div className="grid grid-cols-2 gap-2">
            {rounds[i].options.map((o) => (
              <button
                key={o}
                onClick={() => choose(o)}
                className={`min-h-16 px-3 py-2 rounded-full border-2 text-sm font-semibold transition-colors ${
                  flash && o === rounds[i].answer ? "bg-emerald-100 border-emerald-500" : "bg-sky-50 border-sky-300 hover:bg-sky-100"
                }`}
              >
                {o}
              </button>
            ))}
          </div>
        </>
      ) : h.loaded && h.hearts <= 0 ? (
        <NoHearts h={h} />
      ) : (
        <button onClick={start} disabled={!words || !h.loaded} className={BTN}>{over ? "Play again" : "Start"}</button>
      )}
      {over && <p className="text-sm font-medium" role="status">Finished. Score {score}/10.</p>}
      <XpLine xp={fin.xp} />
      {err && <p className="text-sm text-rose-700" role="alert">{err}</p>}
    </div>
  );
};

// ---- Word Search ----
const SIZE = 10;
const DIRS = [[0, 1], [1, 0], [1, 1]] as const;
interface Placed { term: string; meaning: string; cells: number[] }

function buildGrid(source: GameWord[]): { grid: string[]; placed: Placed[] } {
  const grid: string[] = Array(SIZE * SIZE).fill("");
  const placed: Placed[] = [];
  const candidates = shuffle(source.filter((w) => /^[a-z]{4,8}$/.test(w.term.toLowerCase())));
  for (const word of candidates) {
    if (placed.length === 5) break;
    const text = word.term.toLowerCase();
    for (let attempt = 0; attempt < 80; attempt++) {
      const [dr, dc] = DIRS[Math.floor(Math.random() * DIRS.length)];
      const r = Math.floor(Math.random() * SIZE);
      const c = Math.floor(Math.random() * SIZE);
      const cells = [...text].map((_, k) => (r + dr * k) * SIZE + (c + dc * k));
      const inside = r + dr * (text.length - 1) < SIZE && c + dc * (text.length - 1) < SIZE;
      if (inside && cells.every((cell, k) => grid[cell] === "" || grid[cell] === text[k])) {
        cells.forEach((cell, k) => (grid[cell] = text[k]));
        placed.push({ term: text, meaning: word.meaning_vi, cells });
        break;
      }
    }
  }
  const letters = "abcdefghijklmnopqrstuvwxyz";
  return { grid: grid.map((g) => g || letters[Math.floor(Math.random() * 26)]), placed };
}

export const WordSearch: React.FC = () => {
  const { words, error } = useWords();
  const [board, setBoard] = useState<{ grid: string[]; placed: Placed[] } | null>(null);
  const [found, setFound] = useState<Set<string>>(new Set());
  const [start, setStart] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const fin = useFinish("word_search", setErr);

  const newGame = () => {
    if (!words) return;
    setBoard(buildGrid(words));
    setFound(new Set());
    setStart(null);
    fin.reset();
  };
  useEffect(() => {
    if (words && !board) newGame();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [words]);

  const click = (cell: number) => {
    if (!board) return;
    if (start === null) return setStart(cell);
    const hit = board.placed.find(
      (p) => (p.cells[0] === start && p.cells[p.cells.length - 1] === cell) || (p.cells[0] === cell && p.cells[p.cells.length - 1] === start),
    );
    setStart(null);
    if (hit && !found.has(hit.term)) {
      const next = new Set(found).add(hit.term);
      setFound(next);
      if (next.size === board.placed.length) fin.finish(next.size);
    }
  };

  if (error) return <p className="text-sm text-rose-700" role="alert">{error}</p>;
  if (!board) return <p className="text-sm text-slate-500">Loading…</p>;
  const foundCells = new Set(board.placed.filter((p) => found.has(p.term)).flatMap((p) => p.cells));
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">Click the first and last letter of each hidden word (across, down or diagonal).</p>
      <div className="grid gap-0.5 w-fit" style={{ gridTemplateColumns: `repeat(${SIZE}, 2rem)` }} role="grid" aria-label="Word search grid">
        {board.grid.map((letter, cell) => (
          <button
            key={cell}
            role="gridcell"
            onClick={() => click(cell)}
            className={`w-8 h-8 rounded text-sm font-bold uppercase ${
              foundCells.has(cell) ? "bg-emerald-200 text-emerald-900" : start === cell ? "bg-amber-300" : "bg-slate-100 hover:bg-slate-200"
            }`}
          >
            {letter}
          </button>
        ))}
      </div>
      <ul className="text-sm space-y-0.5" aria-label="Words to find">
        {board.placed.map((p) => (
          <li key={p.term} className={found.has(p.term) ? "line-through text-emerald-700" : ""}>
            {found.has(p.term) ? p.term : "?".repeat(p.term.length)} — {p.meaning}
          </li>
        ))}
      </ul>
      <XpLine xp={fin.xp} />
      {err && <p className="text-sm text-rose-700" role="alert">{err}</p>}
      <button onClick={newGame} className={BTN}>New puzzle</button>
    </div>
  );
};

// ---- Word Chain (đối kháng với máy) ----
const CHAIN_ERRORS: Record<string, string> = {
  not_in_word_list: "That is not in my word list.",
  wrong_start_letter: "It must start with the last letter of the previous word.",
  already_used: "That word was already used.",
};

export const WordChain: React.FC = () => {
  const [chain, setChain] = useState<string[]>([]);
  const [mine, setMine] = useState(0);
  const [input, setInput] = useState("");
  const [msg, setMsg] = useState("");
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const fin = useFinish("word_chain", setErr);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy || over || !input.trim()) return;
    setBusy(true);
    setMsg("");
    try {
      const word = input.trim().toLowerCase();
      const { reply } = await wordChainTurn(chain, word);
      const nextMine = mine + 1;
      setChain(reply ? [...chain, word, reply] : [...chain, word]);
      setMine(nextMine);
      setInput("");
      if (!reply || nextMine >= 6) {
        setOver(true);
        setMsg(reply ? "You win - 6 words in a row!" : "I am stuck. You win!");
        fin.finish(nextMine);
      }
    } catch (e2) {
      const code = (e2 as Error).message;
      setMsg(CHAIN_ERRORS[code] ?? code);
    } finally {
      setBusy(false);
    }
  };

  const last = chain[chain.length - 1];
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">Take turns with me: each word starts with the last letter of the previous one. Get 6 words in to win.</p>
      <p className="text-sm min-h-6" aria-label="Chain">{chain.length ? chain.join(" → ") : "You start - any word."}</p>
      {!over && (
        <form onSubmit={submit} className="flex gap-2">
          <input
            name="chain_word"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={last ? `Starts with "${last[last.length - 1]}"` : "Your word"}
            aria-label="Your word"
            className="field flex-1"
            autoComplete="off"
          />
          <button type="submit" disabled={busy} className={BTN}>Play</button>
        </form>
      )}
      {msg && <p className="text-sm font-medium" role="status">{msg}</p>}
      <XpLine xp={fin.xp} />
      {err && <p className="text-sm text-rose-700" role="alert">{err}</p>}
      {over && (
        <button onClick={() => { setChain([]); setMine(0); setOver(false); setMsg(""); fin.reset(); }} className={BTN}>
          Play again
        </button>
      )}
    </div>
  );
};

// ---- Dictation Racer ----
export const DictationRacer: React.FC = () => {
  const { words, error } = useWords();
  const [list, setList] = useState<GameWord[]>([]);
  const [i, setI] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [input, setInput] = useState("");
  const [feedback, setFeedback] = useState("");
  const [startedAt, setStartedAt] = useState(0);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const fin = useFinish("dictation_racer", setErr);

  const speak = (text: string) => {
    if (typeof speechSynthesis === "undefined") return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US";
    speechSynthesis.speak(u);
  };

  const start = () => {
    if (!words) return;
    const next = pick(words.filter((w) => /^[a-z]{4,9}$/i.test(w.term)), 6);
    setList(next);
    setI(0);
    setCorrect(0);
    setInput("");
    setFeedback("");
    setElapsed(null);
    setStartedAt(Date.now());
    fin.reset();
    speak(next[0].term);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!list.length || elapsed !== null) return;
    const ok = input.trim().toLowerCase() === list[i].term.toLowerCase();
    const nextCorrect = correct + (ok ? 1 : 0);
    setCorrect(nextCorrect);
    setFeedback(ok ? "Correct!" : `It was "${list[i].term}".`);
    setInput("");
    if (i === list.length - 1) {
      setElapsed(Math.round((Date.now() - startedAt) / 1000));
      fin.finish(nextCorrect);
    } else {
      setI(i + 1);
      speak(list[i + 1].term);
    }
  };

  if (error) return <p className="text-sm text-rose-700" role="alert">{error}</p>;
  const racing = list.length > 0 && elapsed === null;
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">Listen and type each word. Every correct word moves your car forward. 4 of 6 for XP.</p>
      <div className="relative h-8 rounded-full bg-slate-100" aria-label="Race track">
        <span className="absolute top-0 text-2xl transition-all duration-500" style={{ left: `${(correct / 6) * 88}%` }}>🏎️</span>
        <span className="absolute right-1 top-0 text-2xl">🏁</span>
      </div>
      {racing ? (
        <form onSubmit={submit} className="space-y-2">
          <p className="text-sm text-slate-500">
            Hint: <b>{list[i].meaning_vi}</b>
            <button type="button" onClick={() => speak(list[i].term)} className="ml-2 underline text-indigo-700">Replay audio</button>
          </p>
          <div className="flex gap-2">
            <input name="dictation_input" autoFocus value={input} onChange={(e) => setInput(e.target.value)} aria-label="Type what you hear" className="field flex-1" autoComplete="off" />
            <button type="submit" className={BTN}>Go</button>
          </div>
          <p className="text-xs text-slate-500">Word {i + 1} of {list.length}</p>
        </form>
      ) : (
        <button onClick={start} disabled={!words} className={BTN}>{elapsed !== null ? "Race again" : "Start race"}</button>
      )}
      {feedback && <p className="text-sm" role="status">{feedback}</p>}
      {elapsed !== null && <p className="text-sm font-medium" role="status">Finished: {correct}/6 correct in {elapsed}s.</p>}
      <XpLine xp={fin.xp} />
      {err && <p className="text-sm text-rose-700" role="alert">{err}</p>}
    </div>
  );
};

// ---- Voice Runner (Web Speech API) ----
const normalize = (s: string) => s.toLowerCase().replace(/[^a-z\s]/g, "").trim();

export const VoiceRunner: React.FC = () => {
  const { words, error } = useWords();
  const [list, setList] = useState<GameWord[]>([]);
  const [i, setI] = useState(0);
  const [score, setScore] = useState(0);
  const [heard, setHeard] = useState("");
  const [listening, setListening] = useState(false);
  const [over, setOver] = useState(false);
  const [err, setErr] = useState("");
  const fin = useFinish("voice_runner", setErr);
  const speechWindow = window as unknown as { SpeechRecognition?: new () => any; webkitSpeechRecognition?: new () => any };
  const Recognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;

  const start = () => {
    if (!words) return;
    setList(pick(words.filter((w) => /^[a-z]{3,9}$/i.test(w.term)), 5));
    setI(0);
    setScore(0);
    setHeard("");
    setOver(false);
    fin.reset();
  };

  const advance = (nextScore: number) => {
    if (i === list.length - 1) {
      setOver(true);
      fin.finish(nextScore);
    } else setI(i + 1);
  };

  const listen = () => {
    if (!Recognition || listening) return;
    const rec = new Recognition();
    rec.lang = "en-US";
    rec.maxAlternatives = 3;
    rec.onresult = (event: any) => {
      const alternatives = [...event.results[0]].map((a: any) => normalize(a.transcript));
      setHeard(alternatives[0] ?? "");
      if (alternatives.some((a) => a.split(/\s+/).includes(list[i].term.toLowerCase()))) {
        const next = score + 1;
        setScore(next);
        advance(next);
      }
    };
    rec.onerror = () => setHeard("(could not hear you - try again)");
    rec.onend = () => setListening(false);
    setListening(true);
    rec.start();
  };

  if (error) return <p className="text-sm text-rose-700" role="alert">{error}</p>;
  if (!Recognition) {
    return <p className="text-sm text-slate-600" role="status">Voice Runner needs speech recognition, which this browser does not support. Try Chrome or Edge.</p>;
  }
  const running = list.length > 0 && !over;
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">Say each word out loud into your microphone to move the runner. 3 of 5 for XP.</p>
      <div className="relative h-8 rounded-full bg-slate-100" aria-label="Runner track">
        <span className="absolute top-0 text-2xl transition-all duration-500" style={{ left: `${(i / 5) * 88}%` }}>🏃</span>
        <span className="absolute right-1 top-0 text-2xl">🏁</span>
      </div>
      {running ? (
        <div className="space-y-2">
          <p className="text-2xl font-bold font-display" aria-label="Word to say">{list[i].term}</p>
          <p className="text-sm text-slate-500">{list[i].meaning_vi}</p>
          <div className="flex gap-2">
            <button onClick={listen} disabled={listening} className={BTN}>{listening ? "Listening…" : "🎤 Speak"}</button>
            <button onClick={() => advance(score)} className="text-sm underline text-slate-600">Skip</button>
          </div>
          {heard && <p className="text-xs text-slate-500" role="status">Heard: "{heard}"</p>}
        </div>
      ) : (
        <button onClick={start} disabled={!words} className={BTN}>{over ? "Run again" : "Start"}</button>
      )}
      {over && <p className="text-sm font-medium" role="status">Finished: {score}/5 words.</p>}
      <XpLine xp={fin.xp} />
      {err && <p className="text-sm text-rose-700" role="alert">{err}</p>}
    </div>
  );
};
