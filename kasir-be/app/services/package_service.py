import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models import Package, PackageItem
from app.schemas.package import PackageCreate, PackageItemCreate, PackageUpdate


async def _load_package(package_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> Package:
    result = await db.execute(
        select(Package)
        .options(selectinload(Package.package_items).selectinload(PackageItem.item))
        .where(Package.id == package_id, Package.store_id == store_id)
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise NotFoundError("Package not found")
    return pkg


async def list_packages(store_id: uuid.UUID, db: AsyncSession) -> list[Package]:
    result = await db.execute(
        select(Package)
        .options(selectinload(Package.package_items).selectinload(PackageItem.item))
        .where(Package.store_id == store_id)
        .order_by(Package.sort_order, Package.name)
    )
    return list(result.scalars().all())


async def get_package(package_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> Package:
    return await _load_package(package_id, store_id, db)


async def create_package(store_id: uuid.UUID, payload: PackageCreate, db: AsyncSession) -> Package:
    pkg = Package(
        store_id=store_id,
        name=payload.name,
        description=payload.description,
        flat_price=payload.flat_price,
        is_available=payload.is_available,
        sort_order=payload.sort_order,
    )
    db.add(pkg)
    await db.flush()
    for pi in payload.items:
        db.add(PackageItem(package_id=pkg.id, item_id=pi.item_id, quantity=pi.quantity))
    await db.commit()
    return await _load_package(pkg.id, store_id, db)


async def update_package(
    package_id: uuid.UUID, store_id: uuid.UUID, payload: PackageUpdate, db: AsyncSession
) -> Package:
    pkg = await _load_package(package_id, store_id, db)
    data = payload.model_dump(exclude_unset=True)
    items_data: list[PackageItemCreate] | None = data.pop("items", None)
    for k, v in data.items():
        setattr(pkg, k, v)
    if items_data is not None:
        await db.execute(delete(PackageItem).where(PackageItem.package_id == package_id))
        await db.flush()
        for pi in items_data:
            db.add(PackageItem(package_id=pkg.id, item_id=pi.item_id, quantity=pi.quantity))
    await db.commit()
    return await _load_package(package_id, store_id, db)


async def delete_package(package_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> None:
    pkg = await _load_package(package_id, store_id, db)
    await db.delete(pkg)
    await db.commit()
