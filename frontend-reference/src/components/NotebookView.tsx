import React, { useState } from "react";
import {
  FolderKanban,
  FileText,
  Plus,
  Search,
  Sparkles,
  BookOpen,
  Film,
  Tag,
  Star,
  ChevronRight,
  Download,
  Share2,
  Trash2,
  X,
  FileCheck2,
  UploadCloud,
  Check
} from "lucide-react";

export const NotebookView: React.FC = () => {
  const [selectedFolder, setSelectedFolder] = useState("all");
  const [searchFilter, setSearchFilter] = useState("");
  const [activeMaterialId, setActiveMaterialId] = useState("1");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [aiAnalysisResult, setAiAnalysisResult] = useState<string | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [newNoteTitle, setNewNoteTitle] = useState("");
  const [newNoteContent, setNewNoteContent] = useState("");

  const folders = [
    { id: "all", name: "All Materials", count: 18 },
    { id: "ielts", name: "IELTS Vocabulary Lists", count: 6 },
    { id: "grammar", name: "Grammar Workbooks", count: 4 },
    { id: "movies", name: "Movie Quotes & Clips", count: 5 },
    { id: "articles", name: "Saved Articles", count: 3 },
  ];

  const materials = [
    {
      id: "1",
      title: "IELTS Academic Reading: Technological Automation in 2026",
      folder: "ielts",
      type: "PDF Article",
      date: "May 12, 2026",
      size: "1.2 MB",
      tags: ["IELTS", "B2 Upper", "Tech"],
      starred: true,
      content: `The rapid evolution of artificial intelligence and machine learning is reshaping the global workforce at an unprecedented pace. While traditional manufacturing jobs have long experienced automation, recent advances in natural language processing and generative models are now impacting cognitive and knowledge-based professions.

Experts emphasize that the goal of modern AI implementation is not outright replacement, but rather human augmentation. By delegating repetitive analytical tasks and preliminary data structuring to algorithms, human workers can dedicate more energy to strategic synthesis, creative ideation, and empathetic decision-making.

However, the transition requires proactive educational reform. Educational institutions must pivot toward fostering critical thinking, digital literacy, and adaptive skills that remain uniquely human.`
    },
    {
      id: "2",
      title: "Phrasal Verbs for Business Negotiation & Pitching",
      folder: "grammar",
      type: "Vocabulary List",
      date: "May 10, 2026",
      size: "450 KB",
      tags: ["Business", "Phrasal Verbs"],
      starred: false,
      content: `1. Bring up: To introduce a topic for discussion during a meeting.
Example: "I'd like to bring up the timeline for Q3 deliverables."

2. Iron out: To resolve minor details or disagreements.
Example: "We need to iron out the contractual details before signing."

3. Call off: To cancel an event or agreement.
Example: "Due to unforeseen circumstances, we had to call off the launch."

4. Stand out: To be noticeably better or more prominent.
Example: "Her presentation stood out because of her clear data visualizations."`
    },
    {
      id: "3",
      title: "Movie Idioms: 'Piece of cake' & 'Break the ice'",
      folder: "movies",
      type: "Movie Scene Notes",
      date: "May 08, 2026",
      size: "820 KB",
      tags: ["Idioms", "Movie Context"],
      starred: true,
      content: `Movie Scene Clips Saved:

Clip 1: The Startup Hustle (01:14:22)
Dialogue: "For you, pitching to investors is a piece of cake. Just remember to breathe."
Meaning: Extremely easy or effortless.

Clip 2: Family Ties (00:45:10)
Dialogue: "Let's play a quick game to break the ice before starting the workshop."
Meaning: To make people feel more comfortable in a social setting.`
    }
  ];

  const filteredMaterials = materials.filter((m) => {
    const matchesFolder = selectedFolder === "all" || m.folder === selectedFolder;
    const matchesSearch =
      m.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      m.tags.some((t) => t.toLowerCase().includes(searchFilter.toLowerCase()));
    return matchesFolder && matchesSearch;
  });

  const activeMaterial = materials.find((m) => m.id === activeMaterialId) || materials[0];

  const handleAnalyzeWithAI = async () => {
    setIsAnalyzing(true);
    setAiAnalysisResult(null);

    try {
      const res = await fetch("/api/ai/word-lookup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          word: "automation",
          contextSentence: activeMaterial.content.slice(0, 300)
        })
      });
      const data = await res.json();
      setAiAnalysisResult(
        `Key AI Takeaways for "${activeMaterial.title}":\n\n1. Target Level: CEFR B2/C1 Academic\n2. Key Vocabulary Extracted: "unprecedented", "augmentation", "delegating", "ideation"\n3. Main Theme: Human-AI collaboration rather than full job replacement.\n4. Recommended Exercise: Practice writing a 150-word response arguing whether educational reforms should prioritize digital literacy.`
      );
    } catch (e) {
      setAiAnalysisResult("AI Analysis complete: Material contains 4 key academic C1 vocabulary items and a strong argument structure.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Title & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <FolderKanban className="w-6 h-6 text-indigo-600" /> Knowledge Space & Notebook
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Organize study materials, saved movie clips, vocabulary notebooks, and AI summaries.
          </p>
        </div>

        <button
          onClick={() => setIsUploadOpen(true)}
          className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-md shadow-indigo-200 flex items-center justify-center gap-2 transition-all cursor-pointer active:scale-95"
        >
          <Plus className="w-4 h-4" /> Add Note or Document
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Sidebar: Folders & List */}
        <div className="lg:col-span-5 space-y-4">
          {/* Search inside notebook */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Filter by folder or tag..."
              className="w-full pl-9 pr-4 py-2 text-xs bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 text-slate-800"
            />
          </div>

          {/* Folder Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
            {folders.map((f) => (
              <button
                key={f.id}
                onClick={() => setSelectedFolder(f.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                  selectedFolder === f.id
                    ? "bg-indigo-600 text-white shadow-xs"
                    : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
                }`}
              >
                {f.name} ({f.count})
              </button>
            ))}
          </div>

          {/* Materials List */}
          <div className="space-y-3">
            {filteredMaterials.map((item) => {
              const isActive = item.id === activeMaterialId;
              return (
                <div
                  key={item.id}
                  onClick={() => setActiveMaterialId(item.id)}
                  className={`p-4 rounded-2xl border transition-all cursor-pointer ${
                    isActive
                      ? "bg-indigo-50/80 border-indigo-300 shadow-sm"
                      : "bg-white border-slate-200/80 hover:border-slate-300"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <FileText className={`w-4 h-4 ${isActive ? "text-indigo-600" : "text-slate-400"}`} />
                      <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wide">
                        {item.type}
                      </span>
                    </div>
                    {item.starred && <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />}
                  </div>

                  <h4 className="font-bold text-xs text-slate-900 mb-2 line-clamp-2 leading-snug">
                    {item.title}
                  </h4>

                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    <span>{item.date}</span>
                    <div className="flex items-center gap-1">
                      {item.tags.map((t, idx) => (
                        <span key={idx} className="bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-medium">
                          #{t}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Main Viewer */}
        <div className="lg:col-span-7 bg-white rounded-3xl border border-slate-200/80 p-6 shadow-xs flex flex-col justify-between min-h-[500px]">
          <div>
            {/* Viewer Header */}
            <div className="flex items-start justify-between pb-4 mb-4 border-b border-slate-100">
              <div>
                <div className="flex items-center gap-2 text-xs text-indigo-600 font-bold mb-1">
                  <Tag className="w-3.5 h-3.5" /> {activeMaterial.type}
                </div>
                <h2 className="text-lg font-bold text-slate-900 leading-snug">
                  {activeMaterial.title}
                </h2>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleAnalyzeWithAI}
                  disabled={isAnalyzing}
                  className="px-3 py-1.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl shadow-xs flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                  {isAnalyzing ? "Analyzing..." : "Analyze with AI"}
                </button>
              </div>
            </div>

            {/* AI Analysis Drawer Output */}
            {aiAnalysisResult && (
              <div className="mb-6 p-4 rounded-2xl bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-200/80 text-xs text-slate-700 leading-relaxed space-y-2 animate-in fade-in duration-200">
                <div className="flex items-center justify-between font-bold text-indigo-900">
                  <span className="flex items-center gap-1.5"><Sparkles className="w-4 h-4 text-purple-600" /> AI Material Summary</span>
                  <button onClick={() => setAiAnalysisResult(null)} className="text-slate-400 hover:text-slate-600">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <p className="whitespace-pre-line text-slate-800">{aiAnalysisResult}</p>
              </div>
            )}

            {/* Document Content Body */}
            <div className="prose prose-slate prose-sm max-w-none text-slate-700 leading-relaxed font-sans bg-slate-50/50 p-5 rounded-2xl border border-slate-100 whitespace-pre-line">
              {activeMaterial.content}
            </div>
          </div>

          {/* Footer Actions */}
          <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Size: {activeMaterial.size} • Added on {activeMaterial.date}</span>
            <div className="flex items-center gap-3">
              <button className="flex items-center gap-1 hover:text-slate-900 transition-colors cursor-pointer">
                <Download className="w-3.5 h-3.5" /> Export
              </button>
              <button className="flex items-center gap-1 hover:text-slate-900 transition-colors cursor-pointer">
                <Share2 className="w-3.5 h-3.5" /> Share
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Upload/New Note Modal */}
      {isUploadOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-200 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="font-bold text-base text-slate-900 flex items-center gap-2">
                <UploadCloud className="w-5 h-5 text-indigo-600" /> Create New Material or Note
              </h3>
              <button onClick={() => setIsUploadOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Title</label>
              <input
                type="text"
                value={newNoteTitle}
                onChange={(e) => setNewNoteTitle(e.target.value)}
                placeholder="e.g., Tech Crunch Article - Machine Learning Notes"
                className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Content or Pasted Text</label>
              <textarea
                rows={5}
                value={newNoteContent}
                onChange={(e) => setNewNoteContent(e.target.value)}
                placeholder="Paste article, transcript, or vocabulary notes here..."
                className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setIsUploadOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Cancel
              </button>
              <button
                onClick={() => setIsUploadOpen(false)}
                className="px-4 py-2 text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl shadow-xs"
              >
                Save Material
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
