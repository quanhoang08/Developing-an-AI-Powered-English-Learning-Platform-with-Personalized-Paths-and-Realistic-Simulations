// Phụ đề YouTube trong Lumina: đọc chữ từ phụ đề (CC) mà YouTube đang vẽ trên player, hiện lại ở khung riêng với
// công tắc English / Tiếng Việt / Cả hai. Bản dịch tiếng Việt do background.js lấy (Ollama qua backend, không có thì MyMemory).
// Khung nằm trong DOM thường (không Shadow DOM) để content-script.js rê chuột tra từ được từng từ tiếng Anh.
// ponytail: đọc DOM của YouTube (.ytp-caption-segment) nên hỏng nếu YouTube đổi tên class; video không có phụ đề thì chưa có gì để đọc
// (bước sau: bắt âm thanh tab + nhận dạng giọng nói).
(() => {
  if (window.__luminaYtCaptions) return;
  window.__luminaYtCaptions = true;

  const POLL_MS = 250;
  const TRANSLATE_DEBOUNCE_MS = 350;
  const CLEAR_AFTER_EMPTY_POLLS = 8; // ~2 giây không có chữ thì ẩn dòng cũ
  const VI_LETTERS = /[ăâđêôơưàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]/i;
  const MODES = [
    ["en", "English"],
    ["vi", "Tiếng Việt"],
    ["both", "Cả hai"],
  ];

  let overlayOn = true;
  let mode = "both";
  let lastText = "";
  let emptyPolls = 0;
  let translateTimer = null;
  let translateSeq = 0;
  let currentVideo = "";
  let sawCaption = false; // YouTube đã vẽ chữ phụ đề nào cho video hiện tại chưa
  const NO_CAPTION_HINT_SECONDS = 15; // phát quá ngần này giây mà chưa có chữ nào thì nhắc dùng phụ đề từ âm thanh
  const NO_CAPTION_HINT =
    "Chưa thấy phụ đề của YouTube. Nếu video không có phụ đề, mở popup extension và bấm “Bật phụ đề cho tab này”.";

  const STYLE_ID = "lumina-yt-captions-style";
  if (!document.getElementById(STYLE_ID)) {
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #movie_player.lumina-yt-on .ytp-caption-window-container { opacity: 0 !important; pointer-events: none !important; }
      #lumina-yt-captions { position: absolute; left: 50%; bottom: 72px; transform: translateX(-50%); z-index: 60;
        width: max-content; max-width: min(86%, 980px); box-sizing: border-box; padding: 8px 14px 10px; border-radius: 12px;
        background: rgba(8, 8, 12, .78); color: #fff; text-align: center; font: 500 22px/1.4 "Segoe UI", system-ui, sans-serif;
        pointer-events: auto; cursor: default; user-select: text; }
      #lumina-yt-captions[hidden] { display: none; }
      #lumina-yt-captions { min-width: 260px; }
      #lumina-yt-captions .lumina-bar { position: absolute; left: 50%; transform: translateX(-50%); bottom: 100%; padding-bottom: 4px;
        width: max-content; white-space: nowrap; display: flex; gap: 4px; opacity: 0; pointer-events: none; transition: opacity .15s; }
      #lumina-yt-captions:hover .lumina-bar { opacity: 1; pointer-events: auto; }
      #lumina-yt-captions .lumina-bar button { all: unset; cursor: pointer; font: 600 11px/1 "Segoe UI", system-ui, sans-serif;
        padding: 4px 8px; border-radius: 999px; background: rgba(255,255,255,.16); color: #fff; }
      #lumina-yt-captions .lumina-bar button[aria-pressed="true"] { background: #4f46e5; }
      #lumina-yt-captions .lumina-en { display: block; }
      #lumina-yt-captions .lumina-vi { display: block; color: #6ee7b7; font-size: 19px; margin-top: 2px; }
      #lumina-yt-captions .lumina-hint { display: block; font-size: 14px; color: #fde68a; }
      #lumina-yt-captions [hidden] { display: none; }
    `;
    document.documentElement.appendChild(style);
  }

  const overlay = document.createElement("div");
  overlay.id = "lumina-yt-captions";
  overlay.hidden = true;
  const bar = document.createElement("div");
  bar.className = "lumina-bar";
  const modeButtons = MODES.map(([value, label]) => {
    const button = document.createElement("button");
    button.textContent = label;
    button.addEventListener("click", () => {
      mode = value;
      chrome.storage.local.set({ captionMode: value });
      render(true);
    });
    bar.appendChild(button);
    return [value, button];
  });
  const enLine = document.createElement("span");
  enLine.className = "lumina-en";
  const viLine = document.createElement("span");
  viLine.className = "lumina-vi";
  // Chữ Việt không đi qua tra từ tiếng Anh của content-script.js (từ ASCII như "la", "an" sẽ bị tra nhầm).
  viLine.setAttribute("data-lumina-skip-lookup", "");
  const hint = document.createElement("span");
  hint.className = "lumina-hint";
  hint.setAttribute("data-lumina-skip-lookup", "");
  overlay.append(bar, enLine, viLine, hint);
  // Bấm vào khung (chọn chữ, đổi chế độ) không được làm video tạm dừng.
  for (const type of ["click", "dblclick", "mousedown", "mouseup"]) {
    overlay.addEventListener(type, (event) => event.stopPropagation());
  }

  // Chữ đang hiển thị. viSource: phụ đề gốc của video đã là tiếng Việt.
  const view = { en: "", vi: "", viSource: false, hint: "" };

  // Con trỏ đang ở trên khung (bấm nút, tra từ): giữ nguyên chữ, không để khung đổi kích thước/xê dịch dưới con trỏ;
  // phụ đề mới được vẽ khi chuột rời khung. force=true cho thao tác của chính người dùng (đổi chế độ).
  let hovering = false;
  let dirty = false;
  overlay.addEventListener("mouseenter", () => (hovering = true));
  overlay.addEventListener("mouseleave", () => {
    hovering = false;
    if (dirty) render();
  });

  function render(force = false) {
    if (hovering && !force) {
      dirty = true;
      return;
    }
    dirty = false;
    for (const [value, button] of modeButtons) button.setAttribute("aria-pressed", String(value === mode));
    // Chế độ Tiếng Việt: trong lúc chờ bản dịch vẫn hiện dòng tiếng Anh để khung không biến mất.
    const showEn = (mode !== "vi" || !view.vi) && Boolean(view.en) && !view.viSource;
    const showVi = mode !== "en" && Boolean(view.vi);
    enLine.textContent = showEn ? view.en : "";
    enLine.hidden = !showEn;
    viLine.textContent = showVi ? view.vi : "";
    viLine.hidden = !showVi;
    hint.textContent = view.hint;
    hint.hidden = !view.hint;
    overlay.hidden = !overlayOn || !(showEn || showVi || view.hint);
  }

  async function translate(text, seq) {
    const response = await chrome.runtime.sendMessage({ type: "TRANSLATE", text }).catch(() => null);
    if (seq !== translateSeq) return; // dòng đã đổi trong lúc chờ dịch
    view.vi = response?.ok && response.data ? response.data : "";
    render();
  }

  function onCaption(text) {
    translateSeq += 1;
    clearTimeout(translateTimer);
    view.en = text;
    view.vi = "";
    view.hint = "";
    view.viSource = VI_LETTERS.test(text);
    if (view.viSource) {
      // Video có phụ đề tiếng Việt sẵn: hiện thẳng ở dòng Việt, khỏi dịch.
      view.vi = text;
      render();
      return;
    }
    render();
    if (!text) return;
    const seq = translateSeq;
    translateTimer = setTimeout(() => translate(text, seq), TRANSLATE_DEBOUNCE_MS);
  }

  function readCaption() {
    const segments = document.querySelectorAll("#movie_player .ytp-caption-segment");
    return [...segments].map((node) => node.textContent).join(" ").replace(/\s+/g, " ").trim();
  }

  function videoId() {
    return new URLSearchParams(location.search).get("v") || "";
  }

  // Mỗi video mới: bật CC nếu đang tắt (người học không phải tự bấm), báo nếu video không có phụ đề.
  function prepareVideo() {
    const id = videoId();
    if (id === currentVideo) return;
    currentVideo = id;
    sawCaption = false;
    lastText = "";
    onCaption("");
    if (!id) return;
    setTimeout(() => {
      if (id !== currentVideo || !overlayOn) return;
      const button = document.querySelector(".ytp-subtitles-button");
      const unavailable = !button || button.offsetParent === null || button.getAttribute("aria-disabled") === "true";
      if (unavailable) {
        view.hint = "Video này chưa có phụ đề YouTube.";
        render();
      } else if (button.getAttribute("aria-pressed") === "false") {
        button.click();
      }
    }, 2500);
  }

  function tick() {
    const player = document.getElementById("movie_player");
    if (!player) return;
    if (!overlay.isConnected || overlay.parentElement !== player) player.appendChild(overlay);
    player.classList.toggle("lumina-yt-on", overlayOn);
    if (!overlayOn) {
      overlay.hidden = true;
      return;
    }
    prepareVideo();
    const text = readCaption();
    if (!text && !sawCaption && !view.hint) {
      const video = player.querySelector("video");
      if (video && !video.paused && video.currentTime > NO_CAPTION_HINT_SECONDS) {
        view.hint = NO_CAPTION_HINT;
        render();
      }
    }
    if (text) {
      sawCaption = true;
      emptyPolls = 0;
      if (text !== lastText) {
        lastText = text;
        onCaption(text);
      }
    } else if (lastText && ++emptyPolls >= CLEAR_AFTER_EMPTY_POLLS) {
      lastText = "";
      onCaption("");
    }
  }

  chrome.storage.local.get(["captionOverlay", "captionMode"]).then((data) => {
    overlayOn = data.captionOverlay !== false;
    if (MODES.some(([value]) => value === data.captionMode)) mode = data.captionMode;
    render();
  });
  chrome.storage.onChanged.addListener((changes) => {
    if (changes.captionOverlay) overlayOn = changes.captionOverlay.newValue !== false;
    if (changes.captionMode && MODES.some(([value]) => value === changes.captionMode.newValue)) {
      mode = changes.captionMode.newValue;
    }
    render(true);
  });

  setInterval(tick, POLL_MS);
})();
