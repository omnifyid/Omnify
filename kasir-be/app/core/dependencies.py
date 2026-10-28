import uuid

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.database import get_db
from app.models import Store, StoreMembership, StoreRole, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorizedError()
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(payload["sub"]), User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError()
    return user


async def get_store_membership(
    store_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StoreMembership:
    result = await db.execute(
        select(StoreMembership)
        .join(Store, Store.id == StoreMembership.store_id)
        .where(
            StoreMembership.user_id == current_user.id,
            StoreMembership.store_id == store_id,
            StoreMembership.is_active.is_(True),
            Store.is_active.is_(True),
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise ForbiddenError("Not a member of this store")
    return membership


def require_roles(*roles: StoreRole):
    """Dependency factory — raises 403 if the caller's role isn't in the allowed list."""

    async def checker(
        membership: StoreMembership = Depends(get_store_membership),
    ) -> StoreMembership:
        if membership.role not in roles:
            raise ForbiddenError(f"Required role: {[r.value for r in roles]}")
        return membership

    return checker


async def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superadmin:
        raise ForbiddenError("Superadmin access required")
    return current_user


# Pre-built guards used as Depends() in route handlers
OwnerOnly = require_roles(StoreRole.OWNER)
OwnerOrManager = require_roles(StoreRole.OWNER, StoreRole.MANAGER)
AnyMember = require_roles(StoreRole.OWNER, StoreRole.MANAGER, StoreRole.OPERATOR)
