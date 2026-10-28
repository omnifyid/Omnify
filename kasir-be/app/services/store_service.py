import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models import Store, StoreMembership, StoreRole, User


async def create_store(
    name: str, slug: str, description: str | None, owner: User, db: AsyncSession
) -> Store:
    existing = await db.execute(select(Store).where(Store.slug == slug))
    if existing.scalar_one_or_none():
        raise ConflictError("Slug already taken")
    store = Store(name=name, slug=slug, description=description)
    db.add(store)
    await db.flush()
    membership = StoreMembership(user_id=owner.id, store_id=store.id, role=StoreRole.OWNER)
    db.add(membership)
    await db.commit()
    await db.refresh(store)
    return store


async def list_stores(user_id: uuid.UUID, db: AsyncSession) -> list[tuple[Store, StoreRole]]:
    result = await db.execute(
        select(Store, StoreMembership.role)
        .join(StoreMembership, StoreMembership.store_id == Store.id)
        .where(
            StoreMembership.user_id == user_id,
            StoreMembership.is_active.is_(True),
            Store.is_active.is_(True),
        )
    )
    return list(result.all())


async def get_store(store_id: uuid.UUID, db: AsyncSession) -> Store:
    result = await db.execute(
        select(Store).where(Store.id == store_id, Store.is_active.is_(True))
    )
    store = result.scalar_one_or_none()
    if not store:
        raise NotFoundError("Store not found")
    return store


async def update_store(store_id: uuid.UUID, data: dict, db: AsyncSession) -> Store:
    store = await get_store(store_id, db)
    for key, value in data.items():
        if value is not None:
            setattr(store, key, value)
    await db.commit()
    await db.refresh(store)
    return store


async def set_store_logo(store_id: uuid.UUID, logo_url: str, db: AsyncSession) -> Store:
    store = await get_store(store_id, db)
    store.logo_url = logo_url
    await db.commit()
    await db.refresh(store)
    return store


async def deactivate_store(store_id: uuid.UUID, db: AsyncSession) -> None:
    store = await get_store(store_id, db)
    store.is_active = False
    await db.commit()


async def list_members(
    store_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[StoreMembership], int]:
    base = select(StoreMembership).where(
        StoreMembership.store_id == store_id, StoreMembership.is_active.is_(True)
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    result = await db.execute(
        base.options(selectinload(StoreMembership.user)).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def add_member(
    store_id: uuid.UUID,
    email: str,
    role: StoreRole,
    db: AsyncSession,
    allow_owner: bool = False,
    full_name: str | None = None,
    phone: str | None = None,
) -> StoreMembership:
    if role == StoreRole.OWNER and not allow_owner:
        raise ForbiddenError("Only superadmin can assign the OWNER role")

    from app.core.security import hash_password

    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if not user:
        # Auto-create the user so the owner can add staff directly.
        # A random password is set; owner uses Reset Password to give them access.
        if phone:
            existing_phone = await db.execute(select(User).where(User.phone == phone))
            if existing_phone.scalar_one_or_none():
                raise ConflictError("Phone number already registered to another account")
        user = User(
            email=email,
            hashed_password=hash_password(secrets.token_urlsafe(16)),
            full_name=full_name or email.split("@")[0],
            phone=phone or None,
        )
        db.add(user)
        await db.flush()
    else:
        # Update name/phone if provided for existing user
        if full_name and not user.full_name:
            user.full_name = full_name
        if phone and not user.phone:
            user.phone = phone

    existing = await db.execute(
        select(StoreMembership).where(
            StoreMembership.store_id == store_id,
            StoreMembership.user_id == user.id,
        )
    )
    m = existing.scalar_one_or_none()
    if m:
        if m.is_active:
            raise ConflictError("User is already a member")
        m.is_active = True
        m.role = role
        await db.commit()
        await db.refresh(m)
        return m

    membership = StoreMembership(store_id=store_id, user_id=user.id, role=role)
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


async def update_member_role(
    store_id: uuid.UUID, member_user_id: uuid.UUID, role: StoreRole, db: AsyncSession
) -> StoreMembership:
    result = await db.execute(
        select(StoreMembership).where(
            StoreMembership.store_id == store_id,
            StoreMembership.user_id == member_user_id,
            StoreMembership.is_active.is_(True),
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise NotFoundError("Member not found")
    if m.role == StoreRole.OWNER or role == StoreRole.OWNER:
        raise ForbiddenError("Only superadmin can change the OWNER role")
    m.role = role
    await db.commit()
    await db.refresh(m)
    return m


async def remove_member(
    store_id: uuid.UUID, member_user_id: uuid.UUID, db: AsyncSession
) -> None:
    result = await db.execute(
        select(StoreMembership).where(
            StoreMembership.store_id == store_id,
            StoreMembership.user_id == member_user_id,
            StoreMembership.is_active.is_(True),
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise NotFoundError("Member not found")
    if m.role == StoreRole.OWNER:
        raise ForbiddenError("Only superadmin can remove an OWNER")
    m.is_active = False
    await db.commit()
