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

async function render() {
  const [{ loggedIn, email, apiBaseUrl }, stored] = await Promise.all([
    send({ type: "AUTH_STATUS" }),
    chrome.storage.local.get("enabled"),
  ]);
  $("enabled").checked = stored.enabled !== false;
  $("loggedIn").hidden = !loggedIn;
  $("loggedOut").hidden = loggedIn;
  $("whoami").textContent = email || "";
  $("apiBaseUrl").value = apiBaseUrl || "";
}

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

$("logoutBtn").addEventListener("click", async () => {
  await send({ type: "LOGOUT" });
  setStatus("Đã đăng xuất.");
  await render();
});

render().catch((error) => setStatus(error.message, "error"));
