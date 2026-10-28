import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError, ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    hash_password,
    hash_password_reset_token,
    hash_refresh_token,
    verify_password,
)
from app.models import PasswordResetToken, RefreshToken, User
from app.services.email_service import send_password_reset_email


async def register(
    email: str, password: str, full_name: str, db: AsyncSession, phone: str | None = None
) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ConflictError("Email already registered")
    if phone:
        existing_phone = await db.execute(select(User).where(User.phone == phone))
        if existing_phone.scalar_one_or_none():
            raise ConflictError("Phone number already registered")
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        phone=phone or None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login(
    identifier: str, password: str, user_agent: str | None, db: AsyncSession
) -> tuple[str, str]:
    result = await db.execute(
        select(User).where(
            or_(User.email == identifier, User.phone == identifier),
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Invalid credentials")

    access_token = create_access_token(str(user.id))
    raw_refresh, hashed = create_refresh_token()

    rt = RefreshToken(
        user_id=user.id,
        token_hash=hashed,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        user_agent=user_agent,
    )
    db.add(rt)
    await db.commit()
    return access_token, raw_refresh


async def refresh(raw_token: str, db: AsyncSession) -> str:
    hashed = hash_refresh_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hashed,
            RefreshToken.is_revoked.is_(False),
        )
    )
    rt = result.scalar_one_or_none()
    if rt is None or rt.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        raise UnauthorizedError("Invalid or expired refresh token")

    access_token = create_access_token(str(rt.user_id))
    return access_token


async def logout(raw_token: str, db: AsyncSession) -> None:
    hashed = hash_refresh_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hashed)
    )
    rt = result.scalar_one_or_none()
    if rt:
        rt.is_revoked = True
        await db.commit()


async def logout_all(user_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked.is_(False),
        )
    )
    tokens = result.scalars().all()
    for rt in tokens:
        rt.is_revoked = True
    await db.commit()


async def request_password_reset(email: str, db: AsyncSession) -> bool:
    result = await db.execute(select(User).where(User.email == email, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user is None:
        return False

    raw_token, token_hash = create_password_reset_token()
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC)
        + timedelta(minutes=settings.password_reset_token_expire_minutes),
    )
    db.add(token)
    await db.commit()

    reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={raw_token}"
    await send_password_reset_email(user.email, reset_url)
    return True


async def reset_password(raw_token: str, password: str, db: AsyncSession) -> None:
    token_hash = hash_password_reset_token(raw_token)
    result = await db.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
    )
    token = result.scalar_one_or_none()
    now = datetime.now(UTC)

    if (
        token is None
        or token.consumed_at is not None
        or token.expires_at.replace(tzinfo=UTC) < now
    ):
        raise BadRequestError("Invalid or expired reset link")

    user_result = await db.execute(
        select(User).where(User.id == token.user_id, User.is_active.is_(True))
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise BadRequestError("Invalid or expired reset link")

    user.hashed_password = hash_password(password)
    token.consumed_at = now

    refresh_result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.is_revoked.is_(False),
        )
    )
    for refresh_token in refresh_result.scalars().all():
        refresh_token.is_revoked = True

    await db.commit()
