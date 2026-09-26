// Content script: rê chuột vào từ → tooltip nghĩa; chuột phải → thêm từ vào danh sách học.
// Không chạy trên web app của dự án (manifest exclude_matches) — web tự có tooltip riêng ở Reading/Writing.
(() => {
  if (window.__luminaLookupLoaded) return;
  window.__luminaLookupLoaded = true;

  const HOVER_DELAY_MS = 300;
  const HIDE_DELAY_MS = 250;
  const WORD_PATTERN = /[A-Za-z][A-Za-z'’-]*/g;

  let enabled = true;
  let hoverTimer = null;
  let hideTimer = null;
  let requestSeq = 0;
  let current = null; // { word, sentence, rect, lookup }
  let lastContextTarget = null;

  // ---------- Tooltip (Shadow DOM để CSS của trang không ảnh hưởng) ----------

  const host = document.createElement("div");
  host.style.cssText = "all: initial; position: fixed; top: 0; left: 0; z-index: 2147483647;";
  const shadow = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = `
    .card { position: fixed; width: 320px; max-width: calc(100vw - 24px); box-sizing: border-box;
      background: #ffffff; color: #0f172a; border: 1px solid #e2e8f0; border-radius: 14px;
      box-shadow: 0 12px 32px rgba(15, 23, 42, .22); padding: 12px 14px;
      font: 13px/1.45 "Segoe UI", system-ui, sans-serif; display: none; }
    .card.open { display: block; }
    .head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
    .word { font-size: 18px; font-weight: 700; color: #4338ca; }
    .ipa { font-family: ui-monospace, monospace; font-size: 12px; color: #64748b; }
    .vi { margin: 6px 0 4px; font-size: 15px; font-weight: 600; color: #047857; }
    .pos { display: inline-block; font-size: 10px; font-weight: 700; text-transform: uppercase;
      background: #eef2ff; color: #4338ca; border-radius: 6px; padding: 1px 6px; margin-right: 6px; }
    .def { margin: 4px 0; color: #334155; }
    .sense { margin: 8px 0 0; }
    .sense-top { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px; }
    .vi-sense { font-size: 14px; font-weight: 600; color: #047857; }
    .level { font-size: 10px; font-weight: 800; border-radius: 6px; padding: 1px 6px; color: #fff; background: #64748b; }
    .lv-a1, .lv-a2 { background: #16a34a; } .lv-b1, .lv-b2 { background: #d97706; } .lv-c1, .lv-c2 { background: #dc2626; }
    .hint { margin-top: 6px; font-size: 11px; color: #94a3b8; }
    .ex { margin: 4px 0; font-style: italic; color: #64748b; }
    .muted { color: #94a3b8; }
    .actions { display: flex; gap: 6px; margin-top: 10px; }
    button { all: unset; cursor: pointer; padding: 5px 10px; border-radius: 8px; font-size: 12px;
      font-weight: 600; background: #f1f5f9; color: #334155; }
    button:hover { background: #e2e8f0; }
    button.primary { background: #4f46e5; color: #fff; }
    button.primary:hover { background: #4338ca; }
    button:disabled { opacity: .5; cursor: default; }
    .status { margin-top: 6px; font-size: 12px; }
    .status.ok { color: #047857; } .status.err { color: #dc2626; }
    .toast { position: fixed; right: 16px; bottom: 16px; max-width: 320px; padding: 10px 14px; border-radius: 12px;
      background: #0f172a; color: #fff; font: 13px/1.4 "Segoe UI", system-ui, sans-serif;
      box-shadow: 0 8px 24px rgba(0,0,0,.3); display: none; }
    .toast.open { display: block; } .toast.err { background: #b91c1c; }
  `;
  const card = document.createElement("div");
  card.className = "card";
  const toast = document.createElement("div");
  toast.className = "toast";
  shadow.append(style, card, toast);

  function attachHost() {
    if (!host.isConnected) document.documentElement.appendChild(host);
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  let toastTimer = null;
  function showToast(message, isError) {
    attachHost();
    toast.textContent = message;
    toast.className = `toast open${isError ? " err" : ""}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toast.className = "toast"), 3500);
  }

  const ERROR_TEXT = {
    not_logged_in: "Hãy đăng nhập tài khoản trong popup của extension để lưu từ.",
  };
  const describeError = (code) => ERROR_TEXT[code] || `Lưu thất bại: ${code}`;

  function positionCard(rect) {
    if (!rect) return;
    const margin = 8;
    const width = Math.min(320, window.innerWidth - 24);
    const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12));
    card.style.left = `${left}px`;
    card.style.top = `${rect.bottom + margin}px`;
    // Nếu tràn đáy màn hình thì lật lên trên từ.
    const height = card.offsetHeight;
    if (rect.bottom + margin + height > window.innerHeight - 8 && rect.top - margin - height > 8) {
      card.style.top = `${rect.top - margin - height}px`;
    }
  }

  function speak(word) {
    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(word);
      utterance.lang = "en-US";
      speechSynthesis.speak(utterance);
    }
  }

  function playAudio(lookup, word) {
    if (lookup?.audio) {
      new Audio(lookup.audio).play().catch(() => speak(word));
    } else {
      speak(word);
    }
  }

  // Nghĩa tiếng Việt luôn ở trên cùng. Có bản AI thì chia từng nghĩa theo level CEFR (kiểu Cambridge),
  // chưa có thì hiện nghĩa dịch nhanh + định nghĩa tiếng Anh từ từ điển.
  function renderCard(target, lookup, aiPending) {
    card.replaceChildren();
    const head = el("div", "head");
    head.append(el("span", "word", target.word));
    if (lookup?.ipa) head.append(el("span", "ipa", lookup.ipa));
    card.append(head);

    if (!lookup) {
      card.append(el("div", "def muted", "Đang tra…"));
    } else if (!lookup.found && !lookup.senses?.length) {
      card.append(el("div", "def muted", "Không tìm thấy nghĩa của từ này."));
    } else if (lookup.senses?.length) {
      for (const sense of lookup.senses) {
        const row = el("div", "sense");
        const top = el("div", "sense-top");
        top.append(el("span", `level lv-${(sense.level || "").toLowerCase()}`, sense.level || "?"));
        if (sense.partOfSpeech) top.append(el("span", "pos", sense.partOfSpeech));
        top.append(el("span", "vi-sense", sense.meaningVi));
        row.append(top);
        if (sense.example) row.append(el("div", "ex", `"${sense.example}"`));
        card.append(row);
      }
    } else {
      if (lookup.vietnamese) card.append(el("div", "vi", lookup.vietnamese));
      for (const meaning of lookup.meanings.slice(0, 2)) {
        const row = el("div", "def");
        if (meaning.partOfSpeech) row.append(el("span", "pos", meaning.partOfSpeech));
        row.append(document.createTextNode(meaning.definition));
        card.append(row);
      }
      const example = lookup.meanings.find((m) => m.example)?.example;
      if (example) card.append(el("div", "ex", `"${example}"`));
    }
    if (aiPending) card.append(el("div", "hint", "⏳ Đang tạo nghĩa chi tiết theo level…"));

    const actions = el("div", "actions");
    const audioBtn = el("button", "", "🔊 Nghe");
    audioBtn.addEventListener("click", () => playAudio(lookup, target.word));
    const saveBtn = el("button", "primary", "＋ Lưu vào từ vựng");
    saveBtn.addEventListener("click", () => saveTarget(target, saveBtn));
    actions.append(audioBtn, saveBtn);
    card.append(actions, el("div", "status"));
  }

  function hideCard() {
    card.classList.remove("open");
    current = null;
    requestSeq += 1;
  }

  // ---------- Tìm từ dưới con trỏ ----------

  function caretAt(x, y) {
    if (document.caretPositionFromPoint) {
      const pos = document.caretPositionFromPoint(x, y);
      return pos ? { node: pos.offsetNode, offset: pos.offset } : null;
    }
    if (document.caretRangeFromPoint) {
      const range = document.caretRangeFromPoint(x, y);
      return range ? { node: range.startContainer, offset: range.startOffset } : null;
    }
    return null;
  }

  function isEditable(node) {
    const element = node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
    return Boolean(element?.closest("input, textarea, select, [contenteditable=''], [contenteditable='true']"));
  }

  function sentenceAround(text, start, end) {
    let from = start;
    while (from > 0 && !/[.!?\n]/.test(text[from - 1])) from -= 1;
    let to = end;
    while (to < text.length && !/[.!?\n]/.test(text[to])) to += 1;
    return text.slice(from, Math.min(to + 1, text.length)).trim().slice(0, 300);
  }

  function wordAtPoint(x, y) {
    const caret = caretAt(x, y);
    if (!caret || caret.node.nodeType !== Node.TEXT_NODE || isEditable(caret.node)) return null;
    const text = caret.node.data;
    WORD_PATTERN.lastIndex = 0;
    let match;
    while ((match = WORD_PATTERN.exec(text))) {
      const start = match.index;
      const end = start + match[0].length;
      if (caret.offset < start || caret.offset > end) continue;
      const range = document.createRange();
      range.setStart(caret.node, start);
      range.setEnd(caret.node, end);
      // Caret API "hít" vào ký tự gần nhất, nên phải kiểm tra con trỏ thật sự nằm trên chữ.
      const hit = [...range.getClientRects()].find(
        (r) => x >= r.left - 1 && x <= r.right + 1 && y >= r.top - 1 && y <= r.bottom + 1,
      );
      if (!hit) return null;
      const word = match[0].replace(/^[-'’]+|[-'’]+$/g, "");
      if (word.length < 2) return null;
      return { word, sentence: sentenceAround(text, start, end), rect: range.getBoundingClientRect() };
    }
    return null;
  }

  function selectedTarget() {
    const selection = window.getSelection();
    const text = selection ? selection.toString().trim() : "";
    if (!text || text.length > 50 || text.split(/\s+/).length > 3 || !/[A-Za-z]/.test(text)) return null;
    const rect = selection.rangeCount ? selection.getRangeAt(0).getBoundingClientRect() : null;
    return { word: text, sentence: "", rect };
  }

  // ---------- Hover ----------

  async function showFor(target) {
    const seq = ++requestSeq;
    attachHost();
    current = { ...target, lookup: null };
    renderCard(target, null);
    card.classList.add("open");
    positionCard(target.rect);

    const response = await chrome.runtime.sendMessage({ type: "LOOKUP", word: target.word }).catch(() => null);
    if (seq !== requestSeq) return;
    const lookup = response?.ok ? response.data : { found: false };
    current.lookup = lookup;
    renderCard(target, lookup, Boolean(lookup.aiAvailable));
    positionCard(target.rect);
    if (!lookup.aiAvailable) return;

    // Đã đăng nhập: nâng cấp bằng nghĩa Ollama (chậm hơn nên hiện sau). Lỗi thì giữ kết quả nhanh.
    const ai = await chrome.runtime
      .sendMessage({ type: "LOOKUP_AI", word: target.word, sentence: target.sentence })
      .catch(() => null);
    if (seq !== requestSeq) return;
    if (ai?.ok && ai.data.senses.length) {
      current.lookup = {
        ...lookup,
        found: true,
        ipa: ai.data.ipa || lookup.ipa,
        senses: ai.data.senses,
        synonyms: ai.data.synonyms.length ? ai.data.synonyms : lookup.synonyms,
        antonyms: ai.data.antonyms.length ? ai.data.antonyms : lookup.antonyms,
      };
    }
    renderCard(target, current.lookup, false);
    positionCard(target.rect);
  }

  function scheduleHide() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(hideCard, HIDE_DELAY_MS);
  }

  document.addEventListener(
    "mousemove",
    (event) => {
      if (!enabled) return;
      clearTimeout(hoverTimer);
      // Con trỏ đang ở trong tooltip: giữ nguyên để người dùng bấm nút.
      if (event.composedPath().includes(host)) {
        clearTimeout(hideTimer);
        return;
      }
      const { clientX, clientY } = event;
      hoverTimer = setTimeout(() => {
        const target = wordAtPoint(clientX, clientY);
        if (!target) {
          if (current) scheduleHide();
          return;
        }
        clearTimeout(hideTimer);
        if (current && current.word.toLowerCase() === target.word.toLowerCase()) return;
        showFor(target);
      }, HOVER_DELAY_MS);
    },
    { passive: true },
  );

  host.addEventListener("mouseleave", scheduleHide);
  document.addEventListener("scroll", () => current && hideCard(), { passive: true, capture: true });
  document.addEventListener("keydown", (event) => event.key === "Escape" && hideCard());

  // ---------- Chuột phải & lưu từ ----------

  document.addEventListener(
    "contextmenu",
    (event) => {
      if (!enabled) return;
      const target = selectedTarget() || wordAtPoint(event.clientX, event.clientY);
      lastContextTarget = target;
      chrome.runtime.sendMessage({ type: "MENU_TITLE", word: target?.word || "" }).catch(() => {});
    },
    true,
  );

  async function saveTarget(target, button) {
    const status = card.querySelector(".status");
    const report = (message, ok) => {
      if (status && card.classList.contains("open")) {
        status.textContent = message;
        status.className = `status ${ok ? "ok" : "err"}`;
      } else {
        showToast(message, !ok);
      }
    };
    if (button) button.disabled = true;
    try {
      let lookup = current?.word === target.word ? current.lookup : null;
      if (!lookup) {
        const looked = await chrome.runtime.sendMessage({ type: "LOOKUP", word: target.word });
        lookup = looked?.ok ? looked.data : null;
      }
      const response = await chrome.runtime.sendMessage({
        type: "SAVE",
        input: { word: target.word.toLowerCase(), sentence: target.sentence, lookup },
      });
      if (!response?.ok) throw new Error(response?.error || "unknown_error");
      report(`Đã lưu "${target.word}" vào danh sách từ vựng.`, true);
    } catch (error) {
      report(describeError(error.message), false);
      if (button) button.disabled = false;
    }
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type !== "SAVE_TARGET_WORD") return;
    // Chỉ dùng từ được bôi đen hoặc từ dưới con trỏ lúc bấm chuột phải — không dùng tooltip cũ còn treo,
    // nếu không chuột phải vào chỗ trống sẽ lưu nhầm từ vừa hover trước đó.
    const target = selectedTarget() || lastContextTarget;
    lastContextTarget = null;
    if (!target) {
      showToast("Không tìm thấy từ tiếng Anh ở vị trí này.", true);
      return;
    }
    saveTarget(target, null);
  });

  // ---------- Bật/tắt từ popup ----------

  chrome.storage.local.get("enabled").then((data) => {
    enabled = data.enabled !== false;
  });
  chrome.storage.onChanged.addListener((changes) => {
    if (changes.enabled) {
      enabled = changes.enabled.newValue !== false;
      if (!enabled) hideCard();
    }
  });
})();
