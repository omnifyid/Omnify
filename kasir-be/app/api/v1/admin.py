import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import require_superadmin
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.database import get_db
from app.models import Store, StoreMembership, StoreRole, User
from app.schemas.auth import UserRead
from app.schemas.common import PaginatedResponse
from app.services import auth_service, seed_service, store_service

router = APIRouter()
user_router = APIRouter()
seed_router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class AdminUserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)
    phone: str | None = Field(default=None, max_length=20)


class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = None
    is_superadmin: bool | None = None
    is_active: bool | None = None


class AdminUserResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=8)


class AdminStoreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    owner_email: EmailStr


class AdminStoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    is_active: bool | None = None
    self_order_enabled: bool | None = None


class ResetOwnerPasswordIn(BaseModel):
    new_password: str = Field(min_length=8)


class AssignOwnerIn(BaseModel):
    owner_email: EmailStr


class AdminStoreRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    is_active: bool
    self_order_enabled: bool
    owner_email: str | None
    owner_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _owner_subquery():
    return (
        select(
            StoreMembership.store_id,
            User.id.label("owner_id"),
            User.email.label("owner_email"),
        )
        .join(User, User.id == StoreMembership.user_id)
        .where(StoreMembership.role == StoreRole.OWNER, StoreMembership.is_active.is_(True))
        .subquery("owner_sq")
    )


async def _fetch_admin_store(store_id: uuid.UUID, db: AsyncSession) -> AdminStoreRead:
    owner_sq = _owner_subquery()
    result = await db.execute(
        select(Store, owner_sq.c.owner_id, owner_sq.c.owner_email)
        .outerjoin(owner_sq, owner_sq.c.store_id == Store.id)
        .where(Store.id == store_id)
    )
    row = result.one_or_none()
    if row is None:
        raise NotFoundError("Store not found")
    store, owner_id, owner_email = row
    return AdminStoreRead(
        id=store.id, name=store.name, slug=store.slug,
        description=store.description, is_active=store.is_active,
        self_order_enabled=store.self_order_enabled,
        owner_email=owner_email, owner_id=owner_id,
    )


# ── User routes ───────────────────────────────────────────────────────────────

@user_router.get("", response_model=PaginatedResponse[UserRead])
async def search_users(
    search: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    base = select(User)
    if search:
        base = base.where(
            or_(
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
                User.phone.ilike(f"%{search}%"),
            )
        )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    result = await db.execute(base.order_by(User.full_name, User.email).limit(limit).offset(offset))
    return {"items": list(result.scalars().all()), "total": total, "limit": limit, "offset": offset}


@user_router.post("", response_model=UserRead, status_code=201)
async def create_user(
    payload: AdminUserCreate,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    return await auth_service.register(payload.email, payload.password, payload.full_name, db, payload.phone)


@user_router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: uuid.UUID,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    return user


@user_router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")

    data = payload.model_dump(exclude_unset=True)

    if "email" in data and data["email"] != user.email:
        existing = await db.execute(select(User).where(User.email == data["email"]))
        if existing.scalar_one_or_none():
            raise ConflictError("Email already in use")

    if "phone" in data and data["phone"] and data["phone"] != user.phone:
        existing = await db.execute(select(User).where(User.phone == data["phone"]))
        if existing.scalar_one_or_none():
            raise ConflictError("Phone number already in use")

    for key, value in data.items():
        setattr(user, key, value if value != "" else None)

    await db.commit()
    await db.refresh(user)
    return user


@user_router.post("/{user_id}/reset-password", status_code=204)
async def reset_user_password(
    user_id: uuid.UUID,
    payload: AdminUserResetPasswordIn,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    user.hashed_password = hash_password(payload.new_password)
    await db.commit()


# ── Stats route ───────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    store_count = (await db.execute(select(func.count(Store.id)))).scalar_one()
    owner_count = (await db.execute(
        select(func.count(func.distinct(StoreMembership.user_id)))
        .where(StoreMembership.role == StoreRole.OWNER, StoreMembership.is_active.is_(True))
    )).scalar_one()
    return {"store_count": store_count, "owner_count": owner_count, "demo_mode": settings.demo_mode}


# ── Store routes ──────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[AdminStoreRead])
async def list_all_stores(
    search: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    owner_sq = _owner_subquery()

    def _apply_search(stmt):
        if not search:
            return stmt
        return stmt.where(
            or_(
                Store.name.ilike(f"%{search}%"),
                owner_sq.c.owner_email.ilike(f"%{search}%"),
            )
        )

    count_stmt = _apply_search(
        select(func.count(Store.id)).outerjoin(owner_sq, owner_sq.c.store_id == Store.id)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = _apply_search(
        select(Store, owner_sq.c.owner_id, owner_sq.c.owner_email)
        .outerjoin(owner_sq, owner_sq.c.store_id == Store.id)
        .order_by(Store.name)
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(data_stmt)).all()

    items = [
        AdminStoreRead(
            id=s.id, name=s.name, slug=s.slug,
            description=s.description, is_active=s.is_active,
            self_order_enabled=s.self_order_enabled,
            owner_email=email, owner_id=oid,
        )
        for s, oid, email in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("", response_model=AdminStoreRead, status_code=201)
async def create_store_with_owner(
    payload: AdminStoreCreate,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    owner_result = await db.execute(
        select(User).where(User.email == payload.owner_email, User.is_active.is_(True))
    )
    owner = owner_result.scalar_one_or_none()
    if not owner:
        raise NotFoundError("Owner user not found")
    store = await store_service.create_store(payload.name, payload.slug, payload.description, owner, db)
    return AdminStoreRead(
        id=store.id, name=store.name, slug=store.slug,
        description=store.description, is_active=store.is_active,
        self_order_enabled=store.self_order_enabled,
        owner_email=payload.owner_email,
    )


@router.patch("/{store_id}", response_model=AdminStoreRead)
async def update_store(
    store_id: uuid.UUID,
    payload: AdminStoreUpdate,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise NotFoundError("Store not found")

    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"] != store.slug:
        existing = await db.execute(select(Store).where(Store.slug == data["slug"]))
        if existing.scalar_one_or_none():
            raise ConflictError("Slug already taken")

    for key, value in data.items():
        setattr(store, key, value)
    await db.commit()
    await db.refresh(store)
    return await _fetch_admin_store(store_id, db)


@router.post("/{store_id}/reset-password", status_code=200)
async def reset_owner_password(
    store_id: uuid.UUID,
    payload: ResetOwnerPasswordIn,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .join(StoreMembership, StoreMembership.user_id == User.id)
        .where(
            StoreMembership.store_id == store_id,
            StoreMembership.role == StoreRole.OWNER,
            StoreMembership.is_active.is_(True),
        )
    )
    owner = result.scalar_one_or_none()
    if not owner:
        raise NotFoundError("Store owner not found")
    owner.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return {"message": "Password reset successfully"}


@router.post("/{store_id}/owner", status_code=200)
async def assign_store_owner(
    store_id: uuid.UUID,
    payload: AssignOwnerIn,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    await store_service.add_member(store_id, payload.owner_email, StoreRole.OWNER, db, allow_owner=True)
    return await _fetch_admin_store(store_id, db)


# ── Demo data ─────────────────────────────────────────────────────────────────

def _require_demo_mode() -> None:
    if not settings.demo_mode:
        raise ForbiddenError("Demo data tools are disabled (set DEMO_MODE=true on this server)")


@seed_router.post("/reset")
async def reset_demo_data(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Remove the demo stores and users, then seed them again."""
    _require_demo_mode()
    return await seed_service.reseed(db)


@seed_router.delete("")
async def clear_demo_data(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Remove the demo stores and users without seeding again."""
    _require_demo_mode()
    return {"removed_stores": await seed_service.reset_demo(db)}
