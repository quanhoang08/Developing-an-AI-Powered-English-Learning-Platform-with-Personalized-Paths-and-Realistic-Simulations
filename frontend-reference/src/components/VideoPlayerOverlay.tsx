// Modal xem 1 cảnh video khớp cụm từ đã tìm (MovieContextPanel). Video là phim thật (platform "film")
// hoặc cảnh hội thoại MÔ PHỎNG do script seed dựng (platform "demo", phụ đề đã ghi cứng vào hình).
// Phim thật: phụ đề chạy theo thời gian phát, dòng chứa cụm từ đã tìm hiện màu hổ phách, các dòng
// thoại khác màu trắng. Video nằm sau JWT nên tải về dạng blob rồi mới gán cho <video>.
import React, { useEffect, useRef, useState } from "react";
import { Bookmark, Check, Film, Loader2, RotateCcw, X } from "lucide-react";
import { fetchAudioObjectUrl, getMovieSubtitles, MovieContextMatch, SubtitleCue } from "../api";

interface VideoPlayerOverlayProps {
  match: MovieContextMatch;
  onClose: () => void;
  onSave: () => void;
}

// Ghi công bắt buộc theo giấy phép của từng phim (khoá = title đã nạp bằng scripts/ingest_video.py).
// ponytail: bảng cứng trong code; thêm cột credit cho video_sources nếu số phim tăng lên.
const FILM_CREDITS: Record<string, string> = {
  "Tears of Steel": "“Tears of Steel” © Blender Foundation | mango.blender.org — CC BY 3.0",
  "The Little Shop of Horrors": "“The Little Shop of Horrors” (1960, dir. Roger Corman) — public domain (Wikimedia Commons)",
};

// Lùi lại một đoạn trước dòng khớp để người học nghe được ngữ cảnh.
const LEAD_IN_MS = 2500;

const formatTime = (ms: number) => {
  const total = Math.floor(ms / 1000);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
};

export const VideoPlayerOverlay: React.FC<VideoPlayerOverlayProps> = ({ match, onClose, onSave }) => {
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const startMs = match.start_ms ?? 0;
  const [cues, setCues] = useState<SubtitleCue[]>([]);
  const [activeCue, setActiveCue] = useState<SubtitleCue | null>(null);

  // Cảnh mô phỏng đã có phụ đề ghi trong hình — chỉ phim thật mới cần lớp phụ đề này.
  useEffect(() => {
    if (match.platform === "demo") return;
    getMovieSubtitles(match.match_id)
      .then(setCues)
      .catch(() => setCues([]));
  }, [match.match_id, match.platform]);

  // Dòng đang được nói tại thời điểm phát hiện tại; chỉ setState khi đổi dòng để không render lại mỗi khung hình.
  const syncSubtitle = (currentSeconds: number) => {
    const nowMs = currentSeconds * 1000;
    const cue = cues.find((entry) => nowMs >= entry.start_ms && nowMs <= entry.end_ms + 250) ?? null;
    setActiveCue((previous) => (previous === cue ? previous : cue));
  };

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    if (!match.video_url) {
      setError("This match has no video.");
      return;
    }
    fetchAudioObjectUrl(match.video_url)
      .then((url) => {
        objectUrl = url;
        if (cancelled) URL.revokeObjectURL(url);
        else setVideoUrl(url);
      })
      .catch(() => setError("Could not load the video. Try again."));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [match.video_url]);

  const replayLine = () => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Math.max(0, startMs - LEAD_IN_MS) / 1000;
    void video.play();
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 text-white rounded-3xl max-w-4xl w-full shadow-2xl overflow-hidden border border-slate-800">
        <div className="p-4 px-6 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-600/30 text-indigo-400 rounded-xl border border-indigo-500/30">
              <Film className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-white">{match.title ?? "Scene"}</h3>
              <p className="text-xs text-slate-400">
                {match.platform === "demo"
                  ? "Simulated demo scene — AI voices, not a real movie"
                  : (FILM_CREDITS[match.title ?? ""] ?? "Film clip")}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-2 rounded-full hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3">
          <div className="relative lg:col-span-2 bg-black aspect-video flex items-center justify-center">
            {error ? (
              <p className="text-sm text-rose-300 px-6 text-center">{error}</p>
            ) : videoUrl ? (
              <video
                ref={videoRef}
                src={videoUrl}
                controls
                autoPlay
                playsInline
                className="w-full h-full"
                onLoadedMetadata={(event) => {
                  event.currentTarget.currentTime = Math.max(0, startMs - LEAD_IN_MS) / 1000;
                }}
                onTimeUpdate={(event) => syncSubtitle(event.currentTarget.currentTime)}
                onSeeked={(event) => syncSubtitle(event.currentTarget.currentTime)}
              />
            ) : (
              <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            )}
            {/* Nằm trên thanh điều khiển của <video> (bottom-14) và không chặn click vào video. */}
            {activeCue && (
              <p
                className={`absolute inset-x-4 bottom-14 text-center pointer-events-none text-base sm:text-lg font-semibold leading-snug [text-shadow:0_2px_6px_rgba(0,0,0,0.95)] ${
                  activeCue.is_match ? "text-amber-300" : "text-white"
                }`}
              >
                {activeCue.text}
              </p>
            )}
          </div>

          <div className="p-6 border-l border-slate-800 flex flex-col justify-between gap-6">
            <div className="space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Line with your phrase</h4>
              <div className="p-3 rounded-xl bg-indigo-950/60 border border-indigo-500/40">
                <p className="font-semibold text-white leading-relaxed text-sm">“{match.phrase_text}”</p>
                <p className="mt-2 text-[11px] font-mono text-indigo-300">
                  {formatTime(startMs)} – {formatTime(match.end_ms ?? startMs)}
                </p>
              </div>
              <button
                onClick={replayLine}
                disabled={!videoUrl}
                className="flex items-center gap-1.5 text-xs font-bold text-indigo-300 hover:text-white disabled:opacity-40 cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Replay this line
              </button>
            </div>

            <button
              onClick={onSave}
              disabled={match.is_saved}
              className={`flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-colors ${
                match.is_saved
                  ? "bg-amber-500/20 text-amber-400 border border-amber-500/40"
                  : "bg-slate-800 text-slate-200 hover:bg-slate-700 cursor-pointer"
              }`}
            >
              {match.is_saved ? <Check className="w-3.5 h-3.5" /> : <Bookmark className="w-3.5 h-3.5" />}
              {match.is_saved ? "Saved" : "Save scene"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
