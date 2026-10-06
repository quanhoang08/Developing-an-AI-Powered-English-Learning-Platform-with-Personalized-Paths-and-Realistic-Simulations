from fastapi.testclient import TestClient

from tests.test_vocab_integration import login, vocab_client  # noqa: F401  (fixture)


def test_mnemonic_reports_hide_after_threshold(vocab_client: TestClient) -> None:
	author, r1, r2, r3, viewer = (login(vocab_client) for _ in range(5))
	term = "Ephemeral-" + author["Authorization"][-8:]
	vocab_client.post("/api/vocab/mnemonics", headers=author, json={"term": term, "text": "e-phe-me-ral: thoáng qua"})
	mid = vocab_client.get("/api/vocab/mnemonics", headers=viewer, params={"term": term}).json()[0]["id"]

	def listing(headers):
		return vocab_client.get("/api/vocab/mnemonics", headers=headers, params={"term": term}).json()

	assert vocab_client.post(f"/api/vocab/mnemonics/{mid}/report", headers=author).status_code >= 400  # không tự báo cáo
	for reporter in (r1, r1, r2):  # báo cáo lặp của cùng 1 người chỉ tính 1
		assert vocab_client.post(f"/api/vocab/mnemonics/{mid}/report", headers=reporter).status_code == 204
	assert len(listing(viewer)) == 1  # mới 2 người báo cáo: còn hiện
	assert listing(r1) == []  # người báo cáo không thấy lại mẹo
	assert vocab_client.post(f"/api/vocab/mnemonics/{mid}/report", headers=r3).status_code == 204
	assert listing(viewer) == []  # đủ 3 người: ẩn với người khác
	assert len(listing(author)) == 1  # chủ mẹo vẫn thấy mẹo của mình


def test_mnemonics_share_vote_and_ownership(vocab_client: TestClient) -> None:
	a, b = login(vocab_client), login(vocab_client)
	term = "Ubiquitous-" + a["Authorization"][-8:]
	assert vocab_client.post("/api/vocab/mnemonics", headers=a, json={"term": term, "text": "u-bi-qui-tous: ở đâu cũng có"}).status_code == 204
	# Gửi lại thì thay nội dung, không tạo bản thứ hai; tra từ không phân biệt hoa/thường.
	vocab_client.post("/api/vocab/mnemonics", headers=a, json={"term": term, "text": "ở đâu cũng thấy, như mạng xã hội"})
	listing = vocab_client.get("/api/vocab/mnemonics", headers=b, params={"term": term.upper()}).json()
	assert [m["text"] for m in listing] == ["ở đâu cũng thấy, như mạng xã hội"] and listing[0]["is_mine"] is False
	mid = listing[0]["id"]

	assert vocab_client.post(f"/api/vocab/mnemonics/{mid}/vote", headers=a).status_code == 409  # không tự bầu
	assert vocab_client.post(f"/api/vocab/mnemonics/{mid}/vote", headers=b).json() == {"voted": True}
	item = vocab_client.get("/api/vocab/mnemonics", headers=b, params={"term": term}).json()[0]
	assert (item["votes"], item["voted"]) == (1, True)
	assert vocab_client.post(f"/api/vocab/mnemonics/{mid}/vote", headers=b).json() == {"voted": False}

	assert vocab_client.delete(f"/api/vocab/mnemonics/{mid}", headers=b).status_code == 404  # không xóa của người khác
	assert vocab_client.delete(f"/api/vocab/mnemonics/{mid}", headers=a).status_code == 204
	assert vocab_client.get("/api/vocab/mnemonics", headers=a, params={"term": term}).json() == []
