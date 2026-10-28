import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AnyMember, OwnerOrManager
from app.database import get_db
from app.models import StoreMembership
from app.schemas.package import PackageCreate, PackageRead, PackageUpdate
from app.services import package_service

router = APIRouter()


@router.get("/{store_id}/packages", response_model=list[PackageRead])
async def list_packages(
    store_id: uuid.UUID,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await package_service.list_packages(store_id, db)


@router.post("/{store_id}/packages", response_model=PackageRead, status_code=201)
async def create_package(
    store_id: uuid.UUID,
    payload: PackageCreate,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await package_service.create_package(store_id, payload, db)


@router.get("/{store_id}/packages/{package_id}", response_model=PackageRead)
async def get_package(
    store_id: uuid.UUID,
    package_id: uuid.UUID,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await package_service.get_package(package_id, store_id, db)


@router.patch("/{store_id}/packages/{package_id}", response_model=PackageRead)
async def update_package(
    store_id: uuid.UUID,
    package_id: uuid.UUID,
    payload: PackageUpdate,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await package_service.update_package(package_id, store_id, payload, db)


@router.delete("/{store_id}/packages/{package_id}", status_code=204)
async def delete_package(
    store_id: uuid.UUID,
    package_id: uuid.UUID,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    await package_service.delete_package(package_id, store_id, db)
