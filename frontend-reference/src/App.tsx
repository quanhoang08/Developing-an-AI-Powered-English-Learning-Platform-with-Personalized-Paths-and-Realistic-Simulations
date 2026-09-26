// Root component: layout Sidebar + Header + nội dung theo tab, quản lý trạng thái đăng
// nhập tập trung (isLoggedIn/userEmail) để chia sẻ cho Sidebar/Dashboard/gate tính năng.
import React, { useEffect, useState } from "react";
import { motion } from "motion/react";
import { ActiveTab } from "./types";
import { clearAccessToken, getAccessToken, getCurrentUser } from "./api";
import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { DashboardView } from "./components/DashboardView";
import { NotebookView } from "./components/NotebookView";
import { ReadingView } from "./components/ReadingView";
import { ListeningView } from "./components/ListeningView";
import { SpeakingView } from "./components/SpeakingView";
import { WritingView } from "./components/WritingView";
import { AnalyticsView } from "./components/AnalyticsView";
import { LockedFeature } from "./components/LockedFeature";
import { SpacedRepetitionModal } from "./components/SpacedRepetitionModal";

const FEATURE_NAMES: Record<Exclude<ActiveTab, "dashboard">, string> = {
  notebook: "Knowledge Space",
  reading: "Reading & Vocab",
  listening: "Listening & Movies",
  speaking: "Speaking Studio",
  writing: "Writing Lab",
  analytics: "Adaptive Progress",
};

export function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("dashboard");
  const [searchQuery, setSearchQuery] = useState("");
  const [isFlashcardModalOpen, setIsFlashcardModalOpen] = useState(false);
  const [authVersion, setAuthVersion] = useState(0);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  // Đọc trực tiếp mỗi render; authVersion đổi sau login/logout ép App re-render nên giá trị
  // này luôn đồng bộ (cùng cơ chế NotebookView đang dùng).
  const isLoggedIn = Boolean(getAccessToken());

  useEffect(() => {
    // Nguồn duy nhất cho email hiện tại — Sidebar và Dashboard đều đọc từ đây, tránh mỗi
    // component tự fetch riêng rồi lệch nhau khi login/logout xảy ra ở chỗ khác.
    if (!isLoggedIn) {
      setUserEmail(null);
      return;
    }
    getCurrentUser()
      .then((user) => setUserEmail(user.email))
      .catch(() => setUserEmail(null));
  }, [authVersion, isLoggedIn]);

  // Component con (vd nút "Back to Dashboard" ở ErrorNotice) đổi tab qua sự kiện, không cần prop drilling.
  useEffect(() => {
    const onNavigate = (event: Event) => setActiveTab((event as CustomEvent<ActiveTab>).detail);
    window.addEventListener("lumina-navigate", onNavigate);
    return () => window.removeEventListener("lumina-navigate", onNavigate);
  }, []);

  // Đăng xuất: xóa token, reset state, rồi phát sự kiện để AuthPanel (header) tự đồng bộ lại.
  const handleLogout = () => {
    clearAccessToken();
    setUserEmail(null);
    setAuthVersion((version) => version + 1);
    window.dispatchEvent(new Event("lumina-auth-changed"));
  };

  // Chọn view hiển thị theo activeTab; khóa mọi tab ngoài Dashboard khi chưa đăng nhập.
  const renderActiveView = () => {
    if (activeTab === "dashboard") {
      return (
        <DashboardView
          setActiveTab={setActiveTab}
          openFlashcards={() => setIsFlashcardModalOpen(true)}
          userEmail={userEmail}
        />
      );
    }

    // Mọi tính năng ngoài Dashboard bắt buộc phải đăng nhập với backend thật trước.
    if (!isLoggedIn) {
      return <LockedFeature featureName={FEATURE_NAMES[activeTab]} />;
    }

    switch (activeTab) {
      case "notebook":
        return <NotebookView authVersion={authVersion} />;
      case "reading":
        return <ReadingView />;
      case "listening":
        return <ListeningView />;
      case "speaking":
        return <SpeakingView />;
      case "writing":
        return <WritingView />;
      case "analytics":
        return <AnalyticsView />;
      default:
        return (
          <DashboardView
            setActiveTab={setActiveTab}
            openFlashcards={() => setIsFlashcardModalOpen(true)}
            userEmail={userEmail}
          />
        );
    }
  };

  return (
    <div className="flex min-h-screen text-slate-900 font-sans antialiased">
      {/* Persistent Left Navigation Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        openFlashcards={() => setIsFlashcardModalOpen(true)}
        isLoggedIn={isLoggedIn}
        userEmail={userEmail}
        onLogout={handleLogout}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Header
          activeTab={activeTab}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          openFlashcards={() => setIsFlashcardModalOpen(true)}
          onAuthChanged={() => setAuthVersion((version) => version + 1)}
        />

        <main className="flex-1 pb-12">
          {/* key theo tab: mỗi lần đổi view chạy lại hiệu ứng vào, chỉ dùng opacity/translate. */}
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          >
            {renderActiveView()}
          </motion.div>
        </main>
      </div>

      {/* Spaced Repetition Flashcards Modal */}
      <SpacedRepetitionModal
        isOpen={isFlashcardModalOpen}
        onClose={() => setIsFlashcardModalOpen(false)}
      />
    </div>
  );
}

export default App;
