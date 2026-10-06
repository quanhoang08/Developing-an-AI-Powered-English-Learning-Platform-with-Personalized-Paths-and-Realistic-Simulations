from fastapi.testclient import TestClient

from app.services import llm_service
from tests.test_vocab_integration import login, vocab_client  # noqa: F401  (fixture)


def test_adapt_text_returns_bilingual_sentences(vocab_client: TestClient, monkeypatch) -> None:
	seen: dict = {}

	async def fake_adapt(text: str, level: str) -> list[dict]:
		seen["level"] = level
		return [{"en": "Cats sleep a lot.", "vi": "Mèo ngủ rất nhiều."}]

	monkeypatch.setattr(llm_service, "adapt_text_level", fake_adapt)
	headers = login(vocab_client)
	body = {"text": "Felines exhibit a pronounced propensity for prolonged slumber.", "level": "A2"}
	result = vocab_client.post("/api/reading/adapt", headers=headers, json=body).json()
	assert seen["level"] == "A2" and result["sentences"][0]["vi"].startswith("Mèo")

	assert vocab_client.post("/api/reading/adapt", headers=headers, json={"text": "short"}).status_code == 422
	assert vocab_client.post("/api/reading/adapt", json=body).status_code in (401, 403)
