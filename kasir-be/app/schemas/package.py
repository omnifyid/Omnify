import uuid

from pydantic import BaseModel, Field


class PackageItemCreate(BaseModel):
    item_id: uuid.UUID
    quantity: int = Field(default=1, ge=1)


class PackageItemRead(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    quantity: int
    item_name: str | None = None

    model_config = {"from_attributes": True}


class PackageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    flat_price: int = Field(ge=0)
    is_available: bool = True
    sort_order: int = 0
    items: list[PackageItemCreate] = []


class PackageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    flat_price: int | None = Field(default=None, ge=0)
    is_available: bool | None = None
    sort_order: int | None = None
    items: list[PackageItemCreate] | None = None


class PackageRead(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    name: str
    description: str | None
    flat_price: int
    is_available: bool
    sort_order: int
    package_items: list[PackageItemRead] = []

    model_config = {"from_attributes": True}
