from fastapi.testclient import TestClient

from app.services import confusable_service
from tests.test_vocab_integration import login, vocab_client  # noqa: F401  (fixture)


def test_confusable_quiz_grades_on_server_and_records_errors(vocab_client: TestClient) -> None:
	headers = login(vocab_client)
	quiz = vocab_client.get("/api/vocab/confusables/quiz?count=14", headers=headers).json()
	assert len(quiz) == 14 and len({q["question_id"] for q in quiz}) == 14
	assert all("___" in q["sentence"] and len(q["options"]) == 2 for q in quiz)
	assert "correct_answer" not in quiz[0]

	def right(question_id: str) -> str:
		pair, item = (int(x) for x in question_id.split("."))
		return confusable_service._PAIRS[pair][3][item][1]

	# Đúng 13 câu, cố tình sai câu cuối bằng từ còn lại của cặp.
	answers = [{"question_id": q["question_id"], "choice": right(q["question_id"])} for q in quiz]
	answers[-1]["choice"] = [o for o in quiz[-1]["options"] if o != answers[-1]["choice"]][0]
	result = vocab_client.post("/api/vocab/confusables/submit", headers=headers, json={"answers": answers}).json()
	assert (result["score"], result["total"]) == (13, 14)
	assert [r["is_correct"] for r in result["results"]].count(False) == 1
	wrong = next(r for r in result["results"] if not r["is_correct"])
	assert wrong["contrast_vi"] and next(r for r in result["results"] if r["is_correct"])["contrast_vi"] is None

	errors = vocab_client.get("/api/adaptive/errors?error_type=vocabulary", headers=headers).json()
	assert [e["detail"]["source"] for e in errors] == ["confusable_pair"]

	bad = vocab_client.post(
		"/api/vocab/confusables/submit", headers=headers, json={"answers": [{"question_id": "0.0", "choice": "zzz"}]}
	)
	assert bad.status_code == 422
