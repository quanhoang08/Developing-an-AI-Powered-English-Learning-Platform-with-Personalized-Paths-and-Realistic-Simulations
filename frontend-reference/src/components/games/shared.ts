// Dùng chung cho các mini-game: từ vựng theo chủ đề (cache 1 lần/phiên) và ví xu/tim.
import { useCallback, useEffect, useState } from "react";
import { VocabTopic, Wallet, getWallet, listVocabTopics } from "../../api";

export interface GameWord { term: string; meaning_vi: string }

let topicsPromise: Promise<GameWord[]> | null = null;

// Mọi game dùng chung kho từ này (~400 từ, đã có sẵn cho Vocab theo chủ đề).
export function loadGameWords(): Promise<GameWord[]> {
  topicsPromise ??= listVocabTopics()
    .then((topics: VocabTopic[]) => topics.flatMap((t) => t.words.map((w) => ({ term: w.term, meaning_vi: w.meaning_vi }))))
    .catch((error) => {
      topicsPromise = null; // lỗi mạng thì cho phép thử lại, không cache lỗi
      throw error;
    });
  return topicsPromise;
}

export const shuffle = <T,>(items: T[]) => [...items].sort(() => Math.random() - 0.5);
export const pick = <T,>(items: T[], n: number) => shuffle(items).slice(0, n);

// Ví: tải lại mỗi khi có thao tác ghi thành công (api.ts phát "lumina-stats-refresh").
export function useWallet() {
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const reload = useCallback(() => {
    getWallet().then(setWallet).catch(() => setWallet(null));
  }, []);
  useEffect(() => {
    reload();
    window.addEventListener("lumina-stats-refresh", reload);
    return () => window.removeEventListener("lumina-stats-refresh", reload);
  }, [reload]);
  return { wallet, reload };
}
