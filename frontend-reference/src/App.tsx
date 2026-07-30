import React, { useState } from "react";
import { ActiveTab } from "./types";
import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { DashboardView } from "./components/DashboardView";
import { NotebookView } from "./components/NotebookView";
import { ReadingView } from "./components/ReadingView";
import { ListeningView } from "./components/ListeningView";
import { SpeakingView } from "./components/SpeakingView";
import { WritingView } from "./components/WritingView";
import { AnalyticsView } from "./components/AnalyticsView";
import { SpacedRepetitionModal } from "./components/SpacedRepetitionModal";

export function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("dashboard");
  const [searchQuery, setSearchQuery] = useState("");
  const [isFlashcardModalOpen, setIsFlashcardModalOpen] = useState(false);

  const renderActiveView = () => {
    switch (activeTab) {
      case "dashboard":
        return (
          <DashboardView
            setActiveTab={setActiveTab}
            openFlashcards={() => setIsFlashcardModalOpen(true)}
          />
        );
      case "notebook":
        return <NotebookView />;
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
          />
        );
    }
  };

  return (
    <div className="flex min-h-screen bg-[#f8f9ff] text-slate-900 font-sans antialiased">
      {/* Persistent Left Navigation Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        openFlashcards={() => setIsFlashcardModalOpen(true)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Header
          activeTab={activeTab}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          openFlashcards={() => setIsFlashcardModalOpen(true)}
        />

        <main className="flex-1 pb-12">
          {renderActiveView()}
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
