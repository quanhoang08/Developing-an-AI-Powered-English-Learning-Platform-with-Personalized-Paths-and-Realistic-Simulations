import express from "express";
import path from "path";
import { createServer as createViteServer } from "vite";
import { GoogleGenAI, Type } from "@google/genai";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = 3000;

app.use(express.json());

// Initialize Gemini Client
const getGeminiAI = () => {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return null;
  }
  return new GoogleGenAI({
    apiKey,
    httpOptions: {
      headers: {
        "User-Agent": "aistudio-build",
      },
    },
  });
};

// Health check endpoint
app.get("/api/health", (req, res) => {
  res.json({ status: "ok" });
});

// Word Lookup API
app.post("/api/ai/word-lookup", async (req, res) => {
  try {
    const { word, contextSentence } = req.body;
    if (!word) {
      return res.status(400).json({ error: "Word is required" });
    }

    const ai = getGeminiAI();
    if (!ai) {
      // Return realistic fallback response if no API key
      return res.json({
        word: word,
        phonetics: `/${word.toLowerCase()}/`,
        partOfSpeech: "adjective",
        meaning: `Spreading or existing widely throughout an area or group of people.`,
        contextQuote: contextSentence || `The influence of technology is ${word} in modern society.`,
        synonyms: ["widespread", "ubiquitous", "omnipresent"],
        antonyms: ["rare", "uncommon", "isolated"],
        challengeSentence: `The smell of fresh coffee was _____ throughout the small cafe, drawing people in.`,
        challengeOptions: [word, "atrophy", "mitigate"],
        challengeCorrectIndex: 0
      });
    }

    const prompt = `Analyze the English word "${word}" in the context of: "${contextSentence || ''}".
    Provide a JSON response with:
    - word: string
    - phonetics: string (e.g. /pərˈvāsiv/)
    - partOfSpeech: string (e.g. adjective, verb, noun)
    - meaning: string (clear definition suitable for B2/C1 English learners)
    - contextQuote: string (how it was used in context or an example)
    - synonyms: string[] (3 synonyms)
    - antonyms: string[] (1-2 antonyms)
    - challengeSentence: string (a new practice fill-in-the-blank sentence where "${word}" is blanked out as _____)
    - challengeOptions: string[] (3 choices including "${word}")
    - challengeCorrectIndex: number (index of "${word}" in options)`;

    const response = await ai.models.generateContent({
      model: "gemini-3.6-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            word: { type: Type.STRING },
            phonetics: { type: Type.STRING },
            partOfSpeech: { type: Type.STRING },
            meaning: { type: Type.STRING },
            contextQuote: { type: Type.STRING },
            synonyms: { type: Type.ARRAY, items: { type: Type.STRING } },
            antonyms: { type: Type.ARRAY, items: { type: Type.STRING } },
            challengeSentence: { type: Type.STRING },
            challengeOptions: { type: Type.ARRAY, items: { type: Type.STRING } },
            challengeCorrectIndex: { type: Type.INTEGER }
          },
          required: ["word", "phonetics", "partOfSpeech", "meaning", "synonyms", "antonyms", "challengeSentence", "challengeOptions", "challengeCorrectIndex"]
        }
      }
    });

    const data = JSON.parse(response.text || "{}");
    res.json(data);
  } catch (error: any) {
    console.error("Word Lookup Error:", error);
    res.status(500).json({ error: error.message || "Failed to analyze word" });
  }
});

// Generate Reading Story API
app.post("/api/ai/generate-story", async (req, res) => {
  try {
    const { topic = "Technology & Society", level = "B2" } = req.body;
    const ai = getGeminiAI();

    if (!ai) {
      return res.json({
        title: `The ubiquitous nature of artificial intelligence in daily life`,
        category: topic,
        readTime: "8 min read",
        wordCount: "1,200 words",
        content: `In recent years, the integration of artificial intelligence into our daily routines has become increasingly pervasive. It is no longer confined to the realms of science fiction or specialized research laboratories; rather, it has seamlessly woven itself into the fabric of our existence. From the moment we wake up to the time we go to sleep, AI algorithms are quietly working in the background, shaping our experiences and making decisions on our behalf.

Consider the simple act of navigating through city traffic. Applications utilizing real-time data and predictive modeling mitigate congestion by suggesting optimal routes. These systems are highly sophisticated, constantly learning from vast amounts of user inputs to refine their accuracy.

However, this growing reliance on technology is not without its detractors. Critics argue that an over-dependence on automated systems could atrophy human cognitive abilities over time. If we outsource our analytical thinking to machines, we risk losing the critical problem-solving skills that have historically driven human progress.

Furthermore, the ethical implications surrounding data privacy remain deeply contentious. As these algorithms require vast troves of personal information to function optimally, establishing robust regulatory frameworks is imperative to protect individual rights.`,
        vocabWords: ["ubiquitous", "pervasive", "mitigate", "sophisticated", "atrophy", "contentious"],
        comprehensionQuestion: "What does the author suggest is a potential negative consequence of relying too heavily on AI?",
        comprehensionOptions: ["Decreased efficiency", "Loss of problem-solving skills", "Increased congestion"],
        correctOptionIndex: 1
      });
    }

    const prompt = `Generate a high quality reading passage for English learners at ${level} level on the topic "${topic}".
    Provide a JSON response with:
    - title: string
    - category: string
    - readTime: string (e.g., "5 min read")
    - wordCount: string (e.g., "850 words")
    - content: string (3-4 paragraphs with 4-6 key vocabulary words included)
    - vocabWords: string[] (array of 4-6 target vocabulary words featured in the text)
    - comprehensionQuestion: string
    - comprehensionOptions: string[] (3 options)
    - correctOptionIndex: number`;

    const response = await ai.models.generateContent({
      model: "gemini-3.6-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            title: { type: Type.STRING },
            category: { type: Type.STRING },
            readTime: { type: Type.STRING },
            wordCount: { type: Type.STRING },
            content: { type: Type.STRING },
            vocabWords: { type: Type.ARRAY, items: { type: Type.STRING } },
            comprehensionQuestion: { type: Type.STRING },
            comprehensionOptions: { type: Type.ARRAY, items: { type: Type.STRING } },
            correctOptionIndex: { type: Type.INTEGER }
          },
          required: ["title", "category", "readTime", "wordCount", "content", "vocabWords", "comprehensionQuestion", "comprehensionOptions", "correctOptionIndex"]
        }
      }
    });

    res.json(JSON.parse(response.text || "{}"));
  } catch (error: any) {
    console.error("Generate Story Error:", error);
    res.status(500).json({ error: error.message || "Failed to generate story" });
  }
});

// Movie Context Finder API
app.post("/api/ai/movie-context", async (req, res) => {
  try {
    const { phrase = "piece of cake" } = req.body;
    const ai = getGeminiAI();

    if (!ai) {
      return res.json({
        phrase,
        matches: [
          {
            id: 1,
            movieTitle: "The Startup Hustle",
            timestamp: "01:14:22",
            image: "https://lh3.googleusercontent.com/aida-public/AB6AXuBHgB9XkSgz6uqLwZJjWS2V_t2yhP5DUs-7PX-TFcDDSiyEb2HugfEYFp2yAXRm87cfEBbysEVTNTq_1VOfLrsFPMQldrAIyvX0mgnoHW8Zkdv1Hx_nZnPuZHYH5KJjAhX4lkICLt98xWaszaUsI7924JmXRstIFlqTtaIwchohQjPZHjWMSqBQ9UaKyVZp5qqr0gUG5vYNbDeWrqk2sE8opkJ8Bbl1e7pX_P_hCKfoqSOA8dhTEtmYU6UtcVD_5-ijhpURAjZX35k",
            speakerA: "I'm not sure I'm ready for tomorrow.",
            speakerB: "...don't worry about the presentation tomorrow. For you, pitching to investors is a piece of cake. Just remember to breathe.",
            speakerA2: "Easy for you to say.",
            saved: false
          },
          {
            id: 2,
            movieTitle: "Family Ties",
            timestamp: "00:45:10",
            image: "https://lh3.googleusercontent.com/aida-public/AB6AXuA6GuRhqN4HQ01O5jNC0f1s0FhjkibRDZd3y0y1CNMdKhyT_5Y_BhlIQQ03aJje4bjl2lbxoh_LTGNjVfLJWefn9U08uvgAncl60TcGp8OZOhhVCQcJWyZMTfKqeipdkmp87lULBRmrK51GjOtALLy9--QdoTxuWXMX53OZPCytlxdaDZSWYN3gJe0vDjicNVAYdUadHj9I0Uyik5uGklALQ6TpwC0LhGg2GLH1WHmful7Ym7uY-JshKCbWoLCX1BEktPaH3BaQ7-8",
            speakerA: "How hard can managing a household really be?",
            speakerB: "You think raising three kids while working full time is a piece of cake? Try doing it for twenty years.",
            speakerA2: "I didn't mean it like that.",
            saved: false
          },
          {
            id: 3,
            movieTitle: "Baking with Buster",
            timestamp: "00:12:05",
            image: "https://lh3.googleusercontent.com/aida-public/AB6AXuA5yPSEutmvNVO1gQTSzY8_rr7kUSc1QxEcbdxHf_sNjK_bRXWGArMJAeLRO0jxHMErIqjW6OevCgoLaZgL5vnuRi5WteOapSDyrIwJ25KMjeqFnLEqcteyAl9H2AB9cJwe23QbNPKBOVpj84tYQfwagaDf6_N8GH4kMxqohjUWox6VGg9QlsHp53DP1xzVdeXrcA918FnU9rSapnyryINe-obEZ24AFBZwMqgWJAVd9pRcgTh4laUGxN6NzTHmS6XGSPuLhubbn0s",
            speakerA: "Buster, is baking chocolate cookies difficult?",
            speakerB: "Now, mix the flour and sugar together. See? Making these cookies is a piece of cake!",
            speakerA2: "Yum! That looks so easy!",
            saved: true
          }
        ]
      });
    }

    const prompt = `Search for native English movie scene contexts featuring the idiom or phrase "${phrase}".
    Provide a JSON response with 3 realistic movie scene examples:
    - phrase: string
    - matches: array of 3 items with:
      - id: number
      - movieTitle: string
      - timestamp: string (e.g. 01:14:22)
      - image: string (cinematic placeholder image URL)
      - speakerA: string (line before)
      - speakerB: string (line containing the exact phrase "${phrase}")
      - speakerA2: string (line after)
      - saved: boolean`;

    const response = await ai.models.generateContent({
      model: "gemini-3.6-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            phrase: { type: Type.STRING },
            matches: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  id: { type: Type.INTEGER },
                  movieTitle: { type: Type.STRING },
                  timestamp: { type: Type.STRING },
                  image: { type: Type.STRING },
                  speakerA: { type: Type.STRING },
                  speakerB: { type: Type.STRING },
                  speakerA2: { type: Type.STRING },
                  saved: { type: Type.BOOLEAN }
                },
                required: ["id", "movieTitle", "timestamp", "speakerA", "speakerB", "speakerA2"]
              }
            }
          },
          required: ["phrase", "matches"]
        }
      }
    });

    const parsed = JSON.parse(response.text || "{}");
    // Ensure image fallback URLs if AI doesn't give valid ones
    const sampleImages = [
      "https://lh3.googleusercontent.com/aida-public/AB6AXuBHgB9XkSgz6uqLwZJjWS2V_t2yhP5DUs-7PX-TFcDDSiyEb2HugfEYFp2yAXRm87cfEBbysEVTNTq_1VOfLrsFPMQldrAIyvX0mgnoHW8Zkdv1Hx_nZnPuZHYH5KJjAhX4lkICLt98xWaszaUsI7924JmXRstIFlqTtaIwchohQjPZHjWMSqBQ9UaKyVZp5qqr0gUG5vYNbDeWrqk2sE8opkJ8Bbl1e7pX_P_hCKfoqSOA8dhTEtmYU6UtcVD_5-ijhpURAjZX35k",
      "https://lh3.googleusercontent.com/aida-public/AB6AXuA6GuRhqN4HQ01O5jNC0f1s0FhjkibRDZd3y0y1CNMdKhyT_5Y_BhlIQQ03aJje4bjl2lbxoh_LTGNjVfLJWefn9U08uvgAncl60TcGp8OZOhhVCQcJWyZMTfKqeipdkmp87lULBRmrK51GjOtALLy9--QdoTxuWXMX53OZPCytlxdaDZSWYN3gJe0vDjicNVAYdUadHj9I0Uyik5uGklALQ6TpwC0LhGg2GLH1WHmful7Ym7uY-JshKCbWoLCX1BEktPaH3BaQ7-8",
      "https://lh3.googleusercontent.com/aida-public/AB6AXuA5yPSEutmvNVO1gQTSzY8_rr7kUSc1QxEcbdxHf_sNjK_bRXWGArMJAeLRO0jxHMErIqjW6OevCgoLaZgL5vnuRi5WteOapSDyrIwJ25KMjeqFnLEqcteyAl9H2AB9cJwe23QbNPKBOVpj84tYQfwagaDf6_N8GH4kMxqohjUWox6VGg9QlsHp53DP1xzVdeXrcA918FnU9rSapnyryINe-obEZ24AFBZwMqgWJAVd9pRcgTh4laUGxN6NzTHmS6XGSPuLhubbn0s"
    ];
    if (parsed.matches) {
      parsed.matches.forEach((m: any, idx: number) => {
        if (!m.image || !m.image.startsWith("http")) {
          m.image = sampleImages[idx % sampleImages.length];
        }
      });
    }
    res.json(parsed);
  } catch (error: any) {
    console.error("Movie Context Error:", error);
    res.status(500).json({ error: error.message || "Failed to search movie contexts" });
  }
});

// AI Conversation / Speech Chat API
app.post("/api/ai/speech-chat", async (req, res) => {
  try {
    const { userMessage, history = [], accent = "US - California" } = req.body;
    const ai = getGeminiAI();

    if (!ai) {
      return res.json({
        correctedText: userMessage ? (userMessage.toLowerCase().includes("go to") ? "I went to the park yesterday and played with my dog." : userMessage) : "I went to the park yesterday.",
        wasErrorDetected: userMessage ? userMessage.toLowerCase().includes("go") : false,
        originalText: userMessage || "I go to the park yesterday and play dog.",
        aiReply: "That sounds lovely! Parks are great for relaxing. What kind of dog do you have?",
        pronunciationScore: 85,
        pronunciationAdvice: "Great clarity on vowels. Watch your 'R' sounds at the end of words.",
        cefrTip: {
          originalPhrase: "I want go...",
          betterPhrase: "I would like to go...",
          explanation: "More Polite & Natural for B2 level"
        },
        grammarTip: "Remember to use the past tense for actions completed yesterday ('played' instead of 'play')."
      });
    }

    const prompt = `You are a supportive, high-level AI English Speaking Tutor named Lumina.
User Accent Setting: ${accent}
User Spoken Message: "${userMessage}"
Conversation History: ${JSON.stringify(history.slice(-4))}

Analyze the user's message for grammar/vocabulary/fluency issues and formulate a warm response to keep the conversation flowing.
Provide a JSON response with:
- originalText: string
- correctedText: string (natural, grammatically correct version)
- wasErrorDetected: boolean
- aiReply: string (conversational response asking a follow-up question)
- pronunciationScore: number (integer 70-98)
- pronunciationAdvice: string (short actionable tip)
- cefrTip: { originalPhrase: string, betterPhrase: string, explanation: string }
- grammarTip: string`;

    const response = await ai.models.generateContent({
      model: "gemini-3.6-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            originalText: { type: Type.STRING },
            correctedText: { type: Type.STRING },
            wasErrorDetected: { type: Type.BOOLEAN },
            aiReply: { type: Type.STRING },
            pronunciationScore: { type: Type.INTEGER },
            pronunciationAdvice: { type: Type.STRING },
            cefrTip: {
              type: Type.OBJECT,
              properties: {
                originalPhrase: { type: Type.STRING },
                betterPhrase: { type: Type.STRING },
                explanation: { type: Type.STRING }
              },
              required: ["originalPhrase", "betterPhrase", "explanation"]
            },
            grammarTip: { type: Type.STRING }
          },
          required: ["originalText", "correctedText", "wasErrorDetected", "aiReply", "pronunciationScore", "pronunciationAdvice", "cefrTip", "grammarTip"]
        }
      }
    });

    res.json(JSON.parse(response.text || "{}"));
  } catch (error: any) {
    console.error("Speech Chat Error:", error);
    res.status(500).json({ error: error.message || "Failed to process speech chat" });
  }
});

// Writing Analysis API
app.post("/api/ai/writing-analysis", async (req, res) => {
  try {
    const { title, text } = req.body;
    const ai = getGeminiAI();

    if (!ai) {
      return res.json({
        overallScore: 82,
        cefrLevel: "B2",
        ieltsScore: "6.5 IELTS",
        insights: [
          {
            type: "grammar",
            title: "Grammar & Spelling",
            originalText: "affect",
            suggestedText: "effect",
            description: 'Instead of "affect", use "effect".',
            rule: '"Affect" is usually a verb, while "effect" is a noun. In this context, you need a noun.'
          },
          {
            type: "vocabulary",
            title: "Vocabulary Enhancement",
            originalText: "good",
            description: 'Suggesting more academic synonyms for "good".',
            synonyms: ["beneficial", "advantageous", "favorable"]
          },
          {
            type: "style",
            title: "Flow & Style",
            description: "Your third sentence is quite long and complex. Consider splitting it to improve readability and impact.",
            suggestion: "However, while some teachers worry that AI will replace them, it will likely serve as an advanced assistant. It handles administrative tasks and grading, freeing up human educators."
          }
        ]
      });
    }

    const prompt = `Analyze the following English essay titled "${title || 'Untitled'}":
    "${text}"

    Provide a JSON response with:
    - overallScore: number (0 to 100)
    - cefrLevel: string (e.g., "B2", "C1")
    - ieltsScore: string (e.g., "6.5 IELTS")
    - insights: array of items:
      - type: "grammar" | "vocabulary" | "style"
      - title: string
      - originalText?: string
      - suggestedText?: string
      - description: string
      - rule?: string
      - synonyms?: string[]
      - suggestion?: string`;

    const response = await ai.models.generateContent({
      model: "gemini-3.6-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            overallScore: { type: Type.INTEGER },
            cefrLevel: { type: Type.STRING },
            ieltsScore: { type: Type.STRING },
            insights: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  type: { type: Type.STRING },
                  title: { type: Type.STRING },
                  originalText: { type: Type.STRING },
                  suggestedText: { type: Type.STRING },
                  description: { type: Type.STRING },
                  rule: { type: Type.STRING },
                  synonyms: { type: Type.ARRAY, items: { type: Type.STRING } },
                  suggestion: { type: Type.STRING }
                },
                required: ["type", "title", "description"]
              }
            }
          },
          required: ["overallScore", "cefrLevel", "ieltsScore", "insights"]
        }
      }
    });

    res.json(JSON.parse(response.text || "{}"));
  } catch (error: any) {
    console.error("Writing Analysis Error:", error);
    res.status(500).json({ error: error.message || "Failed to analyze writing" });
  }
});

// Start Express server with Vite middleware in development
async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Lumina AI Learning Studio running on port ${PORT}`);
  });
}

startServer();
