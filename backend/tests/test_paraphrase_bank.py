from fastapi.testclient import TestClient

from app.services import paraphrase_service
from tests.test_vocab_integration import login, vocab_client  # noqa: F401  (fixture)


def test_similarity_flags_copy_but_not_passive_or_synonyms() -> None:
	original = "The government should reduce taxes."
	assert paraphrase_service.similarity(original, original) == 1.0
	assert paraphrase_service.similarity(original, "Taxes should be reduced by the government.") < 0.75
	assert paraphrase_service.similarity(original, "The state ought to cut levies.") < 0.75


def test_every_model_answer_passes_its_own_check() -> None:
	for item in paraphrase_service.list_bank(None):
		for model in paraphrase_service.check_attempt(item["id"], "x y z")["model_paraphrases"]:
			assert not paraphrase_service.check_attempt(item["id"], model)["too_similar"], item["original"]


def test_paraphrase_bank_endpoints(vocab_client: TestClient) -> None:
	headers = login(vocab_client)
	items = vocab_client.get("/api/writing/paraphrase-bank?technique=voice", headers=headers).json()
	assert items and {i["technique"] for i in items} == {"voice"}
	assert vocab_client.get("/api/writing/paraphrase-bank?technique=nope", headers=headers).status_code == 422

	copy = vocab_client.post(
		f"/api/writing/paraphrase-bank/{items[0]['id']}/check", headers=headers, json={"text": items[0]["original"]}
	).json()
	assert copy["too_similar"] and copy["model_paraphrases"]
	assert vocab_client.post("/api/writing/paraphrase-bank/999/check", headers=headers, json={"text": "abc def"}).status_code == 404
