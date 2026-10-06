from fastapi.testclient import TestClient

from app.services import reading_service
from app.services.vocab_service import parse_unit_line
from tests.test_vocab_integration import login, vocab_client  # noqa: F401  (fixture)


def test_parse_unit_line() -> None:
	assert parse_unit_line("apple - quả táo") == ("apple", "quả táo")
	assert parse_unit_line("apple: quả táo") == ("apple", "quả táo")
	assert parse_unit_line("apple\tquả táo") == ("apple", "quả táo")
	assert parse_unit_line("ice-cream = kem") == ("ice-cream", "kem")
	assert parse_unit_line("apple") == ("apple", None)


def test_import_unit(vocab_client: TestClient, monkeypatch) -> None:
	async def fake_lookup(term: str, context: str) -> dict:
		return {"definition": f"nghĩa của {term}", "ipa": None, "example_sentence": "", "synonyms": [], "antonyms": []}

	monkeypatch.setattr(reading_service, "lookup_term", fake_lookup)
	headers = login(vocab_client)
	lines = ["apple - quả táo", "Apple: lặp", "bread", "123", ""] + [f"w{c}" for c in "abcdefg"]
	body = vocab_client.post("/api/vocab/import-unit", headers=headers, json={"lines": lines}).json()
	# "Apple" lặp trong cùng lần gửi bị bỏ; "123" không hợp lệ; "w..." chứa chữ số? không, nên hợp lệ.
	terms = [v["term"] for v in body["created"]]
	assert terms[:2] == ["apple", "bread"] and body["created"][0]["definition"] == "quả táo"
	assert body["invalid"] == ["123"]
	# 5 lượt tra tối đa: bread + 4 từ w*, 3 từ còn lại để gửi lại.
	assert len(terms) == 6 and len(body["skipped_no_definition"]) == 3
	again = vocab_client.post("/api/vocab/import-unit", headers=headers, json={"lines": ["apple - x"]}).json()
	assert again["duplicates"] == ["apple"] and again["created"] == []


def test_unit_label_and_listing(vocab_client: TestClient) -> None:
	headers = login(vocab_client)
	body = vocab_client.post(
		"/api/vocab/import-unit", headers=headers, json={"lines": ["tide - thủy triều", "reef: rạn san hô"], "unit": "Unit 3"}
	).json()
	assert len(body["created"]) == 2
	assert vocab_client.get("/api/vocab/units", headers=headers).json() == [{"unit": "Unit 3", "count": 2}]
	words = vocab_client.get("/api/vocab/units/words", params={"unit": "Unit 3"}, headers=headers).json()
	assert [w["term"] for w in words] == ["reef", "tide"]
