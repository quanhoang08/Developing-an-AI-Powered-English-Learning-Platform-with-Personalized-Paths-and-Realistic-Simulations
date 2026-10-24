import asyncio
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from tests.test_vocab_integration import login, vocab_client  # noqa: F401  (fixture)


def _sql(statement: str, **params) -> None:
	async def run() -> None:
		engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
		async with engine.begin() as conn:
			await conn.execute(text(statement), params)
		await engine.dispose()

	asyncio.run(run())


def _uid(client: TestClient, headers: dict) -> str:
	return client.get("/api/users/me", headers=headers).json()["id"]


def test_xp_pays_coins_and_booster_doubles_xp(vocab_client: TestClient) -> None:
	headers = login(vocab_client)
	uid = _uid(vocab_client, headers)
	vocab_client.post("/api/games/memory-match/complete", headers=headers, json={"pairs": 6, "moves": 9})  # 8 XP -> 4 xu
	assert vocab_client.get("/api/economy/wallet", headers=headers).json()["coins"] == 4

	_sql("UPDATE wallets SET coins = 500 WHERE user_id = :u", u=uid)
	assert vocab_client.post("/api/economy/shop/booster_2x/buy", headers=headers).json() == {"coins": 400}
	assert vocab_client.get("/api/economy/wallet", headers=headers).json()["booster_seconds_left"] > 3500
	vocab_client.post("/api/games/memory-match/complete", headers=headers, json={"pairs": 6, "moves": 9})  # 8 -> 16 XP
	assert vocab_client.get("/api/streaks", headers=headers).json()["total_xp"] == 8 + 16


def test_shop_equip_and_errors(vocab_client: TestClient) -> None:
	headers = login(vocab_client)
	uid = _uid(vocab_client, headers)
	vocab_client.get("/api/economy/wallet", headers=headers)
	assert vocab_client.post("/api/economy/shop/avatar_fox/buy", headers=headers).status_code == 409  # không đủ xu
	_sql("UPDATE wallets SET coins = 300 WHERE user_id = :u", u=uid)
	assert vocab_client.post("/api/economy/shop/avatar_fox/buy", headers=headers).json() == {"coins": 240}
	assert vocab_client.post("/api/economy/shop/avatar_fox/buy", headers=headers).status_code == 409  # đã sở hữu
	assert vocab_client.post("/api/economy/shop/nope/buy", headers=headers).status_code == 404
	assert vocab_client.post("/api/economy/items/avatar_panda/equip", headers=headers).status_code == 404  # chưa có
	assert vocab_client.post("/api/economy/items/avatar_fox/equip", headers=headers).status_code == 204
	shop = {i["id"]: i for i in vocab_client.get("/api/economy/wallet", headers=headers).json()["shop"]}
	assert shop["avatar_fox"]["owned"] and shop["avatar_fox"]["equipped"] and not shop["avatar_panda"]["owned"]


def test_hearts_lose_regen_and_refill(vocab_client: TestClient) -> None:
	headers = login(vocab_client)
	uid = _uid(vocab_client, headers)
	assert vocab_client.get("/api/economy/wallet", headers=headers).json()["hearts"] == 5
	assert vocab_client.post("/api/economy/hearts/lose", headers=headers).json() == {"hearts": 4}
	assert vocab_client.post("/api/economy/hearts/lose", headers=headers).json() == {"hearts": 3}
	assert vocab_client.post("/api/economy/hearts/refill", headers=headers).status_code == 409  # không đủ xu
	# 70 phút trước = hồi 2 tim (30 phút/tim).
	_sql("UPDATE wallets SET hearts_updated_at = :t WHERE user_id = :u", u=uid, t=datetime.now(timezone.utc) - timedelta(minutes=70))
	wallet = vocab_client.get("/api/economy/wallet", headers=headers).json()
	assert wallet["hearts"] == 5 and wallet["next_heart_in_seconds"] is None
	vocab_client.post("/api/economy/hearts/lose", headers=headers)
	_sql("UPDATE wallets SET coins = 30 WHERE user_id = :u", u=uid)
	assert vocab_client.post("/api/economy/hearts/refill", headers=headers).json() == {"hearts": 5, "coins": 10}
	assert vocab_client.post("/api/economy/hearts/refill", headers=headers).status_code == 409  # đã đầy


def test_gacha_cost_rewards_and_duplicate_refund(vocab_client: TestClient, monkeypatch) -> None:
	from app.services import economy_service

	headers = login(vocab_client)
	uid = _uid(vocab_client, headers)
	vocab_client.get("/api/economy/wallet", headers=headers)
	assert vocab_client.post("/api/economy/gacha", headers=headers).status_code == 409  # không đủ xu
	_sql("UPDATE wallets SET coins = 1000 WHERE user_id = :u", u=uid)

	# Cố định kết quả quay: lần 1 ra avatar_fox, lần 2 trùng -> hoàn 30 xu.
	monkeypatch.setattr(economy_service.random, "choices", lambda population, weights: [{"item": "avatar_fox"}])
	first = vocab_client.post("/api/economy/gacha", headers=headers).json()
	assert first["reward"] == {"item": "avatar_fox"} and not first["duplicate"] and first["coins"] == 950
	second = vocab_client.post("/api/economy/gacha", headers=headers).json()
	assert second["duplicate"] and second["coins"] == 950 - 50 + 30

	# Bảng quà hợp lệ: tổng trọng số 100, phần thưởng item đều có trong shop.
	assert sum(w for w, _ in economy_service.LOOT) == 100
	assert all(r["item"] in economy_service.SHOP for _, r in economy_service.LOOT if "item" in r)


def test_guild_lifecycle_and_leaderboard(vocab_client: TestClient) -> None:
	owner = login(vocab_client)
	assert vocab_client.get("/api/guilds/me", headers=owner).json() is None
	assert vocab_client.post("/api/guilds", headers=owner, json={"name": "ab"}).status_code == 409  # tên quá ngắn
	guild = vocab_client.post("/api/guilds", headers=owner, json={"name": "Night Owls"}).json()
	assert guild["name"] == "Night Owls" and len(guild["join_code"]) == 6 and guild["members"][0]["is_owner"]
	assert vocab_client.post("/api/guilds", headers=owner, json={"name": "Another"}).status_code == 409

	vocab_client.post("/api/games/memory-match/complete", headers=owner, json={"pairs": 6, "moves": 9})
	members = [login(vocab_client) for _ in range(4)]
	for headers in members:
		assert vocab_client.post("/api/guilds/join", headers=headers, json={"code": guild["join_code"].lower()}).status_code == 200
	late = login(vocab_client)
	assert vocab_client.post("/api/guilds/join", headers=late, json={"code": guild["join_code"]}).status_code == 409  # đầy 5
	assert vocab_client.post("/api/guilds/join", headers=late, json={"code": "ZZZZZZ"}).status_code == 404
	assert vocab_client.post("/api/guilds/join", headers=members[0], json={"code": guild["join_code"]}).status_code == 409  # đã trong bang

	mine = vocab_client.get("/api/guilds/me", headers=owner).json()
	assert len(mine["members"]) == 5 and mine["weekly_xp"] >= 8 and mine["members"][0]["weekly_xp"] >= 8
	board = vocab_client.get("/api/guilds/leaderboard", headers=owner).json()
	assert any(row["name"] == "Night Owls" and row["is_mine"] and row["members"] == 5 for row in board)

	# Chủ rời bang -> quyền chuyển cho thành viên vào sớm nhất; người cuối rời -> bang bị xoá.
	assert vocab_client.post("/api/guilds/leave", headers=owner).status_code == 204
	assert vocab_client.post("/api/guilds/leave", headers=owner).status_code == 404
	now_owner = vocab_client.get("/api/guilds/me", headers=members[0]).json()
	assert now_owner["members"] and any(m["is_owner"] for m in now_owner["members"])
	for headers in members:
		vocab_client.post("/api/guilds/leave", headers=headers)
	assert vocab_client.get("/api/guilds/me", headers=members[0]).json() is None
	assert vocab_client.post("/api/guilds/join", headers=late, json={"code": guild["join_code"]}).status_code == 404
