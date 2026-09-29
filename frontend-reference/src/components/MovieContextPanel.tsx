// Movie Context Finder: cụm từ khớp phụ đề của phim thật (public domain/CC) hoặc cảnh demo mô phỏng ->
// xem cảnh (VideoPlayerOverlay); không khớp -> nhánh TTS fallback (AI viết câu thoại ví dụ, đọc mẫu
// bằng TTS để nghe và đọc nhại). Cảnh mô phỏng và câu AI được ghi rõ trên giao diện, không giả làm phim thật.
import React, { useEffect, useRef, useState } from "react";
import { Bookmark, Check, Film, Loader2, Play, Search, Square } from "lucide-react";
import { fetchAudioObjectUrl, MovieContextMatch, saveMovieMatch, searchMovieContext } from "../api";
import { ErrorNotice } from "./ErrorNotice";
import { VideoPlayerOverlay } from "./VideoPlayerOverlay";

// 3 cụm đầu có trong "Tears of Steel", 2 cụm kế trong "The Little Shop of Horrors" (phim thật);
// "piece of cake" là cảnh mô phỏng; cuối cùng rơi về TTS.
const POPULAR = ["freaked out", "all systems go", "keep an eye on", "take care of", "piece of cake", "spill the beans"];

export const MovieContextPanel: React.FC = () => {
  const [phrase, setPhrase] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [matches, setMatches] = useState<MovieContextMatch[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [watchingId, setWatchingId] = useState<string | null>(null);
  const watching = matches?.find((item) => item.match_id === watchingId) ?? null;
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  const stopAudio = () => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = null;
    setPlayingId(null);
  };

  // Rời trang thì dừng tiếng và giải phóng blob.
  useEffect(() => stopAudio, []);

  const search = async (text: string) => {
    const query = text.trim();
    if (!query) return;
    stopAudio();
    setPhrase(query);
    setIsSearching(true);
    setError(null);
    try {
      setMatches((await searchMovieContext(query)).matches);
    } catch (searchError) {
      setError(searchError);
    } finally {
      setIsSearching(false);
    }
  };

  const togglePlay = async (match: MovieContextMatch) => {
    if (playingId === match.match_id) {
      stopAudio();
      return;
    }
    stopAudio();
    if (!match.audio_url) return;
    setPlayingId(match.match_id);
    try {
      const url = await fetchAudioObjectUrl(match.audio_url);
      const audio = new Audio(url);
      audioRef.current = audio;
      objectUrlRef.current = url;
      audio.onended = stopAudio;
      await audio.play();
    } catch (playError) {
      stopAudio();
      setError(playError);
    }
  };

  const save = async (match: MovieContextMatch) => {
    setSavingId(match.match_id);
    try {
      await saveMovieMatch(match.match_id);
      setMatches((current) =>
        current?.map((item) => (item.match_id === match.match_id ? { ...item, is_saved: true } : item)) ?? null,
      );
    } catch (saveError) {
      setError(saveError);
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="surface p-7 space-y-4">
        <div className="flex items-center gap-2 font-display text-xl font-bold text-slate-900">
          <Film className="w-5 h-5 text-indigo-600" /> Hear an idiom used in everyday dialogue
        </div>
        <p className="text-xs text-slate-500">
          Search a phrase to see it used in a real film clip (currently “Tears of Steel” and “The Little Shop of Horrors”) or in a simulated demo
          scene. Phrases found in neither get AI-written example lines read aloud. Listen, then repeat out loud.
        </p>

        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={phrase}
              maxLength={255}
              onChange={(event) => setPhrase(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && void search(phrase)}
              placeholder="e.g. piece of cake, break the ice..."
              className="w-full pl-10 pr-4 py-3 text-sm bg-white ring-1 ring-slate-900/10 rounded-2xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60 font-medium text-slate-900"
            />
          </div>
          <button
            onClick={() => void search(phrase)}
            disabled={isSearching || !phrase.trim()}
            className="px-6 py-3 bg-indigo-700 hover:bg-indigo-800 text-white font-bold text-sm rounded-2xl flex items-center gap-1.5 transition-all cursor-pointer active:scale-95 disabled:opacity-50"
          >
            {isSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : "Find lines"}
          </button>
        </div>

        <div className="flex items-center gap-2 pt-1 overflow-x-auto">
          <span className="text-xs font-semibold text-slate-400 shrink-0">Popular:</span>
          {POPULAR.map((item) => (
            <button
              key={item}
              onClick={() => void search(item)}
              disabled={isSearching}
              className="px-3.5 py-1.5 rounded-full bg-paper-deep hover:bg-indigo-100 hover:text-indigo-700 text-slate-700 text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer disabled:opacity-50"
            >
              “{item}”
            </button>
          ))}
        </div>
      </div>

      {error !== null && <ErrorNotice error={error} onRetry={phrase.trim() ? () => void search(phrase) : undefined} />}

      {isSearching && (
        <p className="text-sm text-slate-500 flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" /> Writing lines and recording them — this takes a few seconds...
        </p>
      )}

      {matches && !isSearching && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 items-start">
          {matches.map((match) => (
            <div key={match.match_id} className="surface p-5 space-y-4">
              {match.source_type === "real_video" && (
                <p className="text-[11px] font-bold text-slate-500 flex items-center gap-1.5">
                  <Film className="w-3.5 h-3.5" /> {match.title} <span className="tag">{match.platform === "demo" ? "demo scene" : "film clip"}</span>
                </p>
              )}
              <div className="p-4 rounded-2xl bg-indigo-50 border-l-4 border-indigo-400 text-base text-indigo-950 italic font-serif leading-relaxed">
                “{match.phrase_text}”
              </div>
              <div className="flex items-center justify-between">
                <button
                  onClick={() => (match.source_type === "real_video" ? setWatchingId(match.match_id) : void togglePlay(match))}
                  className="text-xs font-bold text-indigo-600 hover:text-indigo-700 flex items-center gap-1.5 cursor-pointer"
                >
                  {playingId === match.match_id ? (
                    <Square className="w-3.5 h-3.5 fill-indigo-600" />
                  ) : (
                    <Play className="w-3.5 h-3.5 fill-indigo-600" />
                  )}
                  {match.source_type === "real_video" ? "Watch scene" : playingId === match.match_id ? "Stop" : "Listen"}
                </button>
                <button
                  onClick={() => void save(match)}
                  disabled={match.is_saved || savingId === match.match_id}
                  aria-label={match.is_saved ? "Saved" : "Save line"}
                  className={`p-2 rounded-xl transition-colors cursor-pointer ${
                    match.is_saved ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                  }`}
                >
                  {match.is_saved ? <Check className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {watching && (
        <VideoPlayerOverlay match={watching} onClose={() => setWatchingId(null)} onSave={() => void save(watching)} />
      )}
    </div>
  );
};
