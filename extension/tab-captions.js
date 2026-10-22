// Khung phụ đề cho âm thanh tab (trang bất kỳ, kể cả video YouTube không có phụ đề): nhận phụ đề đã nhận dạng + dịch từ
// background.js (offscreen.js thu âm tab -> backend) và vẽ nổi ở đáy trang với công tắc English / Tiếng Việt / Cả hai.
// Nằm trong DOM thường (không Shadow DOM) để content-script.js rê chuột tra từ được từng từ tiếng Anh.
(() => {
  if (window.top !== window || window.__luminaTabCaptions) return;
  window.__luminaTabCaptions = true;

  const CLEAR_AFTER_MS = 7000;
  const MODES = [
    ["en", "English"],
    ["vi", "Tiếng Việt"],
    ["both", "Cả hai"],
  ];
  const STATUS_TEXT = {
    connecting: "Đang kết nối phụ đề…",
    ready: "Đang nghe âm thanh của tab này… (lần đầu tải mô hình có thể mất vài chục giây)",
    fellBack: "Phụ đề cloud không dùng được, đã chuyển sang chế độ offline (chậm hơn, chỉ hiện câu đã xong).",
    invalid_token: "Phiên đăng nhập hết hạn. Hãy đăng nhập lại trong popup extension.",
    captions_unavailable: "Phụ đề đang không khả dụng, hãy thử lại sau.",
    local_models_unavailable: "Không tải được mô hình nhận dạng offline.",
    unreachable: "Không kết nối được tới backend. Kiểm tra API URL trong popup.",
    capture_failed: "Không thu được âm thanh của tab này.",
    closed: "",
  };

  let mode = "both";
  let clearTimer = null;
  const view = { en: "", vi: "", final: true, hint: "", hintIsError: false };

  const STYLE_ID = "lumina-tab-captions-style";
  if (!document.getElementById(STYLE_ID)) {
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #lumina-tab-captions { position: fixed; left: 50%; bottom: 7%; transform: translateX(-50%); z-index: 2147483646;
        width: max-content; max-width: min(86vw, 980px); box-sizing: border-box; padding: 8px 14px 10px; border-radius: 12px;
        background: rgba(8, 8, 12, .8); color: #fff; text-align: center; font: 500 22px/1.4 "Segoe UI", system-ui, sans-serif;
        user-select: text; cursor: default; }
      #lumina-tab-captions[hidden], #lumina-tab-captions [hidden] { display: none; }
      #lumina-tab-captions { min-width: 260px; }
      #lumina-tab-captions .lumina-bar { position: absolute; left: 50%; transform: translateX(-50%); bottom: 100%; padding-bottom: 4px;
        width: max-content; white-space: nowrap; display: flex; gap: 4px; opacity: 0; pointer-events: none; transition: opacity .15s; }
      #lumina-tab-captions:hover .lumina-bar { opacity: 1; pointer-events: auto; }
      #lumina-tab-captions .lumina-bar button { all: unset; cursor: pointer; font: 600 11px/1 "Segoe UI", system-ui, sans-serif;
        padding: 4px 8px; border-radius: 999px; background: rgba(15,15,20,.85); color: #fff; }
      #lumina-tab-captions .lumina-bar button[aria-pressed="true"] { background: #4f46e5; }
      #lumina-tab-captions .lumina-en { display: block; }
      #lumina-tab-captions .lumina-vi { display: block; color: #6ee7b7; font-size: 19px; margin-top: 2px; }
      #lumina-tab-captions .lumina-hint { display: block; font-size: 14px; color: #fde68a; }
      #lumina-tab-captions.pending .lumina-en { opacity: .65; }
    `;
    document.documentElement.appendChild(style);
  }

  const overlay = document.createElement("div");
  overlay.id = "lumina-tab-captions";
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
  viLine.setAttribute("data-lumina-skip-lookup", ""); // dòng Việt không đi qua tra từ tiếng Anh
  const hint = document.createElement("span");
  hint.className = "lumina-hint";
  hint.setAttribute("data-lumina-skip-lookup", "");
  overlay.append(bar, enLine, viLine, hint);

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
    // Chế độ Tiếng Việt: chưa có bản dịch thì vẫn hiện dòng tiếng Anh để khung không biến mất.
    const showEn = (mode !== "vi" || !view.vi) && Boolean(view.en);
    const showVi = mode !== "en" && Boolean(view.vi);
    enLine.textContent = showEn ? view.en : "";
    enLine.hidden = !showEn;
    viLine.textContent = showVi ? view.vi : "";
    viLine.hidden = !showVi;
    hint.textContent = view.hint;
    hint.hidden = !view.hint;
    overlay.classList.toggle("pending", !view.final);
    overlay.hidden = !(showEn || showVi || view.hint);
    if (!overlay.isConnected) document.documentElement.appendChild(overlay);
  }

  function scheduleClear() {
    clearTimeout(clearTimer);
    clearTimer = setTimeout(() => {
      view.en = view.vi = "";
      render();
    }, CLEAR_AFTER_MS);
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === "TAB_CAPTION") {
      const { text, translation, final } = message.caption;
      view.en = text || "";
      view.vi = translation || "";
      view.final = final !== false;
      view.hint = "";
      scheduleClear();
      render();
    } else if (message?.type === "TAB_STATUS") {
      const key = message.state === "error" ? message.code : message.fellBack ? "fellBack" : message.state;
      if (message.state === "closed") {
        // Socket lỗi báo "error" rồi gần như cùng lúc báo "closed": đừng để "closed" xoá mất thông báo lỗi.
        view.en = view.vi = "";
        if (!view.hintIsError) view.hint = "";
      } else {
        view.hint = STATUS_TEXT[key] ?? "";
        view.hintIsError = message.state === "error";
        if (message.state === "ready") setTimeout(() => ((view.hint = ""), render()), 6000);
        if (message.state === "error") {
          setTimeout(() => {
            if (!view.hintIsError) return;
            view.hint = "";
            view.hintIsError = false;
            render();
          }, 12000);
        }
      }
      render();
    }
  });

  chrome.storage.local.get("captionMode").then((data) => {
    if (MODES.some(([value]) => value === data.captionMode)) mode = data.captionMode;
    render();
  });
  chrome.storage.onChanged.addListener((changes) => {
    if (changes.captionMode && MODES.some(([value]) => value === changes.captionMode.newValue)) {
      mode = changes.captionMode.newValue;
      render(true);
    }
  });
})();
