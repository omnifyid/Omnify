import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AnyMember, OwnerOnly, OwnerOrManager
from app.database import get_db
from app.models import OrderChannel, StoreMembership
from app.schemas.channel import ChannelReport, ChannelSettingRead, ChannelSettingUpdate
from app.services import channel_service

router = APIRouter()


@router.get("/{store_id}/channels", response_model=list[ChannelSettingRead])
async def list_channels(
    store_id: uuid.UUID,
    _: StoreMembership = Depends(AnyMember),
    db: AsyncSession = Depends(get_db),
):
    return await channel_service.list_settings(store_id, db)


@router.patch("/{store_id}/channels/{channel}", response_model=ChannelSettingRead)
async def update_channel(
    store_id: uuid.UUID,
    channel: OrderChannel,
    payload: ChannelSettingUpdate,
    _: StoreMembership = Depends(OwnerOnly),
    db: AsyncSession = Depends(get_db),
):
    return await channel_service.update_setting(store_id, channel, payload, db)


@router.get("/{store_id}/reports/by-channel", response_model=ChannelReport)
async def channel_report(
    store_id: uuid.UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    _: StoreMembership = Depends(OwnerOrManager),
    db: AsyncSession = Depends(get_db),
):
    return await channel_service.channel_report(store_id, db, from_date, to_date)
