from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.main import limiter
from app.models import User
from app.schemas.auth import (
    ForgotPasswordIn,
    LoginIn,
    RefreshIn,
    RegisterIn,
    ResetPasswordIn,
    TokenResponse,
    UserRead,
)
from app.services import auth_service
from app.services.email_service import EmailSendError

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=201)
@limiter.limit("10/minute")
async def register(
    request: Request,
    payload: RegisterIn,
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.register(payload.email, payload.password, payload.full_name, db, payload.phone)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("20/minute")
async def login(
    request: Request,
    payload: LoginIn,
    user_agent: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    access_token, refresh_token = await auth_service.login(
        payload.identifier, payload.password, user_agent, db
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/forgot-password", status_code=204)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    payload: ForgotPasswordIn,
    db: AsyncSession = Depends(get_db),
):
    try:
        await auth_service.request_password_reset(payload.email, db)
    except EmailSendError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email could not be sent",
        ) from exc


@router.post("/reset-password", status_code=204)
@limiter.limit("10/minute")
async def reset_password(
    request: Request,
    payload: ResetPasswordIn,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.reset_password(payload.token, payload.password, db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshIn,
    db: AsyncSession = Depends(get_db),
):
    access_token = await auth_service.refresh(payload.refresh_token, db)
    return TokenResponse(access_token=access_token, refresh_token=payload.refresh_token)


@router.post("/logout", status_code=204)
async def logout(
    payload: RefreshIn,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.logout(payload.refresh_token, db)


@router.post("/logout-all", status_code=204)
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await auth_service.logout_all(current_user.id, db)
