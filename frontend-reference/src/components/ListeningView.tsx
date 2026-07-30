import React, { useState } from "react";
import { MovieMatch } from "../types";
import { VideoPlayerOverlay } from "./VideoPlayerOverlay";
import {
  Headphones,
  Film,
  Search,
  Play,
  Pause,
  RotateCcw,
  RotateCw,
  Volume2,
  Sparkles,
  CheckCircle2,
  Languages,
  Mic,
  Bookmark,
  Check,
  Zap,
  Sliders,
  ChevronRight
} from "lucide-react";

export const ListeningView: React.FC = () => {
  const [subMode, setSubMode] = useState<"listening" | "movies">("listening");

  // Listening Audio Player State
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1.0);
  const [progress, setProgress] = useState(25);
  const [showTranslation, setShowTranslation] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState("Spanish");

  // Dictation Mode State
  const [userDictationInput, setUserDictationInput] = useState("");
  const [accuracyScore, setAccuracyScore] = useState<number | null>(null);
  const targetDictationSegment = "We need to iron out the contractual details before signing.";

  // Movie Context Search State
  const [searchPhrase, setSearchPhrase] = useState("piece of cake");
  const [isSearchingMovies, setIsSearchingMovies] = useState(false);
  const [selectedMovieForOverlay, setSelectedMovieForOverlay] = useState<MovieMatch | null>(null);

  const [movieResults, setMovieResults] = useState<MovieMatch[]>([
    {
      id: 1,
      movieTitle: "The Startup Hustle",
      timestamp: "01:14:22",
      image: "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=600&auto=format&fit=crop&q=80",
      speakerA: "I'm not sure I'm ready for tomorrow.",
      speakerB: "Don't worry about the presentation tomorrow. For you, pitching to investors is a piece of cake. Just remember to breathe.",
      speakerA2: "Easy for you to say.",
      saved: false
    },
    {
      id: 2,
      movieTitle: "Family Ties",
      timestamp: "00:45:10",
      image: "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?w=600&auto=format&fit=crop&q=80",
      speakerA: "How hard can managing a household really be?",
      speakerB: "You think raising three kids while working full time is a piece of cake? Try doing it for twenty years.",
      speakerA2: "I didn't mean it like that.",
      saved: true
    },
    {
      id: 3,
      movieTitle: "Baking with Buster",
      timestamp: "00:12:05",
      image: "https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=600&auto=format&fit=crop&q=80",
      speakerA: "Buster, is baking chocolate cookies difficult?",
      speakerB: "Now, mix the flour and sugar together. See? Making these cookies is a piece of cake!",
      speakerA2: "Yum! That looks so easy!",
      saved: false
    }
  ]);

  const handleSearchMoviePhrases = async () => {
    if (!searchPhrase.trim()) return;
    setIsSearchingMovies(true);

    try {
      const res = await fetch("/api/ai/movie-context", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phrase: searchPhrase })
      });
      const data = await res.json();
      if (data.matches) {
        setMovieResults(data.matches);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsSearchingMovies(false);
    }
  };

  const handleCheckDictation = () => {
    const cleanUser = userDictationInput.trim().toLowerCase().replace(/[^a-z0-9 ]/g, "");
    const cleanTarget = targetDictationSegment.trim().toLowerCase().replace(/[^a-z0-9 ]/g, "");

    if (cleanUser === cleanTarget) {
      setAccuracyScore(100);
    } else {
      const userWords = cleanUser.split(" ");
      const targetWords = cleanTarget.split(" ");
      let matched = 0;
      userWords.forEach((w) => {
        if (targetWords.includes(w)) matched++;
      });
      const score = Math.round((matched / targetWords.length) * 100);
      setAccuracyScore(Math.min(100, Math.max(20, score)));
    }
  };

  const playTTS = (text: string) => {
    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-US";
      utterance.rate = playbackSpeed;
      window.speechSynthesis.speak(utterance);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* View Sub-Toggle Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Headphones className="w-6 h-6 text-indigo-600" /> Listening & Movie Context Hub
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Train native listening comprehension, dictation accuracy, and explore idiom usages in movie clips.
          </p>
        </div>

        {/* Tab Toggle */}
        <div className="inline-flex p-1 bg-slate-200/60 rounded-2xl border border-slate-200">
          <button
            onClick={() => setSubMode("listening")}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              subMode === "listening"
                ? "bg-white text-indigo-600 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Headphones className="w-3.5 h-3.5 inline mr-1.5" /> AI Podcast & Dictation
          </button>
          <button
            onClick={() => setSubMode("movies")}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              subMode === "movies"
                ? "bg-white text-indigo-600 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Film className="w-3.5 h-3.5 inline mr-1.5" /> Movie Context Finder
          </button>
        </div>
      </div>

      {subMode === "listening" ? (
        /* Listening & Dictation Mode */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Main Audio Player & Dictation Card (7 Cols) */}
          <div className="lg:col-span-7 bg-white rounded-3xl border border-slate-200/80 p-6 md:p-8 shadow-xs space-y-6">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold px-3 py-1 rounded-full bg-purple-50 text-purple-700">
                Episode 14 • Business English
              </span>
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
                <span>Speed:</span>
                {[0.8, 1.0, 1.25, 1.5].map((spd) => (
                  <button
                    key={spd}
                    onClick={() => setPlaybackSpeed(spd)}
                    className={`px-2 py-0.5 rounded-lg text-[11px] font-bold cursor-pointer transition-colors ${
                      playbackSpeed === spd
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    {spd}x
                  </button>
                ))}
              </div>
            </div>

            {/* Audio Title & Artwork Banner */}
            <div className="p-6 rounded-2xl bg-gradient-to-br from-indigo-900 to-slate-900 text-white relative overflow-hidden flex items-center justify-between">
              <div className="relative z-10 max-w-sm">
                <span className="text-[10px] uppercase font-bold tracking-wider text-indigo-300">
                  AI Generated Conversation
                </span>
                <h3 className="text-xl font-extrabold tracking-tight mt-1 mb-2">
                  Ironing Out Contractual Details in Q3
                </h3>
                <p className="text-xs text-slate-300">
                  Speakers: Alex (US) & Sophia (UK)
                </p>
              </div>

              {/* Simulated Waveform Animation */}
              <div className="flex items-center gap-1 h-12">
                {[40, 70, 30, 90, 60, 100, 45, 80, 50, 30, 85, 60].map((h, i) => (
                  <div
                    key={i}
                    className={`w-1.5 bg-indigo-400 rounded-full transition-all duration-300 ${
                      isPlaying ? "animate-pulse" : ""
                    }`}
                    style={{ height: `${isPlaying ? h : 20}%` }}
                  ></div>
                ))}
              </div>
            </div>

            {/* Interactive Audio Controls */}
            <div className="space-y-3">
              <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden cursor-pointer">
                <div className="bg-indigo-600 h-full rounded-full" style={{ width: `${progress}%` }}></div>
              </div>

              <div className="flex items-center justify-between text-xs text-slate-500 font-mono">
                <span>01:15</span>
                <span>04:30</span>
              </div>

              <div className="flex items-center justify-center gap-6 pt-2">
                <button
                  onClick={() => setProgress(Math.max(0, progress - 10))}
                  className="p-2 text-slate-500 hover:text-slate-900 transition-colors cursor-pointer"
                  title="Rewind 10s"
                >
                  <RotateCcw className="w-5 h-5" />
                </button>

                <button
                  onClick={() => {
                    setIsPlaying(!isPlaying);
                    if (!isPlaying) playTTS(targetDictationSegment);
                  }}
                  className="p-4 rounded-full bg-indigo-600 hover:bg-indigo-700 text-white shadow-lg shadow-indigo-200 transition-transform active:scale-95 cursor-pointer"
                >
                  {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6 fill-white ml-0.5" />}
                </button>

                <button
                  onClick={() => setProgress(Math.min(100, progress + 10))}
                  className="p-2 text-slate-500 hover:text-slate-900 transition-colors cursor-pointer"
                  title="Forward 10s"
                >
                  <RotateCw className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Dictation Mode Box */}
            <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                  <Mic className="w-4 h-4 text-indigo-600" /> Active Dictation Practice
                </span>
                <button
                  onClick={() => playTTS(targetDictationSegment)}
                  className="text-xs font-semibold text-indigo-600 hover:underline flex items-center gap-1 cursor-pointer"
                >
                  <Volume2 className="w-3.5 h-3.5" /> Replay Segment
                </button>
              </div>

              <textarea
                rows={2}
                value={userDictationInput}
                onChange={(e) => setUserDictationInput(e.target.value)}
                placeholder="Type the exact sentence segment you just heard..."
                className="w-full p-3 text-xs bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 text-slate-800"
              />

              <div className="flex items-center justify-between">
                <button
                  onClick={handleCheckDictation}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-xs cursor-pointer"
                >
                  Check Dictation
                </button>

                {accuracyScore !== null && (
                  <div className="flex items-center gap-2 text-xs font-bold">
                    <span>Accuracy:</span>
                    <span
                      className={`px-2.5 py-1 rounded-full text-white ${
                        accuracyScore >= 80 ? "bg-emerald-600" : "bg-amber-500"
                      }`}
                    >
                      {accuracyScore}%
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Synced Transcript Panel (5 Cols) */}
          <div className="lg:col-span-5 bg-white rounded-3xl border border-slate-200/80 p-6 shadow-xs flex flex-col justify-between">
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <h3 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                  <Languages className="w-4 h-4 text-indigo-600" /> Synced Transcript
                </h3>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowTranslation(!showTranslation)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                      showTranslation ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {showTranslation ? "Hide Translation" : "Translate"}
                  </button>
                </div>
              </div>

              {/* Line by Line Transcript */}
              <div className="space-y-3 text-xs leading-relaxed">
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <p className="font-bold text-slate-900 mb-0.5">Alex (00:10):</p>
                  <p className="text-slate-700">"I'd like to bring up the timeline for our Q3 deliverables."</p>
                  {showTranslation && (
                    <p className="text-[11px] text-indigo-600 font-medium italic mt-1">
                      Me gustaría presentar el cronograma para los entregables del tercer trimestre.
                    </p>
                  )}
                </div>

                <div className="p-3 rounded-xl bg-indigo-50/80 border border-indigo-200 text-indigo-950 font-medium">
                  <p className="font-bold text-indigo-800 mb-0.5 flex items-center justify-between">
                    <span>Sophia (00:25):</span>
                    <span className="text-[10px] bg-indigo-200 text-indigo-800 px-1.5 py-0.2 rounded font-bold">Active</span>
                  </p>
                  <p className="text-indigo-950">"We need to iron out the contractual details before signing."</p>
                  {showTranslation && (
                    <p className="text-[11px] text-indigo-700 font-semibold italic mt-1">
                      Necesitamos resolver los detalles contractuales antes de firmar.
                    </p>
                  )}
                </div>

                <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <p className="font-bold text-slate-900 mb-0.5">Alex (00:42):</p>
                  <p className="text-slate-700">"Agreed. Let's make sure everyone stands behind the agreement."</p>
                  {showTranslation && (
                    <p className="text-[11px] text-indigo-600 font-medium italic mt-1">
                      De acuerdo. Asegurémonos de que todos apoyen el acuerdo.
                    </p>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-6 pt-3 border-t border-slate-100 text-[11px] text-slate-400">
              Target CEFR B2 Business Idioms
            </div>
          </div>
        </div>
      ) : (
        /* Movie Context Finder Mode */
        <div className="space-y-6">
          {/* Search Box */}
          <div className="p-6 bg-white rounded-3xl border border-slate-200/80 shadow-xs space-y-4">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-900 uppercase tracking-wide">
              <Film className="w-4 h-4 text-indigo-600" /> Search Native Idioms in Movie Scenes
            </div>

            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchPhrase}
                  onChange={(e) => setSearchPhrase(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearchMoviePhrases()}
                  placeholder="e.g. piece of cake, hit the nail on the head, break the ice..."
                  className="w-full pl-10 pr-4 py-2.5 text-xs bg-slate-50 border border-slate-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 font-medium text-slate-900"
                />
              </div>
              <button
                onClick={handleSearchMoviePhrases}
                disabled={isSearchingMovies}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-2xl shadow-md shadow-indigo-200 flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
              >
                {isSearchingMovies ? <Sparkles className="w-4 h-4 animate-spin" /> : "Find Scenes"}
              </button>
            </div>

            {/* Popular Idiom Pills */}
            <div className="flex items-center gap-2 pt-1 overflow-x-auto">
              <span className="text-xs font-semibold text-slate-400 shrink-0">Popular:</span>
              {["piece of cake", "break the ice", "under the weather", "spill the beans", "bite the bullet"].map((p) => (
                <button
                  key={p}
                  onClick={() => {
                    setSearchPhrase(p);
                    handleSearchMoviePhrases();
                  }}
                  className="px-3 py-1 rounded-xl bg-slate-100 hover:bg-indigo-50 hover:text-indigo-600 text-slate-700 text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer"
                >
                  "{p}"
                </button>
              ))}
            </div>
          </div>

          {/* Results Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {movieResults.map((match) => (
              <div
                key={match.id}
                className="bg-white rounded-3xl border border-slate-200/80 overflow-hidden shadow-xs hover:shadow-lg transition-all duration-200 group flex flex-col justify-between"
              >
                <div>
                  {/* Video Thumbnail */}
                  <div
                    onClick={() => setSelectedMovieForOverlay(match)}
                    className="relative h-48 bg-slate-900 overflow-hidden cursor-pointer"
                  >
                    <img
                      src={match.image}
                      alt={match.movieTitle}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300 opacity-90"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-black/20 to-transparent"></div>

                    {/* Play Icon Badge */}
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="w-12 h-12 rounded-full bg-indigo-600/90 text-white flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
                        <Play className="w-5 h-5 fill-white ml-0.5" />
                      </div>
                    </div>

                    <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between text-white text-xs">
                      <span className="font-bold">{match.movieTitle}</span>
                      <span className="font-mono text-[11px] bg-black/60 px-2 py-0.5 rounded">{match.timestamp}</span>
                    </div>
                  </div>

                  {/* Scene Dialogue Quote */}
                  <div className="p-5 space-y-3">
                    <div className="p-3 rounded-xl bg-indigo-50/70 border border-indigo-100 text-xs text-indigo-950 italic leading-relaxed">
                      "{match.speakerB}"
                    </div>
                    <p className="text-[11px] text-slate-500">
                      Context Speaker A: "{match.speakerA}"
                    </p>
                  </div>
                </div>

                <div className="px-5 pb-5 pt-1 flex items-center justify-between">
                  <button
                    onClick={() => setSelectedMovieForOverlay(match)}
                    className="text-xs font-bold text-indigo-600 hover:text-indigo-700 flex items-center gap-1 cursor-pointer"
                  >
                    Watch Full Clip <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => {
                      match.saved = !match.saved;
                      setMovieResults([...movieResults]);
                    }}
                    className={`p-2 rounded-xl transition-colors cursor-pointer ${
                      match.saved ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                    }`}
                  >
                    <Bookmark className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Video Overlay Modal */}
      {selectedMovieForOverlay && (
        <VideoPlayerOverlay
          match={selectedMovieForOverlay}
          onClose={() => setSelectedMovieForOverlay(null)}
        />
      )}
    </div>
  );
};
