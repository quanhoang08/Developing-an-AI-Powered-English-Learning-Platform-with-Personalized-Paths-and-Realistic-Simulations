// Side panel: kiểm tra ngữ pháp / dịch câu mà không cần chuyển tab. Mọi gọi API đi qua background.js (đã đăng nhập ở popup).
const $ = (id) => document.getElementById(id);

async function send(message) {
  const response = await chrome.runtime.sendMessage(message);
  if (!response?.ok) throw new Error(response?.error || "unknown_error");
  return response.data;
}

async function run(button, work) {
  const text = $("text").value.trim();
  if (!text) return;
  button.disabled = true;
  $("status").textContent = "Đang xử lý...";
  $("issues").replaceChildren();
  $("out").textContent = "";
  try {
    await work(text);
    $("status").textContent = "";
  } catch (error) {
    $("status").textContent = error.message === "not_logged_in" ? "Hãy đăng nhập ở popup của extension." : `Lỗi: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

$("grammar").addEventListener("click", (event) =>
  run(event.target, async (text) => {
    const result = await send({ type: "GRAMMAR_CHECK", text });
    if (!result.insights.length) {
      $("out").textContent = "Không thấy lỗi ngữ pháp.";
      return;
    }
    for (const item of result.insights) {
      const li = document.createElement("li");
      const wrong = document.createElement("s");
      wrong.textContent = item.original_text;
      const right = document.createElement("b");
      right.textContent = item.suggested_text;
      li.append(wrong, " → ", right, item.explanation ? ` (${item.explanation})` : "");
      $("issues").append(li);
    }
  }),
);

$("translate").addEventListener("click", (event) =>
  run(event.target, async (text) => {
    $("out").textContent = (await send({ type: "TRANSLATE", text })) || "Chưa dịch được.";
  }),
);
