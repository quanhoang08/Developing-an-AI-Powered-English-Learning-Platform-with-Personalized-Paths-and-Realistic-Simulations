from fastapi.testclient import TestClient

from app.services import grammar_service
from app.services.vi_contrast import CONTRAST
from tests.test_vocab_integration import login, vocab_client  # noqa: F401  (fixture)


def test_grammar_placement_covers_topics_and_grades_on_server(vocab_client: TestClient) -> None:
	headers = login(vocab_client)
	quiz = vocab_client.get("/api/grammar/quiz?count=12", headers=headers).json()
	assert len(quiz) == 12 and {q["topic"] for q in quiz} == set(grammar_service.TOPICS)
	assert all(len(q["options"]) == 4 for q in quiz) and "correct_answer" not in quiz[0]

	only = vocab_client.get("/api/grammar/quiz?topic=articles&count=6", headers=headers).json()
	assert len(only) == 6 and {q["topic"] for q in only} == {"articles"}

	right = lambda q: grammar_service._BANK[int(q["question_id"])][2][0]  # noqa: E731
	answers = [{"question_id": q["question_id"], "choice": right(q)} for q in quiz]
	answers[0]["choice"] = [o for o in quiz[0]["options"] if o != right(quiz[0])][0]
	result = vocab_client.post("/api/grammar/submit", headers=headers, json={"answers": answers}).json()
	assert (result["score"], result["total"]) == (11, 12)
	assert result["by_topic"][quiz[0]["topic"]]["correct"] == 1 and sum(t["total"] for t in result["by_topic"].values()) == 12

	assert result["previous_by_topic"] is None
	wrong = next(r for r in result["results"] if not r["is_correct"])
	assert wrong["why_chosen_vi"] in grammar_service._WHY[int(wrong["question_id"])]
	assert wrong["contrast_vi"] and wrong["contrast_vi"] == CONTRAST[wrong["topic"]]
	# Lượt 2 (cùng phạm vi trộn) so sánh được với lượt 1; lịch sử có 2 lượt; bài hằng ngày chọn chủ điểm yếu nhất.
	again = vocab_client.post("/api/grammar/submit", headers=headers, json={"answers": answers}).json()
	assert again["previous_by_topic"] == result["by_topic"]
	assert len(vocab_client.get("/api/grammar/attempts", headers=headers).json()) == 2
	daily = vocab_client.get("/api/grammar/daily", headers=headers).json()
	assert daily["topic"] == quiz[0]["topic"] and len(daily["questions"]) == 6

	errors = vocab_client.get("/api/adaptive/errors?error_type=grammar", headers=headers).json()
	assert {e["detail"]["source"] for e in errors} == {"grammar_bank"}

	bad = vocab_client.post("/api/grammar/submit", headers=headers, json={"answers": [{"question_id": "0", "choice": "zzz"}]})
	assert bad.status_code == 422
