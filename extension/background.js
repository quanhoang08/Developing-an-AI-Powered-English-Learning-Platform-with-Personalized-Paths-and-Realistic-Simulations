// Service worker: tra từ (không cần đăng nhập), đăng nhập backend, lưu từ vựng, menu chuột phải.
// Mọi request cross-origin đều đi qua đây (host_permissions) nên không vướng CORS của trang.
const DEFAULT_API_BASE_URL = "http://localhost:8000";
const MENU_ID = "lumina-add-vocab";
const DICT_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/";
const TRANSLATE_URL = "https://api.mymemory.translated.net/get";
const CACHE_LIMIT = 300;

const lookupCache = new Map();

async function getConfig() {
  const data = await chrome.storage.local.get(["apiBaseUrl", "accessToken", "refreshToken", "email"]);
  return {
    apiBaseUrl: (data.apiBaseUrl || DEFAULT_API_BASE_URL).replace(/\/+$/, ""),
    accessToken: data.accessToken || null,
    refreshToken: data.refreshToken || null,
    email: data.email || null,
  };
}

// ---------- Tra từ ----------

// Thử chính từ đó trước, rồi các dạng gốc (số nhiều, quá khứ, -ing...) nếu từ điển không có.
function candidateForms(word) {
  const forms = [word];
  const add = (form) => form.length >= 3 && !forms.includes(form) && forms.push(form);
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

async function fetchDictionary(word) {
  for (const form of candidateForms(word)) {
    const response = await fetch(DICT_URL + encodeURIComponent(form), { signal: AbortSignal.timeout(3000) });
    if (response.status === 404) continue;
    if (!response.ok) throw new Error(`dictionary_${response.status}`);
    const entries = await response.json();
    if (Array.isArray(entries) && entries.length > 0) return { form, entries };
  }
  return null;
}

async function fetchVietnamese(text) {
  try {
    const url = `${TRANSLATE_URL}?q=${encodeURIComponent(text)}&langpair=en|vi`;
    const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!response.ok) return null;
    const body = await response.json();
    const translated = body?.responseData?.translatedText;
    // MyMemory trả lại chính từ gốc khi không dịch được — coi như không có nghĩa.
    if (!translated || translated.toLowerCase() === text.toLowerCase()) return null;
    if (/MYMEMORY WARNING|QUERY LENGTH LIMIT/i.test(translated)) return null;
    return translated;
  } catch {
    return null;
  }
}

function unique(list) {
  return [...new Set(list.filter(Boolean))];
}

function shapeEntries(word, form, entries) {
  const phonetics = entries.flatMap((entry) => entry.phonetics || []);
  const ipa = entries.find((entry) => entry.phonetic)?.phonetic || phonetics.find((p) => p.text)?.text || null;
  const audio = phonetics.find((p) => p.audio)?.audio || null;
  const allMeanings = entries.flatMap((entry) => entry.meanings || []);
  const meanings = allMeanings.slice(0, 3).map((meaning) => {
    const first = meaning.definitions?.[0] || {};
    return {
      partOfSpeech: meaning.partOfSpeech || null,
      definition: first.definition || "",
      example: first.example || null,
    };
  });
  const collect = (key) =>
    unique(allMeanings.flatMap((m) => [...(m[key] || []), ...(m.definitions || []).flatMap((d) => d[key] || [])])).slice(0, 6);
  return { word, headword: form, ipa, audio, meanings, synonyms: collect("synonyms"), antonyms: collect("antonyms") };
}

async function lookupWord(rawWord) {
  const word = String(rawWord || "").toLowerCase().trim();
  if (!/^[a-z][a-z'’-]{0,49}$/.test(word)) return { found: false, word };
  if (lookupCache.has(word)) return lookupCache.get(word);

  // Từ điển miễn phí hay chập chờn (timeout/5xx) — lỗi ở đây không được làm mất luôn nghĩa tiếng Việt.
  // Dịch chạy song song: từ điển hay treo nên không được chặn nghĩa tiếng Việt.
  const viPromise = fetchVietnamese(word);
  const dictionary = await fetchDictionary(word).catch(() => null);
  let result;
  if (dictionary) {
    const shaped = shapeEntries(word, dictionary.form, dictionary.entries);
    const vietnamese = (await viPromise) ?? (shaped.headword !== word ? await fetchVietnamese(shaped.headword) : null);
    result = { found: true, ...shaped, vietnamese };
  } else {
    // Không có trong từ điển (tên riêng, từ lóng...) — vẫn thử dịch để có gợi ý nghĩa.
    const vietnamese = await viPromise;
    result = vietnamese
      ? { found: true, word, headword: word, ipa: null, audio: null, meanings: [], synonyms: [], antonyms: [], vietnamese }
      : { found: false, word };
  }

  // Kết quả lỗi mạng tạm thời không được cache, để lần hover sau thử lại.
  if (result.found) {
    if (lookupCache.size >= CACHE_LIMIT) lookupCache.delete(lookupCache.keys().next().value);
    lookupCache.set(word, result);
  }
  return result;
}

// Tra nhanh (không cần đăng nhập) + báo cho content script biết có thể nâng cấp lên bản AI hay không.
async function lookupFast(word) {
  const [result, { accessToken }] = await Promise.all([lookupWord(word), getConfig()]);
  return { ...result, aiAvailable: Boolean(accessToken) };
}

// ---------- Tra nghĩa bằng Ollama qua backend (cần đăng nhập, không tốn quota Gemini) ----------

const aiCache = new Map();
const aiInFlight = new Map();

function postLookup(payload, token, apiBaseUrl) {
  return fetch(`${apiBaseUrl}/api/extension/lookup`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
    // Ollama 7B có thể mất vài chục giây khi nạp model lần đầu.
    signal: AbortSignal.timeout(90000),
  });
}

async function fetchAiLookup(word, sentence) {
  const config = await getConfig();
  if (!config.accessToken) throw new Error("not_logged_in");
  const payload = { term: word, context_sentence: (sentence || word).slice(0, 500) };
  let response = await postLookup(payload, config.accessToken, config.apiBaseUrl);
  if (response.status === 401) {
    const fresh = await refreshAccessToken();
    if (!fresh) throw new Error("not_logged_in");
    response = await postLookup(payload, fresh, config.apiBaseUrl);
  }
  if (!response.ok) throw new Error(await readError(response));
  const body = await response.json();
  return {
    ipa: body.ipa || null,
    senses: (body.senses || []).map((s) => ({
      level: s.level,
      partOfSpeech: s.part_of_speech,
      meaningVi: s.meaning_vi,
      example: s.example_en || null,
    })),
    synonyms: body.synonyms || [],
    antonyms: body.antonyms || [],
  };
}

function lookupAi(rawWord, sentence) {
  const word = String(rawWord || "").toLowerCase().trim();
  const key = `${word}|${String(sentence || "").slice(0, 200).toLowerCase()}`;
  if (aiCache.has(key)) return Promise.resolve(aiCache.get(key));
  // Hover cùng từ nhiều lần trong lúc Ollama đang chạy thì dùng chung 1 request.
  if (aiInFlight.has(key)) return aiInFlight.get(key);
  const pending = fetchAiLookup(word, sentence)
    .then((data) => {
      if (aiCache.size >= CACHE_LIMIT) aiCache.delete(aiCache.keys().next().value);
      aiCache.set(key, data);
      return data;
    })
    .finally(() => aiInFlight.delete(key));
  aiInFlight.set(key, pending);
  return pending;
}

// ---------- Xác thực ----------

async function readError(response) {
  const body = await response.json().catch(() => ({}));
  return typeof body.detail === "string" ? body.detail : `request_failed_${response.status}`;
}

async function login(email, password, apiBaseUrl) {
  const base = (apiBaseUrl || DEFAULT_API_BASE_URL).replace(/\/+$/, "");
  const response = await fetch(`${base}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // client_type "extension": token chỉ gọi được /api/reading/lookup, /api/vocab, /api/extension/*.
    body: JSON.stringify({ email, password, client_type: "extension" }),
  });
  if (!response.ok) throw new Error(await readError(response));
  const tokens = await response.json();
  await chrome.storage.local.set({
    apiBaseUrl: base,
    email,
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
  });
}

async function logout() {
  await chrome.storage.local.remove(["accessToken", "refreshToken", "email"]);
}

// Đổi refresh token lấy access token mới; thất bại nghĩa là phiên đã hết hạn hẳn.
async function refreshAccessToken() {
  const { apiBaseUrl, refreshToken } = await getConfig();
  if (!refreshToken) return null;
  const response = await fetch(`${apiBaseUrl}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    await logout();
    return null;
  }
  const tokens = await response.json();
  await chrome.storage.local.set({
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token || refreshToken,
  });
  return tokens.access_token;
}

// ---------- Lưu từ vựng ----------

function postVocab(payload, token, apiBaseUrl) {
  return fetch(`${apiBaseUrl}/api/vocab`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}

function buildVocabPayload(input, sourceUrl) {
  const { lookup, sentence } = input;
  // Bản AI (Ollama) có senses tiếng Việt theo level thì ưu tiên nghĩa đầu tiên (hợp ngữ cảnh nhất).
  const aiSense = lookup?.senses?.[0];
  const primary = lookup?.meanings?.[0];
  const definition = aiSense
    ? aiSense.meaningVi
    : [lookup?.vietnamese, primary?.definition].filter(Boolean).join(" — ") || null;
  return {
    term: input.word.slice(0, 100),
    definition,
    // Backend yêu cầu đúng 1 nguồn: extension luôn dùng URL trang đang đọc.
    source_url: sourceUrl,
    ipa: lookup?.ipa || null,
    part_of_speech: aiSense?.partOfSpeech || primary?.partOfSpeech || null,
    example_sentence: (sentence || aiSense?.example || primary?.example || "").slice(0, 500) || null,
    synonyms: lookup?.synonyms || [],
    antonyms: lookup?.antonyms || [],
  };
}

async function saveVocab(input, sourceUrl) {
  const config = await getConfig();
  if (!config.accessToken) throw new Error("not_logged_in");

  const payload = buildVocabPayload(input, sourceUrl);
  let response = await postVocab(payload, config.accessToken, config.apiBaseUrl);
  if (response.status === 401) {
    const fresh = await refreshAccessToken();
    if (!fresh) throw new Error("not_logged_in");
    response = await postVocab(payload, fresh, config.apiBaseUrl);
  }
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

// ---------- Menu chuột phải ----------

function createMenu() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: MENU_ID,
      title: "Thêm từ này vào danh sách từ vựng",
      contexts: ["all"],
    });
  });
}

chrome.runtime.onInstalled.addListener(createMenu);
chrome.runtime.onStartup.addListener(createMenu);

// Content script báo từ đang trỏ chuột khi người dùng bấm chuột phải để menu hiện đúng từ.
function setMenuTitle(word) {
  chrome.contextMenus.update(MENU_ID, {
    title: word ? `Thêm "${word.slice(0, 30)}" vào từ vựng` : "Thêm từ này vào danh sách từ vựng",
  });
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== MENU_ID || !tab?.id) return;
  try {
    // Content script biết từ nào đang được trỏ/bôi đen và câu chứa nó.
    await chrome.tabs.sendMessage(tab.id, { type: "SAVE_TARGET_WORD" }, { frameId: info.frameId ?? 0 });
  } catch {
    // Trang không có content script (chrome://, PDF viewer...) — không có gì để lưu.
  }
});

// ---------- Nhận message ----------

const handlers = {
  LOOKUP: (message) => lookupFast(message.word),
  LOOKUP_AI: (message) => lookupAi(message.word, message.sentence),
  SAVE: (message, sender) => saveVocab(message.input, sender.tab?.url || sender.url),
  MENU_TITLE: (message) => setMenuTitle(message.word),
  AUTH_STATUS: async () => {
    const { email, accessToken, apiBaseUrl } = await getConfig();
    return { loggedIn: Boolean(accessToken), email, apiBaseUrl };
  },
  LOGIN: (message) => login(message.email, message.password, message.apiBaseUrl),
  LOGOUT: () => logout(),
};

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const handler = handlers[message?.type];
  if (!handler) return false;
  Promise.resolve()
    .then(() => handler(message, sender))
    .then((data) => sendResponse({ ok: true, data }))
    .catch((error) => sendResponse({ ok: false, error: error.message || "unknown_error" }));
  return true;
});
