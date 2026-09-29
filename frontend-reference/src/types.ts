// Shape dữ liệu dùng bởi các view còn ở dạng demo (Reading word lookup, Listening/Movie,
// Writing insights, Analytics error journal, flashcards) — không phải response API thật.

// Tab đang active ở Sidebar/Header, điều khiển view nào App.tsx render.
export type ActiveTab =
  | "dashboard"
  | "notebook"
  | "reading"
  | "listening"
  | "speaking"
  | "writing"
  | "analytics";

export interface VocabWord {
  id: string;
  word: string;
  phonetics: string;
  partOfSpeech: string;
  meaning: string;
  contextQuote: string;
  synonyms: string[];
  antonyms: string[];
  challengeSentence: string;
  challengeOptions: string[];
  challengeCorrectIndex: number;
}

export interface WritingInsight {
  type: "grammar" | "vocabulary" | "style";
  title: string;
  originalText?: string;
  suggestedText?: string;
  description: string;
  rule?: string;
  synonyms?: string[];
  suggestion?: string;
}

export interface ErrorJournalItem {
  id: string;
  category: "Grammar" | "Vocabulary" | "Pronunciation";
  timeAgo: string;
  originalText: string;
  correctedText: string;
  spacedRepetitionLevel: number;
  explanation: string;
}

export interface FlashcardItem {
  id: string;
  front: string;
  back: string;
  type: "Grammar" | "Vocabulary" | "Phrasal Verb";
  context: string;
}
