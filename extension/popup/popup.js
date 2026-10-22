const $ = (id) => document.getElementById(id);
const statusNode = $("status");

function setStatus(message, type) {
  statusNode.textContent = message || "";
  statusNode.classList.remove("ok", "error");
  if (type) statusNode.classList.add(type);
}

async function send(message) {
  const response = await chrome.runtime.sendMessage(message);
  if (!response?.ok) throw new Error(response?.error || "unknown_error");
  return response.data;
}

const LOGIN_ERRORS = {
  invalid_credentials: "Email hoặc mật khẩu không đúng.",
};

// Phụ đề từ âm thanh của tab đang mở: nút bật/tắt cho đúng tab hiện tại.
const currentTabId = async () => (await chrome.tabs.query({ active: true, currentWindow: true }))[0]?.id;

async function refreshTabCaptionButton() {
  const tabId = await currentTabId();
  const active = tabId !== undefined && (await send({ type: "TAB_CAPTION_STATE", tabId }));
  $("tabCaptionBtn").textContent = active ? "Tắt phụ đề của tab này" : "Bật phụ đề cho tab này (nghe âm thanh)";
  $("tabCaptionBtn").dataset.active = String(active);
}

async function render() {
  const [{ loggedIn, email, apiBaseUrl }, stored] = await Promise.all([
    send({ type: "AUTH_STATUS" }),
    chrome.storage.local.get("enabled"),
  ]);
  $("enabled").checked = stored.enabled !== false;
  $("loggedIn").hidden = !loggedIn;
  $("tabCaptions").hidden = !loggedIn;
  if (loggedIn) await refreshTabCaptionButton();
  $("loggedOut").hidden = loggedIn;
  $("whoami").textContent = email || "";
  $("apiBaseUrl").value = apiBaseUrl || "";
}

chrome.storage.local.get("captionOverlay").then((stored) => {
  $("captionOverlay").checked = stored.captionOverlay !== false;
});
$("captionOverlay").addEventListener("change", (event) => {
  chrome.storage.local.set({ captionOverlay: event.target.checked });
});

$("enabled").addEventListener("change", (event) => {
  chrome.storage.local.set({ enabled: event.target.checked });
});

$("loginBtn").addEventListener("click", async () => {
  const email = $("email").value.trim();
  const password = $("password").value;
  if (!email || !password) {
    setStatus("Nhập email và mật khẩu.", "error");
    return;
  }
  setStatus("Đang đăng nhập…");
  try {
    await send({ type: "LOGIN", email, password, apiBaseUrl: $("apiBaseUrl").value.trim() });
    $("password").value = "";
    setStatus("Đăng nhập thành công.", "ok");
    await render();
  } catch (error) {
    setStatus(LOGIN_ERRORS[error.message] || `Đăng nhập thất bại: ${error.message}`, "error");
  }
});

const TAB_CAPTION_ERRORS = {
  not_logged_in: "Hãy đăng nhập trước.",
};

$("tabCaptionBtn").addEventListener("click", async () => {
  try {
    if ($("tabCaptionBtn").dataset.active === "true") {
      await send({ type: "STOP_TAB_CAPTIONS" });
      setStatus("Đã tắt phụ đề của tab.");
    } else {
      const tabId = await currentTabId();
      if (tabId === undefined) throw new Error("no_tab");
      await send({ type: "START_TAB_CAPTIONS", tabId });
      setStatus("Đang bật phụ đề: nghe âm thanh của tab này…", "ok");
    }
    await refreshTabCaptionButton();
  } catch (error) {
    setStatus(TAB_CAPTION_ERRORS[error.message] || `Không bật được phụ đề: ${error.message}`, "error");
  }
});

$("logoutBtn").addEventListener("click", async () => {
  await send({ type: "LOGOUT" });
  setStatus("Đã đăng xuất.");
  await render();
});

render().catch((error) => setStatus(error.message, "error"));
