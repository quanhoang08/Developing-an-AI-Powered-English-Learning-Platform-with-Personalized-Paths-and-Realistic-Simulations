from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import economy_service, guild_service

router = APIRouter(tags=["economy"])


class GuildName(BaseModel):
	name: str = Field(min_length=1, max_length=40)


class GuildCode(BaseModel):
	code: str = Field(min_length=1, max_length=8)


def _fail(error: Exception) -> HTTPException:
	status = 404 if isinstance(error, LookupError) else 409
	return HTTPException(status_code=status, detail=str(error.args[0]))


@router.get("/economy/wallet")
async def wallet(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
	return await economy_service.view(db, current_user.id)


@router.post("/economy/hearts/lose")
async def lose_heart(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
	return await economy_service.lose_heart(db, current_user.id)


@router.post("/economy/hearts/refill")
async def refill_hearts(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
	try:
		return await economy_service.refill_hearts(db, current_user.id)
	except ValueError as error:
		raise _fail(error) from error


@router.post("/economy/shop/{item_id}/buy")
async def buy(item_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
	try:
		return await economy_service.buy(db, current_user.id, item_id)
	except (LookupError, ValueError) as error:
		raise _fail(error) from error


@router.post("/economy/items/{item_id}/equip", status_code=204)
async def equip(item_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
	try:
		await economy_service.equip(db, current_user.id, item_id)
	except LookupError as error:
		raise _fail(error) from error


@router.post("/economy/gacha")
async def gacha(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
	try:
		return await economy_service.gacha(db, current_user.id)
	except ValueError as error:
		raise _fail(error) from error


@router.post("/guilds", status_code=201)
async def create_guild(request: GuildName, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
	try:
		await guild_service.create(db, current_user, request.name)
	except ValueError as error:
		raise _fail(error) from error
	return await guild_service.mine(db, current_user.id)


@router.post("/guilds/join")
async def join_guild(request: GuildCode, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
	try:
		await guild_service.join(db, current_user, request.code)
	except (LookupError, ValueError) as error:
		raise _fail(error) from error
	return await guild_service.mine(db, current_user.id)


@router.post("/guilds/leave", status_code=204)
async def leave_guild(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
	try:
		await guild_service.leave(db, current_user.id)
	except LookupError as error:
		raise _fail(error) from error


@router.get("/guilds/me")
async def my_guild(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict | None:
	return await guild_service.mine(db, current_user.id)


@router.get("/guilds/leaderboard")
async def guild_leaderboard(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
	return await guild_service.leaderboard(db, current_user.id)
