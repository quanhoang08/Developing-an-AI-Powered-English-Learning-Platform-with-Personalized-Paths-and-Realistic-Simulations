// Mẹo nhớ tiếng Việt cho một từ: xem mẹo của cộng đồng (xếp theo số phiếu), bình chọn, viết/xóa mẹo của mình.
import React, { useCallback, useEffect, useState } from "react";
import { Flag, ThumbsUp, Trash2 } from "lucide-react";
import { Mnemonic, deleteMnemonic, listMnemonics, reportMnemonic, saveMnemonic, voteMnemonic } from "../api";

export const MnemonicsPanel: React.FC<{ term: string }> = ({ term }) => {
  const [items, setItems] = useState<Mnemonic[]>([]);
  const [draft, setDraft] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(() => listMnemonics(term).then(setItems).catch(() => setItems([])), [term]);
  useEffect(() => {
    setDraft("");
    setMessage("");
    void load();
  }, [load]);

  // Mọi thao tác ghi: chạy xong thì tải lại danh sách; lỗi hiện thành 1 dòng.
  const act = async (action: () => Promise<unknown>) => {
    setMessage("");
    try {
      await action();
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Something went wrong.");
    }
  };

  const mine = items.find((item) => item.is_mine);

  return (
    <div className="rounded-2xl bg-slate-50 p-4 space-y-3 text-sm">
      <h4 className="font-bold text-slate-900">Memory tips for “{term}”</h4>
      {items.length === 0 && <p className="text-slate-500">No tips yet — be the first to add one.</p>}
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.id} className="flex items-start gap-2 bg-white rounded-xl p-3 ring-1 ring-slate-900/10">
            <p className="flex-1 font-serif text-slate-800">{item.text}</p>
            {item.is_mine ? (
              <>
                <span className="text-xs text-slate-500 num">{item.votes} 👍</span>
                <button onClick={() => void act(() => deleteMnemonic(item.id))} aria-label="Delete my tip" className="text-rose-600 cursor-pointer">
                  <Trash2 className="w-4 h-4" />
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => void act(() => voteMnemonic(item.id))}
                  aria-pressed={item.voted}
                  aria-label="Vote helpful"
                  className={`flex items-center gap-1 text-xs font-bold cursor-pointer ${item.voted ? "text-indigo-700" : "text-slate-500"}`}
                >
                  <ThumbsUp className="w-4 h-4" /> <span className="num">{item.votes}</span>
                </button>
                <button
                  onClick={() => window.confirm("Report this tip as inappropriate? It will be hidden from you.") && void act(() => reportMnemonic(item.id))}
                  aria-label="Report inappropriate tip"
                  className="text-slate-400 hover:text-rose-700 cursor-pointer"
                >
                  <Flag className="w-4 h-4" />
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        maxLength={300}
        rows={2}
        placeholder={mine ? "Replace my tip…" : "Write a Vietnamese memory tip (e.g. a sound-alike or a story)…"}
        className="w-full px-3 py-2 rounded-xl ring-1 ring-slate-900/10 text-sm"
      />
      <div className="flex items-center gap-3">
        <button
          onClick={() => void act(async () => { await saveMnemonic(term, draft.trim()); setDraft(""); })}
          disabled={draft.trim().length < 5}
          className="px-4 py-2 bg-indigo-700 hover:bg-indigo-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl cursor-pointer"
        >
          {mine ? "Replace my tip" : "Share my tip"}
        </button>
        <span role="alert" className="text-xs text-rose-700">{message}</span>
      </div>
    </div>
  );
};
