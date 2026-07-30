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

export interface MovieMatch {
  id: number;
  movieTitle: string;
  timestamp: string;
  image: string;
  speakerA: string;
  speakerB: string;
  speakerA2: string;
  saved: boolean;
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
