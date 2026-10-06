// Trang Knowledge Space: danh sách folder/document thật (sau login) hoặc demo (trước login),
// xem nội dung, và chat RAG (NotebookLM-style) trên tài liệu đã ingest xong.
import React, { useEffect, useRef, useState } from "react";
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
  Check,
  MessageSquare,
  Send,
  Quote,
  Loader2
} from "lucide-react";
import {
  ChatMessage,
  ChatProvider,
  createFolder,
  deleteDocument,
  getAccessToken,
  getChatHistory,
  listDocuments,
  listFolders,
  sendChatMessage,
  updateDocument,
  uploadDocument,
} from "../api";

interface NotebookViewProps {
  // authVersion thay đổi sau login/logout để buộc view tải lại dữ liệu backend.
  authVersion: number;
}

export const NotebookView: React.FC<NotebookViewProps> = ({ authVersion }) => {
  const [selectedFolder, setSelectedFolder] = useState("all");
  const [searchFilter, setSearchFilter] = useState("");
  const [activeMaterialId, setActiveMaterialId] = useState("1");
  const [viewMode, setViewMode] = useState<"content" | "chat">("content");
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [newNoteTitle, setNewNoteTitle] = useState("");
  const [newNoteContent, setNewNoteContent] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  // Backend ingest đồng bộ (chunk + embed) nên upload có thể mất vài chục giây: khóa nút và báo "đang xử lý".
  const [isUploading, setIsUploading] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  // Model dùng cho Chat RAG — người dùng chuyển được giữa Gemini (cloud) và Ollama (local).
  const [chatProvider, setChatProvider] = useState<ChatProvider>(() => {
    try {
      return localStorage.getItem("chatProvider") === "ollama" ? "ollama" : "gemini";
    } catch {
      return "gemini";
    }
  });
  const handleProviderChange = (provider: ChatProvider) => {
    setChatProvider(provider);
    try {
      localStorage.setItem("chatProvider", provider);
    } catch {
      // localStorage không khả dụng: lựa chọn chỉ có hiệu lực trong phiên hiện tại.
    }
  };
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [isChatSending, setIsChatSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const demoFolders = [
    { id: "all", name: "All Materials", count: 18 },
    { id: "ielts", name: "IELTS Vocabulary Lists", count: 6 },
    { id: "grammar", name: "Grammar Workbooks", count: 4 },
    { id: "movies", name: "Movie Quotes & Clips", count: 5 },
    { id: "articles", name: "Saved Articles", count: 3 },
  ];

  const demoMaterials = [
    {
      id: "1",
      title: "IELTS Academic Reading: Technological Automation in 2026",
      folder: "ielts",
      type: "PDF Article",
      date: "May 12, 2026",
      size: "1.2 MB",
      tags: ["IELTS", "B2 Upper", "Tech"],
      starred: true,
      isDemo: true,
      status: "demo",
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
      isDemo: true,
      status: "demo",
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
      isDemo: true,
      status: "demo",
      content: `Movie Scene Clips Saved:

Clip 1: The Startup Hustle (01:14:22)
Dialogue: "For you, pitching to investors is a piece of cake. Just remember to breathe."
Meaning: Extremely easy or effortless.

Clip 2: Family Ties (00:45:10)
Dialogue: "Let's play a quick game to break the ice before starting the workshop."
Meaning: To make people feel more comfortable in a social setting.`
    }
  ];

  const [folders, setFolders] = useState(demoFolders);
  const [materials, setMaterials] = useState(demoMaterials);

  useEffect(() => {
    // Không gọi backend khi chưa login để prototype vẫn hoạt động offline.
    if (!getAccessToken()) {
      setIsBackendConnected(false);
      setFolders(demoFolders);
      setMaterials(demoMaterials);
      return;
    }

    // Sau login, lấy folder/document thật và chuyển về shape mà UI hiện tại đang dùng.
    Promise.all([listFolders(), listDocuments()])
      .then(([backendFolders, backendDocuments]) => {
        setIsBackendConnected(true);
        setFolders([
          { id: "all", name: "All Materials", count: backendDocuments.total },
          ...backendFolders.map((folder) => ({ id: folder.id, name: folder.name, count: 0 })),
        ]);
        setMaterials(
          backendDocuments.items.map((document) => ({
            id: document.id,
            title: document.title,
            folder: document.folder_id || "all",
            type: document.source_type.toUpperCase(),
            date: new Date(document.created_at).toLocaleDateString(),
            size: `${document.file_size_kb || 0} KB`,
            tags: document.tags || [],
            starred: document.starred,
            isDemo: false,
            status: document.status,
            content:
              document.status === "ready"
                ? "Content ingested — ask questions about this document in the Chat tab."
                : document.status === "failed"
                ? "Ingestion failed for this file. Chat is unavailable until you upload a readable .docx."
                : "Document status: processing. Content will appear after ingestion.",
          })),
        );
      })
      .catch(() => {
        setIsBackendConnected(false);
      });
  }, [authVersion]);

  // Lọc danh sách hiển thị theo folder đang chọn + ô tìm kiếm (title hoặc tag).
  const filteredMaterials = materials.filter((m) => {
    const matchesFolder = selectedFolder === "all" || m.folder === selectedFolder;
    const matchesSearch =
      m.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      m.tags.some((t) => t.toLowerCase().includes(searchFilter.toLowerCase()));
    return matchesFolder && matchesSearch;
  });

  // Đã kết nối mà chưa có tài liệu nào: hiện khung trống, không mượn tài liệu demo làm nội dung.
  const emptyMaterial = {
    id: "1", title: "No documents yet", folder: "all", type: "EMPTY", date: "—", size: "—", tags: [] as string[],
    starred: false, isDemo: false, status: "empty",
    content: "Upload a .docx or audio file with \"Add Note or Document\" to start studying here.",
  };
  const activeMaterial =
    materials.find((m) => m.id === activeMaterialId) || materials[0] || (isBackendConnected ? emptyMaterial : demoMaterials[0]);
  // Chat RAG chỉ khả dụng cho document thật (không phải demo) đã ingest xong (status=ready).
  const isChatAvailable = isBackendConnected && !activeMaterial.isDemo && activeMaterial.status === "ready";

  useEffect(() => {
    // Đổi tài liệu đang xem thì reset về tab Content và load lại lịch sử chat của tài liệu đó.
    setViewMode("content");
    setChatMessages([]);
    setChatError(null);
    if (!isBackendConnected || activeMaterial.isDemo || activeMaterial.status !== "ready") return;
    setIsChatLoading(true);
    getChatHistory(activeMaterial.id)
      .then(setChatMessages)
      .catch(() => setChatError("Could not load chat history."))
      .finally(() => setIsChatLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeMaterialId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, viewMode]);

  // Gửi 1 câu hỏi chat, chèn cả câu hỏi lẫn câu trả lời AI vào danh sách khi thành công.
  const handleSendChat = async () => {
    const message = chatInput.trim();
    if (!message || isChatSending) return;
    setChatInput("");
    setChatError(null);
    setIsChatSending(true);
    try {
      const result = await sendChatMessage(activeMaterial.id, message, chatProvider);
      setChatMessages((current) => [...current, result.user_message, result.assistant_message]);
    } catch (error) {
      const raw = error instanceof Error ? error.message : "Failed to send message";
      setChatError(raw);
    } finally {
      setIsChatSending(false);
    }
  };

  const handleSaveMaterial = async () => {
    // Backend hiện chỉ nhận audio/.docx; text note thuần sẽ được hỗ trợ ở phase sau.
    if (!selectedFile) {
      setUploadError("Choose an audio or .docx file first.");
      return;
    }
    if (isUploading) return;
    setIsUploading(true);
    try {
      setUploadError(null);
      const uploaded = await uploadDocument(
        selectedFile,
        selectedFolder === "all" ? undefined : selectedFolder,
        newNoteTitle ? [newNoteTitle] : [],
      );
      // Chèn document mới vào đầu danh sách để người dùng thấy kết quả ngay.
      setMaterials((current) => [
        {
          id: uploaded.id,
          title: uploaded.title,
          folder: uploaded.folder_id || "all",
          type: uploaded.source_type.toUpperCase(),
          date: new Date(uploaded.created_at).toLocaleDateString(),
          size: `${uploaded.file_size_kb || 0} KB`,
          tags: uploaded.tags || [],
          starred: uploaded.starred,
          isDemo: false,
          status: uploaded.status,
          content:
            uploaded.status === "ready"
              ? "Content ingested — ask questions about this document in the Chat tab."
              : uploaded.status === "failed"
              ? "Ingestion failed for this file. Chat is unavailable until you upload a readable .docx."
              : "Document status: processing. Content will appear after ingestion.",
        },
        ...current,
      ]);
      // Nhãn "All Materials (n)" lấy từ state folders nên phải tăng tay, không thì phải tải lại trang mới đúng.
      setFolders((current) => current.map((f) => (f.id === "all" ? { ...f, count: f.count + 1 } : f)));
      setIsUploadOpen(false);
      setSelectedFile(null);
      setNewNoteTitle("");
      setNewNoteContent("");
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  // Tạo folder mới qua prompt() đơn giản, chỉ hoạt động khi đã đăng nhập.
  const handleCreateFolder = async () => {
    if (!isBackendConnected) return;
    const name = window.prompt("Folder name");
    if (!name?.trim()) return;
    try {
      const folder = await createFolder(name.trim());
      setFolders((current) => [...current, { id: folder.id, name: folder.name, count: 0 }]);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Folder creation failed");
    }
  };

  // Bật/tắt đánh dấu sao cho tài liệu đang xem (bỏ qua nếu đang xem material demo id="1").
  const handleToggleStar = async () => {
    if (!isBackendConnected || !activeMaterial || activeMaterial.id === "1") return;
    const updated = await updateDocument(activeMaterial.id, { starred: !activeMaterial.starred });
    setMaterials((current) => current.map((item) => item.id === updated.id ? { ...item, starred: updated.starred } : item));
  };

  // Xóa vĩnh viễn tài liệu đang xem rồi quay lại material demo đầu tiên.
  const handleDeleteActive = async () => {
    if (!isBackendConnected || !activeMaterial || activeMaterial.id === "1") return;
    await deleteDocument(activeMaterial.id);
    setMaterials((current) => current.filter((item) => item.id !== activeMaterial.id));
    setFolders((current) => current.map((f) => (f.id === "all" ? { ...f, count: Math.max(0, f.count - 1) } : f)));
    setActiveMaterialId("1");
  };

  return (
    <div className="stagger-in p-6 md:p-10 max-w-7xl mx-auto space-y-8">
      {/* Title & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <p className="text-sm italic text-slate-500 mb-1">Everything you study, in one place</p>
          <h1 className="font-display text-4xl font-bold text-slate-900 flex items-center gap-3">
            <FolderKanban className="w-8 h-8 text-purple-500 -rotate-6" /> Knowledge Space & Notebook
          </h1>
          <p className="text-sm text-slate-500 mt-2 max-w-xl">
            Organize study materials, saved movie clips, vocabulary notebooks, and AI summaries.
          </p>
          <p className={`text-xs mt-3 font-semibold flex items-center gap-1.5 ${isBackendConnected ? "text-emerald-600" : "text-slate-400"}`}>
            <span className={`w-2 h-2 rounded-full ${isBackendConnected ? "bg-emerald-500" : "bg-slate-300"}`} />
            {isBackendConnected ? "Connected to FastAPI backend" : "Demo materials - connect an account to sync"}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsUploadOpen(true)}
            className="px-5 py-3 bg-indigo-700 hover:bg-indigo-800 text-white font-semibold text-sm rounded-2xl shadow-[0_16px_26px_-14px_rgba(31,87,73,0.9)] flex items-center justify-center gap-2 transition-all cursor-pointer hover:-translate-y-0.5 active:scale-95"
          >
            <Plus className="w-4 h-4" /> Add Note or Document
          </button>
          <button
            onClick={handleCreateFolder}
            disabled={!isBackendConnected}
            title="Create folder in backend Notebook"
            className="px-4 py-3 bg-paper-deep hover:bg-slate-200/70 text-slate-700 font-semibold text-sm rounded-2xl flex items-center justify-center gap-2 disabled:opacity-40 transition-colors active:scale-95"
          >
            <FolderKanban className="w-4 h-4" /> New Folder
          </button>
        </div>
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
              className="w-full pl-9 pr-4 py-2.5 text-sm bg-[#fffdf8] ring-1 ring-slate-900/10 rounded-full focus:outline-none focus:ring-2 focus:ring-indigo-500/60 text-slate-800"
            />
          </div>

          {/* Folder Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
            {folders.map((f) => (
              <button
                key={f.id}
                onClick={() => setSelectedFolder(f.id)}
                className={`px-3.5 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                  selectedFolder === f.id
                    ? "bg-indigo-700 text-white"
                    : "bg-paper-deep text-slate-600 hover:bg-indigo-100 hover:text-indigo-700"
                }`}
              >
                {f.name} ({f.id === "all" ? f.count : materials.filter((m) => m.folder === f.id).length})
              </button>
            ))}
          </div>

          {/* Materials List */}
          <div className="space-y-3">
            {filteredMaterials.map((item, index) => {
              const isActive = item.id === activeMaterialId;
              return (
                <div
                  key={item.id}
                  onClick={() => setActiveMaterialId(item.id)}
                  style={{ animationDelay: `${Math.min(index, 8) * 0.04}s` }}
                  className={`pop-in p-5 rounded-2xl transition-all cursor-pointer ${
                    isActive
                      ? "bg-indigo-700 text-white shadow-[0_18px_28px_-16px_rgba(31,87,73,0.9)]"
                      : "surface surface-lift"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <FileText className={`w-4 h-4 ${isActive ? "text-indigo-200" : "text-slate-400"}`} />
                      <span className={`tag ${isActive ? "bg-white/20 text-white" : "bg-paper-deep text-slate-500"}`}>
                        {item.type}
                      </span>
                    </div>
                    {item.starred && <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />}
                  </div>

                  <h4 className={`font-display font-bold text-base mb-3 line-clamp-2 leading-snug ${isActive ? "text-white" : "text-slate-900"}`}>
                    {item.title}
                  </h4>

                  <div className={`flex items-center justify-between text-[11px] ${isActive ? "text-indigo-200" : "text-slate-400"}`}>
                    <span>{item.date}</span>
                    <div className="flex items-center gap-1">
                      {item.tags.map((t, idx) => (
                        <span key={idx} className={`px-1.5 py-0.5 rounded font-medium ${isActive ? "bg-white/15 text-white" : "bg-paper-deep text-slate-600"}`}>
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
        <div className="surface lg:col-span-7 p-7 md:p-8 flex flex-col justify-between min-h-[500px] lg:sticky lg:top-24 lg:self-start">
          <div key={activeMaterial.id} className="pop-in">
            {/* Viewer Header */}
            <div className="flex items-start justify-between pb-5 mb-5 border-b border-dashed border-slate-200">
              <div>
                <div className="flex items-center gap-2 text-xs text-indigo-700 font-bold mb-1.5">
                  <Tag className="w-3.5 h-3.5" /> {activeMaterial.type}
                </div>
                <h2 className="font-display text-2xl font-bold text-slate-900 leading-snug">
                  {activeMaterial.title}
                </h2>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleToggleStar}
                  title="Toggle backend star"
                  aria-label="Toggle star"
                  className="p-2.5 rounded-full bg-paper-deep text-amber-500 hover:bg-amber-100 transition-colors active:scale-95"
                >
                  <Star className={`w-4 h-4 ${activeMaterial.starred ? "fill-amber-400" : ""}`} />
                </button>
                <div className="flex items-center bg-paper-deep rounded-full p-1">
                  <button
                    onClick={() => setViewMode("content")}
                    className={`px-3.5 py-1.5 text-xs font-bold rounded-full transition-colors cursor-pointer ${
                      viewMode === "content" ? "bg-indigo-700 text-white" : "text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    Content
                  </button>
                  <button
                    onClick={() => setViewMode("chat")}
                    title={isChatAvailable ? undefined : "Connect and wait for ingestion (status: ready) to chat"}
                    className={`px-3.5 py-1.5 text-xs font-bold rounded-full transition-colors flex items-center gap-1 cursor-pointer ${
                      viewMode === "chat" ? "bg-indigo-700 text-white" : "text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    <MessageSquare className="w-3.5 h-3.5" /> Chat
                  </button>
                </div>
              </div>
            </div>

            {viewMode === "content" ? (
              /* Document Content Body */
              <div className="max-w-none text-slate-700 text-[17px] leading-[1.85] font-serif bg-paper-deep/50 p-6 rounded-2xl whitespace-pre-line">
                {activeMaterial.content}
              </div>
            ) : (
              /* NotebookLM-style RAG chat: hỏi đáp trực tiếp trên nội dung tài liệu thật */
              <div className="flex flex-col h-[420px]">
                {!isChatAvailable ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-400 gap-2 px-6">
                    <MessageSquare className="w-8 h-8" />
                    <p className="text-xs font-medium">
                      {activeMaterial.isDemo
                        ? "Chat is only available for documents connected to your real account."
                        : activeMaterial.status === "empty"
                        ? "Upload a document first, then you can chat with it here."
                        : activeMaterial.status === "failed"
                        ? "This file failed to ingest, so there's no content to chat about."
                        : "This document is still processing. Chat unlocks once ingestion is done (status: ready)."}
                    </p>
                  </div>
                ) : (
                  <>
                    <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                      {isChatLoading && (
                        <p className="text-xs text-slate-400 text-center py-6">Loading conversation...</p>
                      )}
                      {!isChatLoading && chatMessages.length === 0 && (
                        <div className="flex flex-col items-center justify-center text-center text-slate-400 gap-2 py-10">
                          <Sparkles className="w-6 h-6" />
                          <p className="text-xs font-medium max-w-xs">
                            Ask anything about this document.
                          </p>
                        </div>
                      )}
                      {chatMessages.map((message) => (
                        <div
                          key={message.id}
                          className={`pop-in flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                        >
                          <div
                            className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                              message.role === "user"
                                ? "bg-indigo-700 text-white rounded-br-md"
                                : "bg-paper-deep text-slate-800 rounded-bl-md"
                            }`}
                          >
                            <p className="whitespace-pre-line">{message.content}</p>
                            {message.sources && message.sources.length > 0 && (
                              <div className="mt-2 pt-2 border-t border-slate-200/60 space-y-1">
                                {message.sources.map((source) => (
                                  <div key={source.chunk_id} className="flex items-start gap-1 text-[10px] text-slate-500">
                                    <Quote className="w-2.5 h-2.5 mt-0.5 shrink-0" />
                                    <span className="line-clamp-2">{source.excerpt}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                      {isChatSending && (
                        <div className="flex justify-start">
                          <div className="bg-paper-deep text-slate-500 rounded-2xl rounded-bl-md px-4 py-3 text-sm flex items-center gap-1.5">
                            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Thinking...
                          </div>
                        </div>
                      )}
                      <div ref={chatEndRef} />
                    </div>
                    {chatError && <p className="text-[11px] text-red-600 mt-2">{chatError}</p>}
                    <div className="mt-3 pt-3 border-t border-dashed border-slate-200 flex items-center gap-2">
                      <select
                        value={chatProvider}
                        onChange={(event) => handleProviderChange(event.target.value as ChatProvider)}
                        disabled={isChatSending}
                        aria-label="Chat model"
                        className="px-2 py-2.5 text-xs bg-white ring-1 ring-slate-900/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
                      >
                        <option value="gemini">Gemini</option>
                        <option value="ollama">Ollama (local)</option>
                      </select>
                      <input
                        type="text"
                        value={chatInput}
                        onChange={(event) => setChatInput(event.target.value)}
                        onKeyDown={(event) => event.key === "Enter" && handleSendChat()}
                        placeholder="Ask a question about this document..."
                        disabled={isChatSending}
                        className="flex-1 px-4 py-2.5 text-sm bg-white ring-1 ring-slate-900/10 rounded-full focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
                      />
                      <button
                        onClick={handleSendChat}
                        disabled={isChatSending || !chatInput.trim()}
                        aria-label="Send message"
                        className="p-3 bg-indigo-700 hover:bg-indigo-800 text-white rounded-full disabled:opacity-40 transition-all active:scale-90"
                      >
                        <Send className="w-4 h-4" />
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Footer Actions */}
          <div className="mt-6 pt-4 border-t border-dashed border-slate-200 flex items-center justify-between text-xs text-slate-500">
            <span>Size: {activeMaterial.size} • Added on {activeMaterial.date}</span>
            <div className="flex items-center gap-3">
              <button className="flex items-center gap-1 hover:text-slate-900 transition-colors cursor-pointer">
                <Download className="w-3.5 h-3.5" /> Export
              </button>
              <button className="flex items-center gap-1 hover:text-slate-900 transition-colors cursor-pointer">
                <Share2 className="w-3.5 h-3.5" /> Share
              </button>
              <button
                onClick={handleDeleteActive}
                disabled={!isBackendConnected || activeMaterial.id === "1"}
                className="flex items-center gap-1 text-rose-600 hover:text-rose-800 disabled:opacity-30"
              >
                <Trash2 className="w-3.5 h-3.5" /> Delete
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Upload/New Note Modal */}
      {isUploadOpen && (
        <div className="fixed inset-0 bg-slate-950/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#fffdf8] rounded-3xl max-w-lg w-full p-7 shadow-[0_40px_80px_-30px_rgba(32,29,24,0.6)] animate-rise space-y-4">
            <div className="flex items-center justify-between pb-1">
              <h3 className="font-display font-bold text-2xl text-slate-900 flex items-center gap-2">
                <UploadCloud className="w-5 h-5 text-indigo-600" /> Create New Material or Note
              </h3>
              <button onClick={() => setIsUploadOpen(false)} disabled={isUploading} aria-label="Close" className="text-slate-400 hover:text-slate-600 disabled:opacity-40">
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
                className="w-full px-3 py-2 text-xs bg-white ring-1 ring-slate-900/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Audio or DOCX file</label>
              <input
                type="file"
                accept=".docx,audio/*"
                onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
                className="w-full text-xs text-slate-600"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Content or Pasted Text</label>
              <textarea
                rows={5}
                value={newNoteContent}
                onChange={(e) => setNewNoteContent(e.target.value)}
                placeholder="Paste article, transcript, or vocabulary notes here..."
                className="w-full px-3 py-2 text-xs bg-white ring-1 ring-slate-900/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setIsUploadOpen(false)}
                disabled={isUploading}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveMaterial}
                disabled={!isBackendConnected || isUploading}
                className="px-5 py-2.5 text-xs font-bold bg-indigo-700 hover:bg-indigo-800 text-white rounded-xl transition-all active:scale-95 disabled:opacity-40 inline-flex items-center gap-2"
              >
                {isUploading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                {isUploading ? "Processing..." : "Upload to Notebook"}
              </button>
            </div>
            {isUploading && (
              <p className="text-xs text-slate-500" role="status">
                Reading and indexing your file so you can chat with it. This can take up to a minute; please keep this window open.
              </p>
            )}
            {uploadError && <p className="text-xs text-red-600">{uploadError}</p>}
          </div>
        </div>
      )}
    </div>
  );
};
