from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import classroom_service

# Chế độ lớp học (backlog nhóm 5).
router = APIRouter(prefix="/classes", tags=["classes"])

_STATUS = {"class_not_found": 404, "assignment_not_found": 404, "member_not_found": 404, "not_teacher": 403}


def _raise(error: ValueError) -> None:
	raise HTTPException(_STATUS.get(str(error), 400), detail=str(error)) from error


class ClassCreate(BaseModel):
	name: str = Field(min_length=1, max_length=100)


class JoinRequest(BaseModel):
	code: str = Field(min_length=4, max_length=8)


class AssignmentCreate(BaseModel):
	title: str = Field(min_length=1, max_length=150)
	description: str | None = Field(default=None, max_length=2000)
	skill: Literal["reading", "listening", "writing", "speaking", "vocab", "grammar"] | None = None
	due_date: date | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create(request: ClassCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
	try:
		room = await classroom_service.create_class(db, current_user, request.name)
	except ValueError as error:
		_raise(error)
	return {"id": str(room.id), "name": room.name, "join_code": room.join_code}


@router.post("/join")
async def join(request: JoinRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
	try:
		room = await classroom_service.join_class(db, current_user, request.code)
	except ValueError as error:
		_raise(error)
	return {"id": str(room.id), "name": room.name}


@router.get("")
async def mine(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
	return await classroom_service.my_classes(db, current_user.id)


@router.get("/{class_id}")
async def detail(class_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
	try:
		return await classroom_service.class_detail(db, current_user.id, class_id)
	except ValueError as error:
		_raise(error)


@router.post("/{class_id}/assignments", status_code=status.HTTP_201_CREATED)
async def add_assignment(
	class_id: UUID, request: AssignmentCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
	try:
		item = await classroom_service.add_assignment(db, current_user.id, class_id, request.title, request.description, request.skill, request.due_date)
	except ValueError as error:
		_raise(error)
	return {"id": str(item.id)}


@router.delete("/{class_id}/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
	class_id: UUID, assignment_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Response:
	try:
		await classroom_service.delete_assignment(db, current_user.id, class_id, assignment_id)
	except ValueError as error:
		_raise(error)
	return Response(status_code=204)


@router.delete("/{class_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
	class_id: UUID, member_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Response:
	try:
		await classroom_service.remove_member(db, current_user.id, class_id, member_id)
	except ValueError as error:
		_raise(error)
	return Response(status_code=204)


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(class_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Response:
	try:
		await classroom_service.delete_class(db, current_user.id, class_id)
	except ValueError as error:
		_raise(error)
	return Response(status_code=204)
