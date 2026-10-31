import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache
from app.config import settings
from app.core.dependencies import AnyMember, OwnerOnly, OwnerOrManager, get_current_user
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.database import get_db
from app.models import RefreshToken, StoreMembership, StoreRole, User
from app.models.membership import ROLE_RANK
from app.schemas.common import PaginatedResponse
from app.schemas.store import (
    AddMemberIn,
    BranchCreate,
    MemberRead,
    StoreCreate,
    StoreRead,
    StoreUpdate,
    UpdateMemberRoleIn,
)
from app.services import store_service


class MemberPasswordResetIn(BaseModel):
    new_password: str = Field(min_length=8)


class SelforderToggleIn(BaseModel):
    is_open: bool


router = APIRouter()


@router.post("", response_model=StoreRead, status_code=201)
async def create_store(
    payload: StoreCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await store_service.create_store(
        payload.name, payload.slug, payload.description, current_user, db
    )


@router.get("", response_model=list[StoreRead])
async def list_stores(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await store_service.list_stores(current_user.id, db)
    return [StoreRead.model_validate({**store.__dict__, "role": role}) for store, role in rows]


@router.get("/{store_id}", response_model=StoreRead)
async def get_store(
    store_id: uuid.UUID,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await store_service.get_store(store_id, db)


# Money rules (tax, service charge, cash-difference limit) change what customers pay and how cash
# is judged, so only the owner may set them even though managers edit the rest of the store.
OWNER_ONLY_STORE_FIELDS = {"tax_bp", "service_bp", "pb1_bp", "shift_variance_threshold", "default_float"}


@router.patch("/{store_id}", response_model=StoreRead)
async def update_store(
    store_id: uuid.UUID,
    payload: StoreUpdate,
    m: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    changes = payload.model_dump(exclude_unset=True)
    if m.role != StoreRole.OWNER and OWNER_ONLY_STORE_FIELDS & changes.keys():
        raise ForbiddenError("Only the owner can change tax, service charge and shift cash settings")
    result = await store_service.update_store(store_id, changes, db)
    s = str(store_id)
    await cache.delete(cache.menu_key(s), cache.items_key(s), cache.cats_key(s))
    return result


@router.post("/{store_id}/logo", response_model=StoreRead)
async def upload_store_logo(
    store_id: uuid.UUID,
    file: UploadFile,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise BadRequestError("Only JPEG, PNG, and WebP images are allowed")
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise BadRequestError("File size must be under 2 MB")
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    dest = Path(settings.media_dir) / f"store_{store_id}.{ext}"
    dest.write_bytes(content)
    logo_url = f"/media/store_{store_id}.{ext}"
    result = await store_service.set_store_logo(store_id, logo_url, db)
    s = str(store_id)
    await cache.delete(cache.menu_key(s), cache.items_key(s), cache.cats_key(s))
    return result


@router.post("/{store_id}/branches", response_model=StoreRead, status_code=201)
async def create_branch(
    store_id: uuid.UUID,
    payload: BranchCreate,
    _: StoreMembership = Depends(OwnerOnly),
    db: AsyncSession = Depends(get_db),
):
    store = await store_service.create_branch(store_id, payload.name, payload.slug, db)
    await store_service.attach_catalog_info([store], db)
    return StoreRead.model_validate({**store.__dict__, "role": StoreRole.OWNER})


@router.delete("/{store_id}", status_code=204)
async def deactivate_store(
    store_id: uuid.UUID,
    _: StoreMembership = Depends(OwnerOnly),
    db: AsyncSession = Depends(get_db),
):
    await store_service.deactivate_store(store_id, db)


@router.get("/{store_id}/members", response_model=PaginatedResponse[MemberRead])
async def list_members(
    store_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    members, total = await store_service.list_members(store_id, db, limit, offset)
    items = [
        MemberRead(
            id=m.id,
            user_id=m.user_id,
            store_id=m.store_id,
            role=m.role,
            is_active=m.is_active,
            full_name=m.user.full_name if m.user else None,
            email=m.user.email if m.user else None,
            phone=m.user.phone if m.user else None,
        )
        for m in members
    ]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/{store_id}/members", response_model=MemberRead, status_code=201)
async def add_member(
    store_id: uuid.UUID,
    payload: AddMemberIn,
    _: StoreMembership = Depends(OwnerOnly),
    db: AsyncSession = Depends(get_db),
):
    m = await store_service.add_member(
        store_id, payload.email, payload.role, db,
        full_name=payload.full_name, phone=payload.phone
    )
    await db.refresh(m, ["user"])
    return MemberRead(
        id=m.id, user_id=m.user_id, store_id=m.store_id, role=m.role, is_active=m.is_active,
        full_name=m.user.full_name if m.user else None,
        email=m.user.email if m.user else None,
        phone=m.user.phone if m.user else None,
    )


@router.patch("/{store_id}/members/{member_user_id}", response_model=MemberRead)
async def update_member_role(
    store_id: uuid.UUID,
    member_user_id: uuid.UUID,
    payload: UpdateMemberRoleIn,
    _: StoreMembership = Depends(OwnerOnly),
    db: AsyncSession = Depends(get_db),
):
    return await store_service.update_member_role(store_id, member_user_id, payload.role, db)


@router.delete("/{store_id}/members/{member_user_id}", status_code=204)
async def remove_member(
    store_id: uuid.UUID,
    member_user_id: uuid.UUID,
    _: StoreMembership = Depends(OwnerOnly),
    db: AsyncSession = Depends(get_db),
):
    await store_service.remove_member(store_id, member_user_id, db)


@router.post("/{store_id}/members/{member_user_id}/reset-password", status_code=204)
async def reset_member_password(
    store_id: uuid.UUID,
    member_user_id: uuid.UUID,
    payload: MemberPasswordResetIn,
    requester: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    # Verify target is an active member of this store
    result = await db.execute(
        select(StoreMembership).where(
            StoreMembership.store_id == store_id,
            StoreMembership.user_id == member_user_id,
            StoreMembership.is_active.is_(True),
        )
    )
    target_membership = result.scalar_one_or_none()
    if target_membership is None:
        raise NotFoundError("Member not found")

    # Requester must outrank target in this store
    if ROLE_RANK[requester.role] <= ROLE_RANK[target_membership.role]:
        raise ForbiddenError("Insufficient role to reset this member's password")

    # Cross-tenant guard: block reset if the target is an owner of ANY store.
    # Without this check, an owner of Store A could reset the password of a user
    # who is also an owner of Store B, taking over that account.
    owner_elsewhere = await db.execute(
        select(StoreMembership).where(
            StoreMembership.user_id == member_user_id,
            StoreMembership.role == StoreRole.OWNER,
            StoreMembership.is_active.is_(True),
        )
    )
    if owner_elsewhere.scalar_one_or_none() is not None:
        raise ForbiddenError("Cannot reset password of a store owner")

    user_result = await db.execute(select(User).where(User.id == member_user_id))
    target_user = user_result.scalar_one_or_none()
    if target_user is None:
        raise NotFoundError("User not found")

    # Invalidate all active sessions so the old password cannot be used after reset
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == member_user_id, RefreshToken.is_revoked.is_(False))
        .values(is_revoked=True)
    )

    target_user.hashed_password = hash_password(payload.new_password)
    await db.commit()


@router.patch("/{store_id}/selforder", response_model=StoreRead)
async def toggle_selforder(
    store_id: uuid.UUID,
    payload: SelforderToggleIn,
    membership: StoreMembership = Depends(OwnerOnly),
    db: AsyncSession = Depends(get_db),
):
    return await store_service.update_store(store_id, {"selforder_is_open": payload.is_open}, db)
