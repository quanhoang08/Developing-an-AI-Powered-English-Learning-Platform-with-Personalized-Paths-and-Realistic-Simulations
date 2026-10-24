// Ví xu + shop + gacha + tim, và bang hội (Study Clan): /api/economy/*, /api/guilds/*.
import React, { useCallback, useEffect, useState } from "react";
import {
  GuildInfo,
  buyShopItem,
  createGuild,
  equipItem,
  getGuildLeaderboard,
  getMyGuild,
  joinGuild,
  leaveGuild,
  refillHearts,
  rollGacha,
} from "../api";
import { useWallet } from "./games/shared";

const ERROR_TEXT: Record<string, string> = {
  not_enough_coins: "Not enough coins.",
  already_owned: "You already own this.",
  hearts_full: "Hearts are already full.",
  already_in_guild: "You are already in a guild.",
  guild_full: "That guild is full (5 members).",
  guild_not_found: "No guild with that code.",
  invalid_name: "Guild name must be 3-40 characters.",
};
const say = (e: unknown) => ERROR_TEXT[(e as Error).message] ?? (e as Error).message;

function rewardText(r: { coins?: number; booster?: boolean; item?: string }, duplicate: boolean) {
  if (r.coins) return `+${r.coins} coins`;
  if (r.booster) return "2x XP booster (1 hour)";
  return duplicate ? `${r.item} (duplicate: 30 coins back)` : `New item: ${r.item}`;
}

const WalletSection: React.FC = () => {
  const { wallet, reload } = useWallet();
  const [msg, setMsg] = useState("");

  const run = async (action: () => Promise<unknown>, ok?: (r: any) => string) => {
    setMsg("");
    try {
      const r = await action();
      if (ok) setMsg(ok(r));
    } catch (e) {
      setMsg(say(e));
    }
    reload();
  };

  if (!wallet) return null;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        <span aria-label="Coins">🪙 <b>{wallet.coins}</b> coins</span>
        <span aria-label="Hearts" className="text-rose-500">{"♥".repeat(wallet.hearts)}<span className="text-slate-300">{"♥".repeat(wallet.max_hearts - wallet.hearts)}</span></span>
        {wallet.hearts < wallet.max_hearts && (
          <button onClick={() => run(refillHearts, () => "Hearts refilled!")} className="text-xs underline text-indigo-700">
            Refill ({wallet.heart_refill_cost} coins)
          </button>
        )}
        {wallet.booster_seconds_left > 0 && <span className="tag bg-amber-100 text-amber-800">⚡ 2x XP · {Math.ceil(wallet.booster_seconds_left / 60)} min</span>}
      </div>
      <p className="text-xs text-slate-500">Earn 1 coin for every 2 XP. Lose a heart on a wrong answer in Word Rain / Bubble Pop; one regenerates every 30 minutes.</p>
      <div className="flex flex-wrap items-center gap-3">
        <button onClick={() => run(rollGacha, (r) => `Gacha: ${rewardText(r.reward, r.duplicate)}`)} className="btn-primary">
          🎁 Open a mystery box ({wallet.gacha_cost} coins)
        </button>
        {msg && <span className="text-sm font-medium" role="status">{msg}</span>}
      </div>
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2" aria-label="Shop">
        {wallet.shop.map((item) => (
          <li key={item.id} className="flex items-center gap-3 p-2 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-2xl">{item.emoji}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate">{item.name}</p>
              <p className="text-xs text-slate-500">{item.slot === "booster" ? "consumable" : item.slot}</p>
            </div>
            {item.owned && item.slot !== "booster" ? (
              <button
                onClick={() => run(() => equipItem(item.id))}
                disabled={item.equipped}
                className="text-xs font-bold px-2 py-1 rounded-lg bg-emerald-100 text-emerald-800 disabled:opacity-70"
              >
                {item.equipped ? "Equipped" : "Equip"}
              </button>
            ) : (
              <button onClick={() => run(() => buyShopItem(item.id), () => `Bought ${item.name}`)} className="text-xs font-bold px-2 py-1 rounded-lg bg-indigo-600 text-white">
                🪙 {item.price}
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};

const GuildSection: React.FC = () => {
  const [guild, setGuild] = useState<GuildInfo | null | undefined>(undefined);
  const [board, setBoard] = useState<Array<{ name: string; weekly_xp: number; members: number; is_mine: boolean }>>([]);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    getMyGuild().then(setGuild).catch(() => setGuild(null));
    getGuildLeaderboard().then(setBoard).catch(() => setBoard([]));
  }, []);
  useEffect(() => {
    load();
    window.addEventListener("lumina-stats-refresh", load);
    return () => window.removeEventListener("lumina-stats-refresh", load);
  }, [load]);

  const act = async (action: () => Promise<unknown>) => {
    setMsg("");
    try {
      await action();
      setName("");
      setCode("");
    } catch (e) {
      setMsg(say(e));
    }
    load();
  };

  if (guild === undefined) return null;
  return (
    <div className="space-y-4">
      {guild ? (
        <div className="space-y-2">
          <p className="text-sm">
            <b>{guild.name}</b> · {guild.weekly_xp} XP this week · invite code <code className="px-1.5 py-0.5 bg-slate-100 rounded font-bold" aria-label="Invite code">{guild.join_code}</code>
          </p>
          <ol className="text-sm space-y-0.5" aria-label="Guild members">
            {guild.members.map((m) => (
              <li key={m.user_id}>{m.name}{m.is_owner ? " 👑" : ""} — {m.weekly_xp} XP</li>
            ))}
          </ol>
          <p className="text-xs text-slate-500">{guild.members.length}/{guild.max_members} members</p>
          <button onClick={() => act(leaveGuild)} className="text-xs underline text-rose-700">Leave guild</button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-4">
          <form onSubmit={(e) => { e.preventDefault(); void act(() => createGuild(name)); }} className="flex gap-2">
            <input name="guild_name" value={name} onChange={(e) => setName(e.target.value)} placeholder="New guild name" aria-label="New guild name" className="field" />
            <button type="submit" disabled={name.trim().length < 3} className="btn-primary">Create</button>
          </form>
          <form onSubmit={(e) => { e.preventDefault(); void act(() => joinGuild(code)); }} className="flex gap-2">
            <input name="guild_code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="Invite code" aria-label="Guild invite code" className="field w-32" />
            <button type="submit" disabled={code.trim().length < 4} className="btn-primary">Join</button>
          </form>
        </div>
      )}
      {msg && <p className="text-sm text-rose-700" role="alert">{msg}</p>}
      {board.length > 0 && (
        <div>
          <h4 className="text-sm font-bold mb-1">Guild leaderboard (this week)</h4>
          <ol className="text-sm space-y-0.5 list-decimal ml-5">
            {board.map((g, idx) => (
              <li key={idx} className={g.is_mine ? "font-bold" : ""}>{g.name} — {g.weekly_xp} XP ({g.members} members)</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
};

export const GuildCard: React.FC = () => (
  <section className="pop-in surface p-6 space-y-5" aria-label="Study guild">
    <h3 className="font-display text-xl font-bold text-slate-900">Study guild</h3>
    <GuildSection />
  </section>
);

export const WalletCard: React.FC = () => (
  <section className="pop-in surface p-6 space-y-5" aria-label="Coins and shop">
    <h3 className="font-display text-xl font-bold text-slate-900">Coins &amp; shop</h3>
    <WalletSection />
  </section>
);

// Bản gộp cũ (ví + bang hội trong 1 thẻ); giữ để tương thích.
export const EconomyCard: React.FC = () => (
  <section className="pop-in surface p-6 space-y-5" aria-label="Coins, shop and guild">
    <h3 className="font-display text-xl font-bold text-slate-900">Coins, shop &amp; study guild</h3>
    <WalletSection />
    <hr className="border-slate-200" />
    <h4 className="font-display text-lg font-bold text-slate-900">Study guild</h4>
    <GuildSection />
  </section>
);
