import io

from fastapi.testclient import TestClient

from app.services import llm_service, pronunciation_service as ps, speech_service
from tests.test_vocab_integration import login, vocab_client  # noqa: F401  (fixture)


def test_word_tips_and_bank() -> None:
	assert "th" in ps.word_tips("thanks") and "ed" in ps.word_tips("asked")
	assert "cluster" in ps.word_tips("street") and "stress" in ps.word_tips("photographer")
	assert all(f in ps.FOCUS_TIPS for _, f, _ in ps.SENTENCES)
	fb = ps.build_feedback([("think", 40.0), ("the", 95.0)], "th")
	assert [f["word"] for f in fb] == ["think"]


def test_pairs_round_trip() -> None:
	quiz = ps.pairs_quiz(5)
	assert len(quiz) == 5 and all(q["speak"] in q["options"] for q in quiz)
	res = ps.pairs_check([{"id": q["id"], "choice": q["speak"]} for q in quiz])
	assert res["correct"] == 5
	wrong = ps.pairs_check([{"id": quiz[0]["id"], "choice": "zzz"}])
	assert wrong["correct"] == 0 and wrong["results"][0]["note_vi"]


def test_assess_and_silent(vocab_client: TestClient, monkeypatch) -> None:
	def fake(path, locale, ref):
		assert ref == ps.sentence_text("t1")
		return speech_service.PronunciationResult(
			score=70, accuracy=70, fluency=80, completeness=100, weak_words=["Thank"], words=[("Thank", 50.0), ("you", 90.0)]
		)

	monkeypatch.setattr(speech_service, "assess_pronunciation", fake)

	async def fake_judge(question, answer):
		return "fox" not in answer

	monkeypatch.setattr(llm_service, "judge_silent_answer", fake_judge)
	h = login(vocab_client)
	wav = {"audio": ("a.wav", io.BytesIO(b"x"), "audio/wav")}
	r = vocab_client.post("/api/pronunciation/sentences/t1/assess", headers=h, files=wav)
	body = r.json()
	assert r.status_code == 200 and body["weak_words"][0]["word"] == "Thank" and body["weak_words"][0]["tips_vi"]
	wav = {"audio": ("a.wav", io.BytesIO(b"x"), "audio/wav")}
	assert vocab_client.post("/api/pronunciation/sentences/zz/assess", headers=h, files=wav).status_code == 404
	assert vocab_client.post("/api/pronunciation/silent", headers=h, json={"prompt_id": 0, "text": "too short"}).status_code == 422
	off = vocab_client.post("/api/pronunciation/silent", headers=h, json={"prompt_id": 0, "text": "The quick brown fox jumps over the lazy dog today."})
	assert off.status_code == 422 and off.json()["detail"] == "answer_off_topic"
	ok = vocab_client.post("/api/pronunciation/silent", headers=h, json={"prompt_id": 0, "text": "This morning I woke up early and drank some coffee."})
	assert ok.status_code == 200 and ok.json()["xp"] == 3
	body = {"prompt_id": 0, "text": "This morning I woke up early and drank some coffee."}
	xps = [vocab_client.post("/api/pronunciation/silent", headers=h, json=body).json()["xp"] for _ in range(5)]
	assert xps == [3, 3, 3, 3, 0]  # lần thứ 6 trong ngày: hết XP
