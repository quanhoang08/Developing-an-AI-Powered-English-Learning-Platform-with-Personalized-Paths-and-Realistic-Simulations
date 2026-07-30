import React, { useState, useEffect, useRef } from "react";
import {
  Mic,
  MicOff,
  Send,
  Sparkles,
  Volume2,
  Globe,
  Award,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Bot,
  User,
  Zap
} from "lucide-react";

interface ChatMessage {
  id: string;
  sender: "ai" | "user";
  text: string;
  originalText?: string;
  wasErrorDetected?: boolean;
}

export const SpeakingView: React.FC = () => {
  const [isListening, setIsListening] = useState(false);
  const [selectedAccent, setSelectedAccent] = useState("US - California");
  const [userTextInput, setUserTextInput] = useState("");
  const [isProcessingAI, setIsProcessingAI] = useState(false);

  // Chat History
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "1",
      sender: "ai",
      text: "Hello Sarah! Today we're practicing talking about weekend plans and job responsibilities. How was your week?"
    },
    {
      id: "2",
      sender: "user",
      text: "I went to the park yesterday and played with my dog.",
      originalText: "I go to the park yesterday and play dog.",
      wasErrorDetected: true
    },
    {
      id: "3",
      sender: "ai",
      text: "That sounds lovely! Parks are great for relaxing. What kind of dog do you have, and do you go there often?"
    }
  ]);

  // Live Feedback Panel Data
  const [pronunciationScore, setPronunciationScore] = useState(85);
  const [pronunciationAdvice, setPronunciationAdvice] = useState(
    "Great clarity on vowels. Watch your 'R' sounds at the end of words like 'park' and 'yesterday'."
  );
  const [cefrTip, setCefrTip] = useState({
    originalPhrase: "I want go...",
    betterPhrase: "I would like to go...",
    explanation: "More Polite & Natural for B2/C1 level"
  });
  const [grammarTip, setGrammarTip] = useState(
    "Remember to use past tense verbs for completed actions in the past ('went' and 'played' instead of 'go' and 'play')."
  );

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Web Speech API / Mic Handling
  const startSpeechRecognition = () => {
    if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
      alert("Speech recognition is supported via fallback text input.");
      setIsListening(true);
      return;
    }

    try {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      recognition.lang = selectedAccent.includes("UK") ? "en-GB" : selectedAccent.includes("AU") ? "en-AU" : "en-US";
      recognition.interimResults = false;

      recognition.onstart = () => setIsListening(true);
      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setIsListening(false);
        handleUserSendMessage(transcript);
      };
      recognition.onerror = () => setIsListening(false);
      recognition.onend = () => setIsListening(false);

      recognition.start();
    } catch (e) {
      console.error(e);
      setIsListening(false);
    }
  };

  const handleUserSendMessage = async (inputMessage?: string) => {
    const messageToSend = inputMessage || userTextInput;
    if (!messageToSend.trim()) return;

    const userMsgId = Date.now().toString();
    const newMessages: ChatMessage[] = [
      ...messages,
      {
        id: userMsgId,
        sender: "user",
        text: messageToSend
      }
    ];

    setMessages(newMessages);
    setUserTextInput("");
    setIsProcessingAI(true);

    try {
      const res = await fetch("/api/ai/speech-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userMessage: messageToSend,
          accent: selectedAccent,
          history: messages.map((m) => ({ sender: m.sender, text: m.text }))
        })
      });
      const data = await res.json();

      // Update User message with corrected text if error detected
      if (data.wasErrorDetected) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === userMsgId
              ? {
                  ...m,
                  text: data.correctedText || m.text,
                  originalText: data.originalText || messageToSend,
                  wasErrorDetected: true
                }
              : m
          )
        );
      }

      // Add AI reply message
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: "ai",
          text: data.aiReply || "That's very interesting! Could you tell me more about that?"
        }
      ]);

      // Update feedback stats
      if (data.pronunciationScore) setPronunciationScore(data.pronunciationScore);
      if (data.pronunciationAdvice) setPronunciationAdvice(data.pronunciationAdvice);
      if (data.cefrTip) setCefrTip(data.cefrTip);
      if (data.grammarTip) setGrammarTip(data.grammarTip);

      // Play AI Voice TTS
      playTTS(data.aiReply || "That's very interesting!");
    } catch (err) {
      console.error(err);
    } finally {
      setIsProcessingAI(false);
    }
  };

  const playTTS = (text: string) => {
    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = selectedAccent.includes("UK") ? "en-GB" : selectedAccent.includes("AU") ? "en-AU" : "en-US";
      window.speechSynthesis.speak(utterance);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Mic className="w-6 h-6 text-indigo-600" /> AI Speaking Studio
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time conversational practice with instant accent, grammar, and pronunciation feedback.
          </p>
        </div>

        {/* Accent Selector */}
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-indigo-600" />
          <span className="text-xs font-bold text-slate-700">Tutor Accent:</span>
          <select
            value={selectedAccent}
            onChange={(e) => setSelectedAccent(e.target.value)}
            className="px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 font-semibold text-slate-800"
          >
            <option value="US - California">US - California</option>
            <option value="UK - London">UK - London</option>
            <option value="AU - Sydney">AU - Sydney</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Main Speaking Canvas (7 Cols) */}
        <div className="lg:col-span-7 bg-white rounded-3xl border border-slate-200/80 p-6 shadow-xs flex flex-col justify-between min-h-[560px]">
          {/* Avatar & Pulse Ring */}
          <div className="flex flex-col items-center justify-center py-6 border-b border-slate-100">
            <div className="relative">
              <div
                className={`w-24 h-24 rounded-full bg-gradient-to-tr from-indigo-600 via-purple-600 to-indigo-500 flex items-center justify-center text-white shadow-xl shadow-indigo-200 ${
                  isListening ? "animate-pulse ring-8 ring-indigo-200" : ""
                }`}
              >
                <Bot className="w-12 h-12" />
              </div>
              <span className="absolute bottom-0 right-0 w-4 h-4 bg-emerald-500 border-2 border-white rounded-full"></span>
            </div>

            <h3 className="font-bold text-sm text-slate-900 mt-3">Lumina AI Tutor</h3>
            <p className="text-xs text-slate-400">
              {isListening ? "Listening to your voice..." : isProcessingAI ? "Analyzing & formulating reply..." : "Ready to converse"}
            </p>
          </div>

          {/* Conversation Chat Feed */}
          <div className="flex-1 my-4 space-y-4 overflow-y-auto max-h-[320px] px-2">
            {messages.map((m) => {
              const isAI = m.sender === "ai";
              return (
                <div
                  key={m.id}
                  className={`flex items-start gap-3 ${isAI ? "" : "flex-row-reverse"}`}
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                      isAI ? "bg-indigo-600 text-white" : "bg-purple-600 text-white"
                    }`}
                  >
                    {isAI ? <Bot className="w-4 h-4" /> : <User className="w-4 h-4" />}
                  </div>

                  <div className={`max-w-[80%] space-y-1 ${isAI ? "text-left" : "text-right"}`}>
                    <div
                      className={`p-3.5 rounded-2xl text-xs leading-relaxed inline-block ${
                        isAI
                          ? "bg-slate-100 text-slate-900 rounded-tl-xs"
                          : "bg-indigo-600 text-white rounded-tr-xs"
                      }`}
                    >
                      <p>{m.text}</p>
                    </div>

                    {/* Show original vs corrected user speech */}
                    {!isAI && m.wasErrorDetected && (
                      <div className="p-2 rounded-xl bg-amber-50 border border-amber-200 text-[11px] text-amber-900 text-left space-y-0.5">
                        <p className="font-semibold text-amber-800">
                          Original spoken: <span className="line-through">{m.originalText}</span>
                        </p>
                        <p className="font-bold text-emerald-700">
                          Natural correction: {m.text}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>

          {/* Controls Bar */}
          <div className="pt-4 border-t border-slate-100 space-y-3">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={userTextInput}
                onChange={(e) => setUserTextInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleUserSendMessage()}
                placeholder="Type your response or hold mic to speak..."
                className="flex-1 px-4 py-2.5 text-xs bg-slate-50 border border-slate-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 text-slate-800"
              />

              <button
                onClick={startSpeechRecognition}
                className={`p-3 rounded-2xl font-bold shadow-md transition-all cursor-pointer ${
                  isListening
                    ? "bg-rose-600 text-white animate-pulse"
                    : "bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-200"
                }`}
                title="Click to Record Voice"
              >
                {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
              </button>

              <button
                onClick={() => handleUserSendMessage()}
                className="p-3 bg-slate-900 hover:bg-slate-800 text-white rounded-2xl font-bold transition-all cursor-pointer"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Right Sidebar: Real-time AI Feedback (5 Cols) */}
        <div className="lg:col-span-5 bg-white rounded-3xl border border-slate-200/80 p-6 shadow-xs space-y-6">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 className="font-bold text-sm text-slate-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-600" /> Live Speaking Feedback
            </h3>
            <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
              B2 Target
            </span>
          </div>

          {/* Pronunciation Gauge */}
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-700">Pronunciation Accuracy</span>
              <span className="font-extrabold text-indigo-600">{pronunciationScore}%</span>
            </div>
            <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
              <div
                className="bg-indigo-600 h-full rounded-full transition-all duration-500"
                style={{ width: `${pronunciationScore}%` }}
              ></div>
            </div>
            <p className="text-[11px] text-slate-500 leading-snug pt-1">
              {pronunciationAdvice}
            </p>
          </div>

          {/* CEFR Recommendation */}
          <div className="p-4 rounded-2xl bg-indigo-50/70 border border-indigo-100 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-indigo-900 flex items-center gap-1">
                <Award className="w-4 h-4 text-indigo-600" /> Natural CEFR Upgrade
              </span>
              <button
                onClick={() => playTTS(cefrTip.betterPhrase)}
                className="text-xs text-indigo-600 hover:underline flex items-center gap-1 cursor-pointer font-bold"
              >
                <Volume2 className="w-3.5 h-3.5" /> Listen
              </button>
            </div>

            <div className="text-xs space-y-1">
              <p className="text-slate-500">Instead of: <span className="line-through">{cefrTip.originalPhrase}</span></p>
              <p className="font-bold text-indigo-950">Say: "{cefrTip.betterPhrase}"</p>
              <p className="text-[11px] text-indigo-700 font-medium">{cefrTip.explanation}</p>
            </div>
          </div>

          {/* Grammar Tip */}
          <div className="p-4 rounded-2xl bg-amber-50/70 border border-amber-200/80 space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-bold text-amber-900">
              <Zap className="w-4 h-4 text-amber-600 fill-amber-500" />
              <span>Active Grammar Tip</span>
            </div>
            <p className="text-xs text-slate-700 leading-relaxed">
              {grammarTip}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
