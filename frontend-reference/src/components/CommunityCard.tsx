// Bạn bè + bảng xếp hạng (backlog 4.6) và lớp học (nhóm 5): tạo/vào lớp, giao bài, xem tiến độ học sinh.
import React, { useEffect, useState } from "react";
import {
  ClassDetail,
  FriendsOverview,
  LeaderboardRow,
  MyClasses,
  acceptFriend,
  addClassAssignment,
  createClass,
  deleteClassAssignment,
  getClassDetail,
  getFriends,
  getLeaderboard,
  getMyClasses,
  joinClass,
  removeClassMember,
  removeFriend,
  sendFriendRequest,
} from "../api";

const SKILLS = ["reading", "listening", "writing", "speaking", "vocab", "grammar"];
const input = "px-3 py-1.5 rounded-xl ring-1 ring-slate-900/10 text-sm";
const btn = "px-4 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-xs rounded-2xl cursor-pointer";

const Friends: React.FC<{ onError: (m: string) => void }> = ({ onError }) => {
  const [data, setData] = useState<FriendsOverview | null>(null);
  const [board, setBoard] = useState<LeaderboardRow[]>([]);
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [period, setPeriod] = useState<"week" | "all">("week");

  const load = () => Promise.all([getFriends(), getLeaderboard(period)]).then(([f, b]) => { setData(f); setBoard(b); }).catch((e) => onError(e.message));
  useEffect(() => { void load(); }, [period]);
  const act = (fn: () => Promise<unknown>) => fn().then(load).catch((e) => onError(e.message));

  return (
    <div className="space-y-3">
      <h4 className="font-bold text-slate-900">Friends &amp; leaderboard</h4>
      <div className="flex gap-2">
        <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" placeholder="Friend's email" className={`${input} flex-1`} />
        <button disabled={!email.trim()} className={btn}
          onClick={() => void sendFriendRequest(email.trim()).then((r) => { setNote(r.detail); setEmail(""); return load(); }).catch((e) => onError(e.message))}>Invite</button>
      </div>
      {note && <p className="text-xs text-slate-600" role="status">{note}</p>}
      <div className="flex gap-2" role="group" aria-label="Leaderboard period">
        {(["week", "all"] as const).map((p) => (
          <button key={p} aria-pressed={period === p} onClick={() => setPeriod(p)}
            className={`px-3 py-1 rounded-full text-xs font-bold cursor-pointer ${period === p ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"}`}>
            {p === "week" ? "This week" : "All time"}
          </button>
        ))}
      </div>
      {data?.incoming.map((f) => (
        <div key={f.friendship_id} className="flex items-center gap-2 text-sm">
          <span>{f.name} wants to be friends</span>
          <button className={btn} onClick={() => void act(() => acceptFriend(f.friendship_id))}>Accept</button>
          <button className="text-xs text-rose-700 cursor-pointer" onClick={() => void act(() => removeFriend(f.friendship_id))}>Decline</button>
        </div>
      ))}
      {data?.outgoing.map((f) => <p key={f.friendship_id} className="text-xs text-slate-500">Waiting for {f.name}…</p>)}
      <ol className="space-y-1">
        {board.map((r) => (
          <li key={r.user_id} className={`flex justify-between text-sm px-3 py-1.5 rounded-xl ${r.is_me ? "bg-indigo-50 font-bold" : "bg-slate-50"}`}>
            <span>{r.rank}. {r.name}{r.is_me ? " (you)" : ""}</span>
            <span className="num">{period === "week" ? r.weekly_xp : r.total_xp} XP · {r.streak}d streak</span>
          </li>
        ))}
      </ol>
      {data?.friends.map((f) => (
        <button key={f.friendship_id} className="text-[11px] text-slate-400 hover:text-rose-700 mr-3 cursor-pointer" onClick={() => void act(() => removeFriend(f.friendship_id))}>Remove {f.name}</button>
      ))}
    </div>
  );
};

const Classes: React.FC<{ onError: (m: string) => void }> = ({ onError }) => {
  const [mine, setMine] = useState<MyClasses | null>(null);
  const [open, setOpen] = useState<ClassDetail | null>(null);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [skill, setSkill] = useState("");
  const [due, setDue] = useState("");

  const load = () => getMyClasses().then(setMine).catch((e) => onError(e.message));
  const show = (id: string) => getClassDetail(id).then(setOpen).catch((e) => onError(e.message));
  useEffect(() => { void load(); }, []);
  const act = (fn: () => Promise<unknown>) => fn().catch((e) => onError(e.message));

  return (
    <div className="space-y-3">
      <h4 className="font-bold text-slate-900">Classes</h4>
      <div className="flex flex-wrap gap-2">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New class name" className={input} />
        <button disabled={!name.trim()} className={btn} onClick={() => void act(async () => { await createClass(name.trim()); setName(""); await load(); })}>Create (I'm the teacher)</button>
        <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} maxLength={8} placeholder="Join code" className={`${input} w-28`} />
        <button disabled={code.length < 4} className={btn} onClick={() => void act(async () => { await joinClass(code); setCode(""); await load(); })}>Join</button>
      </div>
      <div className="flex flex-wrap gap-2">
        {mine?.teaching.map((c) => (
          <button key={c.id} onClick={() => void show(c.id)} className="px-3 py-1.5 rounded-full bg-indigo-100 text-indigo-900 text-xs font-bold cursor-pointer">{c.name} · code {c.join_code} · {c.members} students</button>
        ))}
        {mine?.joined.map((c) => (
          <button key={c.id} onClick={() => void show(c.id)} className="px-3 py-1.5 rounded-full bg-slate-100 text-slate-800 text-xs font-bold cursor-pointer">{c.name}</button>
        ))}
      </div>
      {open && (
        <div className="space-y-3 border-t border-dashed border-slate-200 pt-3">
          <p className="font-bold text-slate-900">{open.name}</p>
          {open.assignments.length === 0 && <p className="text-xs text-slate-500">No assignments yet.</p>}
          {open.assignments.map((a) => (
            <div key={a.id} className="text-sm flex items-center gap-2">
              <span>{a.title}{a.skill && ` (${a.skill})`}{a.due_date && ` — due ${a.due_date}`}</span>
              {a.auto_graded && (open.is_teacher
                ? <span className="num text-xs text-slate-500">{a.done_count}/{a.total_students} done</span>
                : <span className={`text-xs font-bold ${a.done ? "text-emerald-700" : "text-slate-400"}`}>{a.done ? "✓ Done" : "Not done yet"}</span>)}
              {open.is_teacher && <button className="text-xs text-rose-700 cursor-pointer" onClick={() => void act(async () => { await deleteClassAssignment(open.id, a.id); await show(open.id); })}>Delete</button>}
            </div>
          ))}
          {open.is_teacher && (
            <>
              <div className="flex flex-wrap gap-2">
                <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Assignment title" className={`${input} flex-1`} />
                <select value={skill} onChange={(e) => setSkill(e.target.value)} className={input} aria-label="Skill">
                  <option value="">Any skill</option>
                  {SKILLS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <input type="date" value={due} onChange={(e) => setDue(e.target.value)} className={input} aria-label="Due date" />
                <button disabled={!title.trim()} className={btn}
                  onClick={() => void act(async () => { await addClassAssignment(open.id, { title: title.trim(), skill: skill || undefined, due_date: due || undefined }); setTitle(""); await show(open.id); })}>Assign</button>
              </div>
              <table className="w-full text-xs text-left">
                <thead><tr className="text-slate-500"><th>Student</th><th>Streak</th><th>XP</th><th>Min/wk</th><th>Mistakes</th><th>Words</th><th>Tasks</th><th /></tr></thead>
                <tbody>
                  {open.students.map((s) => (
                    <tr key={s.user_id} className="border-t border-slate-100">
                      <td className="py-1">{s.name}</td><td className="num">{s.streak}</td><td className="num">{s.total_xp}</td>
                      <td className="num">{s.minutes}</td><td className="num">{s.mistakes_logged}</td><td className="num">{s.words_saved}</td><td className="num">{s.assignments_done}/{s.assignments_total}</td>
                      <td><button className="text-rose-700 cursor-pointer" onClick={() => void act(async () => { await removeClassMember(open.id, s.user_id); await show(open.id); })}>Remove</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-[11px] text-slate-400">Minutes only count for students who turned on timer mode. Tasks with a skill are marked done automatically once the student practises that skill after the task was set.</p>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export const CommunityCard: React.FC = () => {
  const [error, setError] = useState("");
  return (
    <section className="surface p-7 space-y-6" aria-label="Friends and classes">
      <h3 className="font-display text-xl font-bold text-slate-900">Friends &amp; classes</h3>
      <Friends onError={setError} />
      <div className="border-t border-dashed border-slate-200 pt-5"><Classes onError={setError} /></div>
      <p role="alert" className="text-xs text-rose-700">
        {error}
      </p>
    </section>
  );
};
