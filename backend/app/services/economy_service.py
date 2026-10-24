"""Coins & Shop, Gacha, Hearts, 2x XP booster (tài liệu tính năng mục VIII + hệ thống tim mục I.3).

Xu kiếm từ XP (mỗi 2 XP = 1 xu, tính trong gamification_service.award_activity qua `boost_and_pay`). Tim hồi lười theo
thời gian, không cần job nền. Danh mục shop và bảng quà gacha nằm trong code (không bảng catalog).
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.economy import UserItem, Wallet

HEART_MAX = 5
HEART_REGEN = timedelta(minutes=30)
HEART_REFILL_COST = 20
GACHA_COST = 50
DUPLICATE_REFUND = 30
BOOSTER_DURATION = timedelta(hours=1)
XP_PER_COIN = 2

SHOP: dict[str, dict] = {
	"avatar_fox": {"name": "Fox avatar", "slot": "avatar", "price": 60, "emoji": "🦊"},
	"avatar_panda": {"name": "Panda avatar", "slot": "avatar", "price": 80, "emoji": "🐼"},
	"avatar_robot": {"name": "Robot avatar", "slot": "avatar", "price": 100, "emoji": "🤖"},
	"avatar_dragon": {"name": "Dragon avatar", "slot": "avatar", "price": 200, "emoji": "🐲"},
	"frame_gold": {"name": "Gold frame", "slot": "frame", "price": 120, "emoji": "🟡"},
	"frame_neon": {"name": "Neon frame", "slot": "frame", "price": 150, "emoji": "🟣"},
	"booster_2x": {"name": "2x XP booster (1 hour)", "slot": "booster", "price": 100, "emoji": "⚡"},
}

# (trọng số, phần thưởng): tổng 100.
LOOT: list[tuple[int, dict]] = [
	(30, {"coins": 20}),
	(20, {"coins": 60}),
	(20, {"booster": True}),
	(10, {"item": "avatar_fox"}),
	(5, {"item": "avatar_panda"}),
	(5, {"item": "avatar_robot"}),
	(5, {"item": "frame_gold"}),
	(3, {"item": "frame_neon"}),
	(2, {"item": "avatar_dragon"}),
]


def _now() -> datetime:
	return datetime.now(timezone.utc)


async def get_wallet(db: AsyncSession, user_id: uuid.UUID, now: datetime | None = None) -> Wallet:
	"""Ví đã khoá dòng + áp hồi tim; tạo dòng nếu chưa có. KHÔNG commit."""
	now = now or _now()
	await db.execute(pg_insert(Wallet).values(user_id=user_id).on_conflict_do_nothing(index_elements=["user_id"]))
	wallet = await db.scalar(select(Wallet).where(Wallet.user_id == user_id).with_for_update())
	if wallet.hearts < HEART_MAX:
		gained = int((now - wallet.hearts_updated_at) / HEART_REGEN)
		if gained > 0:
			wallet.hearts = min(HEART_MAX, wallet.hearts + gained)
			wallet.hearts_updated_at = now if wallet.hearts == HEART_MAX else wallet.hearts_updated_at + gained * HEART_REGEN
	else:
		wallet.hearts_updated_at = now
	return wallet


async def boost_and_pay(db: AsyncSession, user_id: uuid.UUID, xp: int, now: datetime | None = None) -> int:
	"""Gọi trong award_activity: nhân đôi XP khi booster còn hạn, cộng xu = XP // 2. Trả XP cuối cùng. KHÔNG commit."""
	if xp <= 0:
		return xp
	now = now or _now()
	wallet = await get_wallet(db, user_id, now)
	if wallet.booster_until is not None and wallet.booster_until > now:
		xp *= 2
	wallet.coins += xp // XP_PER_COIN
	return xp


async def view(db: AsyncSession, user_id: uuid.UUID) -> dict:
	wallet = await get_wallet(db, user_id)
	owned = {i.item_id: i.equipped for i in await db.scalars(select(UserItem).where(UserItem.user_id == user_id))}
	await db.commit()
	now = _now()
	next_in = None
	if wallet.hearts < HEART_MAX:
		next_in = max(0, int((wallet.hearts_updated_at + HEART_REGEN - now).total_seconds()))
	booster_left = int((wallet.booster_until - now).total_seconds()) if wallet.booster_until and wallet.booster_until > now else 0
	return {
		"coins": wallet.coins,
		"hearts": wallet.hearts,
		"max_hearts": HEART_MAX,
		"next_heart_in_seconds": next_in,
		"booster_seconds_left": booster_left,
		"heart_refill_cost": HEART_REFILL_COST,
		"gacha_cost": GACHA_COST,
		"shop": [
			{"id": item_id, **info, "owned": item_id in owned, "equipped": owned.get(item_id, False)}
			for item_id, info in SHOP.items()
		],
	}


async def lose_heart(db: AsyncSession, user_id: uuid.UUID) -> dict:
	wallet = await get_wallet(db, user_id)
	if wallet.hearts > 0:
		if wallet.hearts == HEART_MAX:
			wallet.hearts_updated_at = _now()  # bắt đầu đếm hồi từ lúc mất tim đầu tiên
		wallet.hearts -= 1
	await db.commit()
	return {"hearts": wallet.hearts}


async def refill_hearts(db: AsyncSession, user_id: uuid.UUID) -> dict:
	wallet = await get_wallet(db, user_id)
	if wallet.hearts >= HEART_MAX:
		raise ValueError("hearts_full")
	if wallet.coins < HEART_REFILL_COST:
		raise ValueError("not_enough_coins")
	wallet.coins -= HEART_REFILL_COST
	wallet.hearts = HEART_MAX
	await db.commit()
	return {"hearts": wallet.hearts, "coins": wallet.coins}


def _extend_booster(wallet: Wallet) -> None:
	start = max(_now(), wallet.booster_until) if wallet.booster_until else _now()
	wallet.booster_until = start + BOOSTER_DURATION


async def buy(db: AsyncSession, user_id: uuid.UUID, item_id: str) -> dict:
	item = SHOP.get(item_id)
	if item is None:
		raise LookupError("item_not_found")
	wallet = await get_wallet(db, user_id)
	if item["slot"] != "booster" and await db.get(UserItem, (user_id, item_id)) is not None:
		raise ValueError("already_owned")
	if wallet.coins < item["price"]:
		raise ValueError("not_enough_coins")
	wallet.coins -= item["price"]
	if item["slot"] == "booster":
		_extend_booster(wallet)
	else:
		db.add(UserItem(user_id=user_id, item_id=item_id))
	await db.commit()
	return {"coins": wallet.coins}


async def equip(db: AsyncSession, user_id: uuid.UUID, item_id: str) -> None:
	item = SHOP.get(item_id)
	owned = await db.get(UserItem, (user_id, item_id))
	if item is None or item["slot"] == "booster" or owned is None:
		raise LookupError("item_not_owned")
	same_slot = [i for i, info in SHOP.items() if info["slot"] == item["slot"]]
	for row in await db.scalars(select(UserItem).where(UserItem.user_id == user_id, UserItem.item_id.in_(same_slot))):
		row.equipped = row.item_id == item_id
	await db.commit()


async def gacha(db: AsyncSession, user_id: uuid.UUID, rng: random.Random | None = None) -> dict:
	rng = rng or random
	wallet = await get_wallet(db, user_id)
	if wallet.coins < GACHA_COST:
		raise ValueError("not_enough_coins")
	wallet.coins -= GACHA_COST
	reward = rng.choices([r for _, r in LOOT], weights=[w for w, _ in LOOT])[0]
	result: dict = {"reward": reward, "duplicate": False}
	if "coins" in reward:
		wallet.coins += reward["coins"]
	elif "booster" in reward:
		_extend_booster(wallet)
	elif await db.get(UserItem, (user_id, reward["item"])) is not None:
		wallet.coins += DUPLICATE_REFUND  # trùng đồ thì hoàn xu thay vì mất trắng
		result["duplicate"] = True
	else:
		db.add(UserItem(user_id=user_id, item_id=reward["item"]))
	await db.commit()
	result["coins"] = wallet.coins
	return result
