from fastapi.testclient import TestClient

from app.services import reading_service, wordlist_service
from tests.test_vocab_integration import login, vocab_client  # noqa: F401  (fixture)


def test_lists_load_and_text_coverage() -> None:
	nawl_heads, nawl_forms = wordlist_service._load("nawl")
	tsl_heads, _ = wordlist_service._load("tsl")
	assert len(nawl_heads) > 900 and len(tsl_heads) > 1200
	# Dạng biến thể trỏ về từ gốc: "absorbing" -> "absorb".
	assert nawl_forms["absorbing"] == "absorb"
	result = wordlist_service.text_coverage("nawl", "The cat will absorb absorption.")
	assert result["tokens"] == 5 and result["words_found"] == ["absorb", "absorption"] and result["percent"] == 40.0
	assert wordlist_service.text_coverage("tsl", "")["percent"] == 0.0


def test_coverage_counts_saved_words_and_add(vocab_client: TestClient, monkeypatch) -> None:
	async def fake_lookup(term: str, context: str) -> dict:
		return {"definition": f"nghĩa của {term}", "ipa": None, "example_sentence": "", "synonyms": [], "antonyms": []}

	monkeypatch.setattr(reading_service, "lookup_term", fake_lookup)
	headers = login(vocab_client)
	url = "/api/vocab/wordlists/nawl"
	before = vocab_client.get(f"{url}/coverage", headers=headers).json()
	assert before["known"] == 0 and len(before["suggestions"]) == 8

	# "zzzz" không thuộc danh sách nên bị bỏ; "Absorb" trùng "absorb" nên chỉ thêm một lần.
	added = vocab_client.post(f"{url}/add", headers=headers, json={"words": ["absorb", "zzzz", "Absorb"]}).json()
	assert [v["term"] for v in added] == ["absorb"]
	after = vocab_client.get(f"{url}/coverage", headers=headers).json()
	assert after["known"] == 1 and "absorb" not in after["suggestions"]

	assert vocab_client.get("/api/vocab/wordlists/xyz/coverage", headers=headers).status_code == 422
