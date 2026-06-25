import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import get_session
from models import User
from sqlalchemy import select, func

router = APIRouter(prefix="/users", tags=["users"])


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: str

    model_config = {"from_attributes": True}


@router.get("/sample-ids")
async def sample_user_ids(limit: int = Query(50, le=200)):
    async with get_session() as session:
        result = await session.execute(select(User.id).order_by(func.random()).limit(limit))
        return [str(row[0]) for row in result.fetchall()]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID):
    async with get_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse.model_validate(user)
