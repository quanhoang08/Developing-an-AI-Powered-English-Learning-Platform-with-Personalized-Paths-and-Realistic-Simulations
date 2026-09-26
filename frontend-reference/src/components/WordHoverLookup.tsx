// Bọc 1 vùng văn bản: rê chuột vào từ bất kỳ → tooltip nghĩa (EN + VI) và nút lưu vào từ vựng.
// Chỉ dùng ở Reading (passage từ tài liệu người dùng upload) và Writing (bài đã được AI sửa);
// các vùng khác của web cố ý không bọc để tránh tra nghĩa ngoài ý muốn.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { getAccessToken, lookupWord, saveVocabulary } from "../api";
import { LookupData, lookupDefinition } from "../dictionary";

const HOVER_DELAY_MS = 300;
const HIDE_DELAY_MS = 250;
const WORD_PATTERN = /[A-Za-z][A-Za-z'’-]*/g;

interface HoverTarget {
  word: string;
  sentence: string;
  rect: { left: number; bottom: number; top: number };
}

// Tìm từ nằm dưới con trỏ bằng caret API rồi kiểm tra con trỏ thật sự nằm trên chữ.
function wordAtPoint(x: number, y: number): HoverTarget | null {
  const doc = document as Document & {
    caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null;
    caretRangeFromPoint?: (x: number, y: number) => Range | null;
  };
  let node: Node | null = null;
  let offset = 0;
  if (doc.caretPositionFromPoint) {
    const pos = doc.caretPositionFromPoint(x, y);
    if (pos) ({ offsetNode: node, offset } = pos);
  } else if (doc.caretRangeFromPoint) {
    const range = doc.caretRangeFromPoint(x, y);
    if (range) ({ startContainer: node, startOffset: offset } = range);
  }
  if (!node || node.nodeType !== Node.TEXT_NODE) return null;

  const text = (node as Text).data;
  WORD_PATTERN.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = WORD_PATTERN.exec(text))) {
    const start = match.index;
    const end = start + match[0].length;
    if (offset < start || offset > end) continue;
    const range = document.createRange();
    range.setStart(node, start);
    range.setEnd(node, end);
    const hit = Array.from(range.getClientRects()).some(
      (r) => x >= r.left - 1 && x <= r.right + 1 && y >= r.top - 1 && y <= r.bottom + 1,
    );
    if (!hit) return null;
    const word = match[0].replace(/^[-'’]+|[-'’]+$/g, "");
    if (word.length < 2) return null;
    let from = start;
    while (from > 0 && !/[.!?\n]/.test(text[from - 1])) from -= 1;
    let to = end;
    while (to < text.length && !/[.!?\n]/.test(text[to])) to += 1;
    const rect = range.getBoundingClientRect();
    return {
      word,
      sentence: text.slice(from, Math.min(to + 1, text.length)).trim().slice(0, 300),
      rect: { left: rect.left, bottom: rect.bottom, top: rect.top },
    };
  }
  return null;
}

interface Props {
  children: React.ReactNode;
  // false → render nguyên trạng, không tra nghĩa (vd. passage do AI tự sinh, không phải file upload).
  enabled?: boolean;
  className?: string;
}

export const WordHoverLookup: React.FC<Props> = ({ children, enabled = true, className }) => {
  const [target, setTarget] = useState<HoverTarget | null>(null);
  const [lookup, setLookup] = useState<LookupData | null>(null);
  const [saveState, setSaveState] = useState<{ ok: boolean; message: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [aiPending, setAiPending] = useState(false);
  const hoverTimer = useRef<number | undefined>(undefined);
  const hideTimer = useRef<number | undefined>(undefined);
  const seq = useRef(0);
  const cardRef = useRef<HTMLDivElement>(null);

  const hide = useCallback(() => {
    seq.current += 1;
    setTarget(null);
    setLookup(null);
    setSaveState(null);
    setAiPending(false);
  }, []);

  useEffect(() => {
    if (!enabled) hide();
    return () => {
      window.clearTimeout(hoverTimer.current);
      window.clearTimeout(hideTimer.current);
    };
  }, [enabled, hide]);

  // Tooltip dùng position: fixed nên phải ẩn khi cuộn để không lệch khỏi từ.
  useEffect(() => {
    if (!target) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && hide();
    window.addEventListener("scroll", hide, true);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("scroll", hide, true);
      window.removeEventListener("keydown", onKey);
    };
  }, [target, hide]);

  const show = async (next: HoverTarget) => {
    const mine = ++seq.current;
    setTarget(next);
    setLookup(null);
    setSaveState(null);
    let data: LookupData;
    try {
      data = await lookupDefinition(next.word);
    } catch {
      data = { found: false, word: next.word, ipa: null, audio: null, vietnamese: null, meanings: [], synonyms: [], antonyms: [] };
    }
    if (mine !== seq.current) return;
    setLookup(data);
    if (!getAccessToken()) return;

    // Đã đăng nhập: nâng cấp bằng nghĩa Ollama theo level (chậm hơn nên hiện sau, lỗi thì giữ kết quả nhanh).
    setAiPending(true);
    try {
      const ai = await lookupWord(next.word, next.sentence || next.word);
      if (mine !== seq.current || !ai.senses?.length) return;
      setLookup({
        ...data,
        found: true,
        ipa: ai.ipa || data.ipa,
        senses: ai.senses.map((sense) => ({
          level: sense.level,
          partOfSpeech: sense.part_of_speech,
          meaningVi: sense.meaning_vi,
          example: sense.example_en || null,
        })),
        synonyms: ai.synonyms.length ? ai.synonyms : data.synonyms,
        antonyms: ai.antonyms.length ? ai.antonyms : data.antonyms,
      });
    } catch {
      // 503 (Ollama chưa chạy) hoặc lỗi mạng — giữ nguyên kết quả nhanh.
    } finally {
      if (mine === seq.current) setAiPending(false);
    }
  };

  const handleMouseMove = (event: React.MouseEvent) => {
    if (!enabled) return;
    window.clearTimeout(hoverTimer.current);
    // Tooltip là con của vùng bọc: chuột đang di trong tooltip thì giữ nguyên, không tra chữ trong chính nó.
    if (cardRef.current?.contains(event.target as Node)) {
      window.clearTimeout(hideTimer.current);
      return;
    }
    const { clientX, clientY } = event;
    hoverTimer.current = window.setTimeout(() => {
      const found = wordAtPoint(clientX, clientY);
      window.clearTimeout(hideTimer.current);
      if (!found) {
        hideTimer.current = window.setTimeout(hide, HIDE_DELAY_MS);
        return;
      }
      if (target && target.word.toLowerCase() === found.word.toLowerCase()) return;
      void show(found);
    }, HOVER_DELAY_MS);
  };

  const speak = (word: string) => {
    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(word);
      utterance.lang = "en-US";
      window.speechSynthesis.speak(utterance);
    }
  };

  const play = () => {
    if (!target) return;
    if (lookup?.audio) {
      void new Audio(lookup.audio).play().catch(() => speak(target.word));
    } else {
      speak(target.word);
    }
  };

  const save = async () => {
    if (!target || !lookup) return;
    if (!getAccessToken()) {
      setSaveState({ ok: false, message: "Hãy đăng nhập để lưu từ." });
      return;
    }
    setSaving(true);
    try {
      const primary = lookup.meanings[0];
      // Bản AI có senses tiếng Việt: lưu nghĩa đầu tiên (hợp ngữ cảnh nhất).
      const aiSense = lookup.senses?.[0];
      await saveVocabulary({
        term: target.word.toLowerCase(),
        definition: aiSense
          ? aiSense.meaningVi
          : [lookup.vietnamese, primary?.definition].filter(Boolean).join(" — "),
        sourceUrl: window.location.href,
        exampleSentence: target.sentence || aiSense?.example || primary?.example || "",
        synonyms: lookup.synonyms,
        antonyms: lookup.antonyms,
        ipa: lookup.ipa ?? undefined,
        partOfSpeech: aiSense?.partOfSpeech || primary?.partOfSpeech || undefined,
      });
      setSaveState({ ok: true, message: `Đã lưu "${target.word}".` });
    } catch (error) {
      setSaveState({ ok: false, message: error instanceof Error ? error.message : "Lưu thất bại" });
    } finally {
      setSaving(false);
    }
  };

  const cardWidth = 320;
  const left = target ? Math.max(12, Math.min(target.rect.left, window.innerWidth - cardWidth - 12)) : 0;
  // Nếu từ nằm sát đáy màn hình thì lật tooltip lên trên từ.
  const flipUp = target ? target.rect.bottom + 240 > window.innerHeight && target.rect.top > 240 : false;

  return (
    <div className={className} onMouseMove={handleMouseMove}>
      {children}
      {enabled && target && (
        <div
          ref={cardRef}
          onMouseEnter={() => window.clearTimeout(hideTimer.current)}
          onMouseLeave={() => {
            hideTimer.current = window.setTimeout(hide, HIDE_DELAY_MS);
          }}
          style={{
            position: "fixed",
            left,
            width: cardWidth,
            top: flipUp ? undefined : target.rect.bottom + 8,
            bottom: flipUp ? window.innerHeight - target.rect.top + 8 : undefined,
            zIndex: 60,
          }}
          className="max-w-[calc(100vw-24px)] rounded-2xl border border-slate-200 bg-white p-3.5 text-xs shadow-xl"
        >
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="text-lg font-extrabold text-indigo-700">{target.word}</span>
            {lookup?.ipa && <span className="font-mono text-slate-500">{lookup.ipa}</span>}
          </div>
          {!lookup && <p className="mt-1.5 text-slate-400">Đang tra…</p>}
          {lookup && !lookup.found && <p className="mt-1.5 text-slate-400">Không tìm thấy nghĩa của từ này.</p>}
          {lookup?.senses?.length ? (
            <div className="mt-1.5 space-y-2">
              {lookup.senses.map((sense, index) => (
                <div key={index}>
                  <p className="flex flex-wrap items-baseline gap-1.5">
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-extrabold text-white ${
                        /^A/.test(sense.level) ? "bg-green-600" : /^B/.test(sense.level) ? "bg-amber-600" : "bg-red-600"
                      }`}
                    >
                      {sense.level}
                    </span>
                    {sense.partOfSpeech && (
                      <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-bold uppercase text-indigo-700">
                        {sense.partOfSpeech}
                      </span>
                    )}
                    <span className="text-sm font-semibold text-emerald-700">{sense.meaningVi}</span>
                  </p>
                  {sense.example && <p className="italic text-slate-500">"{sense.example}"</p>}
                </div>
              ))}
            </div>
          ) : lookup?.found ? (
            <div className="mt-1.5 space-y-1.5">
              {lookup.vietnamese && <p className="text-sm font-semibold text-emerald-700">{lookup.vietnamese}</p>}
              {lookup.meanings.slice(0, 2).map((meaning, index) => (
                <p key={index} className="text-slate-700">
                  {meaning.partOfSpeech && (
                    <span className="mr-1.5 rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-bold uppercase text-indigo-700">
                      {meaning.partOfSpeech}
                    </span>
                  )}
                  {meaning.definition}
                </p>
              ))}
            </div>
          ) : null}
          {aiPending && <p className="mt-1.5 text-[11px] text-slate-400">⏳ Đang tạo nghĩa chi tiết theo level…</p>}
          <div className="mt-2.5 flex gap-1.5">
            <button onClick={play} className="rounded-lg bg-slate-100 px-2.5 py-1 font-semibold text-slate-700 hover:bg-slate-200">
              🔊 Nghe
            </button>
            <button
              onClick={() => void save()}
              disabled={!lookup || saving || saveState?.ok === true}
              className="rounded-lg bg-indigo-600 px-2.5 py-1 font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {saveState?.ok ? "Đã lưu" : "＋ Lưu vào từ vựng"}
            </button>
          </div>
          {saveState && (
            <p className={`mt-1.5 ${saveState.ok ? "text-emerald-700" : "text-red-600"}`}>{saveState.message}</p>
          )}
        </div>
      )}
    </div>
  );
};
