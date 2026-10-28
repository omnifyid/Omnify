from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequestError
from app.core.security import hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas.auth import UserRead

router = APIRouter()


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    old_password: str | None = None
    password: str | None = Field(default=None, min_length=8)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.password is not None:
        if not payload.old_password or not verify_password(
            payload.old_password, current_user.hashed_password
        ):
            raise BadRequestError("Current password is incorrect")
        current_user.hashed_password = hash_password(payload.password)
    await db.commit()
    await db.refresh(current_user)
    return current_user
