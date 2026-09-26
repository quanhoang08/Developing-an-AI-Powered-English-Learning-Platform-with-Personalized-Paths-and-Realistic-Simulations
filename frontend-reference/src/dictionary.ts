// Tra nghĩa hover: Free Dictionary API (định nghĩa EN, IPA, synonyms) + MyMemory (nghĩa tiếng Việt).
// Cả hai đều công khai, cho phép CORS từ browser và không cần đăng nhập — cùng nguồn với extension.
const DICT_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/";
const TRANSLATE_URL = "https://api.mymemory.translated.net/get";
const CACHE_LIMIT = 300;

export interface LookupMeaning {
  partOfSpeech: string | null;
  definition: string;
  example: string | null;
}

// 1 nghĩa kiểu Cambridge do Ollama sinh (chỉ có khi đã đăng nhập): level CEFR + nghĩa tiếng Việt.
export interface LookupSenseVi {
  level: string;
  partOfSpeech: string;
  meaningVi: string;
  example: string | null;
}

export interface LookupData {
  senses?: LookupSenseVi[];
  found: boolean;
  word: string;
  ipa: string | null;
  audio: string | null;
  vietnamese: string | null;
  meanings: LookupMeaning[];
  synonyms: string[];
  antonyms: string[];
}

const cache = new Map<string, LookupData>();

// Thử chính từ đó trước, rồi các dạng gốc (số nhiều, quá khứ, -ing...) nếu từ điển không có.
function candidateForms(word: string): string[] {
  const forms = [word];
  const add = (form: string) => {
    if (form.length >= 3 && !forms.includes(form)) forms.push(form);
  };
  if (word.endsWith("ies")) add(word.slice(0, -3) + "y");
  if (word.endsWith("es")) add(word.slice(0, -2));
  if (word.endsWith("s")) add(word.slice(0, -1));
  if (word.endsWith("ied")) add(word.slice(0, -3) + "y");
  if (word.endsWith("ed")) {
    add(word.slice(0, -2));
    add(word.slice(0, -1));
  }
  if (word.endsWith("ing")) {
    const stem = word.slice(0, -3);
    add(stem);
    add(stem + "e");
    if (stem.length > 3 && stem[stem.length - 1] === stem[stem.length - 2]) add(stem.slice(0, -1));
  }
  if (word.endsWith("ly")) add(word.slice(0, -2));
  return forms;
}

async function fetchVietnamese(text: string): Promise<string | null> {
  try {
    const response = await fetch(`${TRANSLATE_URL}?q=${encodeURIComponent(text)}&langpair=en|vi`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) return null;
    const body = await response.json();
    const translated: string | undefined = body?.responseData?.translatedText;
    if (!translated || translated.toLowerCase() === text.toLowerCase()) return null;
    if (/MYMEMORY WARNING|QUERY LENGTH LIMIT/i.test(translated)) return null;
    return translated;
  } catch {
    return null;
  }
}

const unique = (list: string[]) => [...new Set(list.filter(Boolean))];

export async function lookupDefinition(rawWord: string): Promise<LookupData> {
  const word = rawWord.toLowerCase().trim();
  const notFound: LookupData = { found: false, word, ipa: null, audio: null, vietnamese: null, meanings: [], synonyms: [], antonyms: [] };
  if (!/^[a-z][a-z'’-]{0,49}$/.test(word)) return notFound;
  const cached = cache.get(word);
  if (cached) return cached;

  // Dịch chạy song song với tra từ điển: từ điển hay treo nên không được chặn nghĩa tiếng Việt.
  const viPromise = fetchVietnamese(word);
  let entries: any[] | null = null;
  let headword = word;
  try {
    for (const form of candidateForms(word)) {
      const response = await fetch(DICT_URL + encodeURIComponent(form), { signal: AbortSignal.timeout(3000) });
      if (response.status === 404) continue;
      if (!response.ok) break;
      const body = await response.json();
      if (Array.isArray(body) && body.length > 0) {
        entries = body;
        headword = form;
        break;
      }
    }
  } catch {
    // Từ điển miễn phí hay chập chờn (timeout/5xx) — vẫn còn nghĩa dịch tiếng Việt để hiển thị.
    entries = null;
  }

  let result: LookupData;
  if (entries) {
    const phonetics = entries.flatMap((entry) => entry.phonetics || []);
    const allMeanings: any[] = entries.flatMap((entry) => entry.meanings || []);
    const collect = (key: "synonyms" | "antonyms") =>
      unique(allMeanings.flatMap((m) => [...(m[key] || []), ...(m.definitions || []).flatMap((d: any) => d[key] || [])])).slice(0, 6);
    result = {
      found: true,
      word,
      ipa: entries.find((entry) => entry.phonetic)?.phonetic || phonetics.find((p) => p.text)?.text || null,
      audio: phonetics.find((p) => p.audio)?.audio || null,
      vietnamese: (await viPromise) ?? (headword !== word ? await fetchVietnamese(headword) : null),
      meanings: allMeanings.slice(0, 3).map((meaning) => ({
        partOfSpeech: meaning.partOfSpeech || null,
        definition: meaning.definitions?.[0]?.definition || "",
        example: meaning.definitions?.[0]?.example || null,
      })),
      synonyms: collect("synonyms"),
      antonyms: collect("antonyms"),
    };
  } else {
    // Không có trong từ điển (tên riêng, từ lóng...) — vẫn thử dịch để có gợi ý nghĩa.
    const vietnamese = await viPromise;
    result = vietnamese ? { ...notFound, found: true, vietnamese } : notFound;
  }

  // Kết quả lỗi mạng tạm thời không cache để lần hover sau thử lại.
  if (result.found) {
    if (cache.size >= CACHE_LIMIT) cache.delete(cache.keys().next().value as string);
    cache.set(word, result);
  }
  return result;
}
