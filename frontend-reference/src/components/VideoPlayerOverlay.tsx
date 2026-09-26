// Modal xem 1 cảnh phim khớp idiom đã tìm (ListeningView). Player là ảnh tĩnh + progress bar
// giả lập (chưa có video thật/kho phụ đề — tier "Định hướng mở rộng", chưa build).
import React, { useState } from "react";
import { MovieMatch } from "../types";
import {
  X,
  Play,
  Pause,
  RotateCcw,
  Volume2,
  VolumeX,
  Bookmark,
  Check,
  Subtitles,
  Film,
  Sparkles
} from "lucide-react";

interface VideoPlayerOverlayProps {
  match: MovieMatch | null;
  onClose: () => void;
}

export const VideoPlayerOverlay: React.FC<VideoPlayerOverlayProps> = ({
  match,
  onClose,
}) => {
  const [isPlaying, setIsPlaying] = useState(true);
  const [isMuted, setIsMuted] = useState(false);
  const [isSaved, setIsSaved] = useState(match?.saved || false);
  const [showSubtitles, setShowSubtitles] = useState(true);
  const [progress, setProgress] = useState(42);

  if (!match) return null;

  const togglePlay = () => setIsPlaying(!isPlaying);
  const toggleSave = () => setIsSaved(!isSaved);

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 text-white rounded-3xl max-w-4xl w-full shadow-2xl overflow-hidden border border-slate-800 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="p-4 px-6 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-600/30 text-indigo-400 rounded-xl border border-indigo-500/30">
              <Film className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-white flex items-center gap-2">
                {match.movieTitle}
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                  {match.timestamp}
                </span>
              </h3>
              <p className="text-xs text-slate-400">Movie Context Clip - Real Native Dialogue</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3">
          {/* Main Simulated Video Screen */}
          <div className="lg:col-span-2 bg-black relative aspect-video flex flex-col justify-end group">
            <img
              src={match.image}
              alt={match.movieTitle}
              className="absolute inset-0 w-full h-full object-cover opacity-85"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent"></div>

            {/* Simulated Live Closed Caption */}
            {showSubtitles && (
              <div className="relative z-10 px-6 py-4 text-center">
                <p className="inline-block bg-black/80 backdrop-blur-xs text-yellow-300 px-4 py-2 rounded-xl text-sm font-semibold border border-yellow-500/20 shadow-lg">
                  "{match.speakerB}"
                </p>
              </div>
            )}

            {/* Video Controls Overlay */}
            <div className="relative z-10 p-4 px-6 bg-gradient-to-t from-slate-950 via-slate-950/80 to-transparent space-y-3">
              {/* Timeline Progress */}
              <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden cursor-pointer relative">
                <div
                  className="bg-indigo-500 h-full rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>

              <div className="flex items-center justify-between text-xs text-slate-300">
                <div className="flex items-center gap-4">
                  <button
                    onClick={togglePlay}
                    className="p-2 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white transition-colors cursor-pointer"
                  >
                    {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-white" />}
                  </button>
                  <button
                    onClick={() => setProgress(0)}
                    className="p-1.5 hover:text-white text-slate-400 transition-colors cursor-pointer"
                    title="Replay Clip"
                  >
                    <RotateCcw className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setIsMuted(!isMuted)}
                    className="p-1.5 hover:text-white text-slate-400 transition-colors cursor-pointer"
                  >
                    {isMuted ? <VolumeX className="w-4 h-4 text-rose-400" /> : <Volume2 className="w-4 h-4" />}
                  </button>
                  <span className="font-mono text-[11px] text-slate-400">00:14 / 00:30</span>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setShowSubtitles(!showSubtitles)}
                    className={`p-1.5 rounded transition-colors ${
                      showSubtitles ? "text-indigo-400 bg-indigo-950/60" : "text-slate-500"
                    }`}
                    title="Toggle Subtitles"
                  >
                    <Subtitles className="w-4 h-4" />
                  </button>
                  <button
                    onClick={toggleSave}
                    className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${
                      isSaved ? "bg-amber-500/20 text-amber-400 border border-amber-500/40" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                    }`}
                  >
                    {isSaved ? <Check className="w-3.5 h-3.5" /> : <Bookmark className="w-3.5 h-3.5" />}
                    {isSaved ? "Saved" : "Save Clip"}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Context Transcript Side Panel */}
          <div className="p-6 bg-slate-900 border-l border-slate-800 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="w-4 h-4 text-indigo-400" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Full Context Dialogue
                </h4>
              </div>

              <div className="space-y-4 text-xs">
                {/* Speaker A */}
                <div className="p-3 rounded-xl bg-slate-800/60 border border-slate-800">
                  <p className="font-semibold text-slate-400 mb-1">Speaker A:</p>
                  <p className="text-slate-200 leading-relaxed">"{match.speakerA}"</p>
                </div>

                {/* Speaker B (Target) */}
                <div className="p-3 rounded-xl bg-indigo-950/60 border border-indigo-500/40 text-indigo-100">
                  <p className="font-bold text-indigo-300 mb-1 flex items-center justify-between">
                    <span>Speaker B (Target Phrase):</span>
                    <span className="text-[10px] bg-indigo-500/30 px-1.5 py-0.5 rounded text-indigo-200">Featured</span>
                  </p>
                  <p className="font-semibold text-white leading-relaxed">"{match.speakerB}"</p>
                </div>

                {/* Speaker A2 */}
                <div className="p-3 rounded-xl bg-slate-800/60 border border-slate-800">
                  <p className="font-semibold text-slate-400 mb-1">Speaker A:</p>
                  <p className="text-slate-200 leading-relaxed">"{match.speakerA2}"</p>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-800 text-center">
              <p className="text-[11px] text-slate-400 leading-snug">
                Saved clips automatically appear in your Notebook under "Movie Clips"
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
