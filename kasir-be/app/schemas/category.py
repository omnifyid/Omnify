import uuid

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    icon: str | None = Field(default=None, max_length=16)
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    icon: str | None = Field(default=None, max_length=16)
    sort_order: int | None = None


class CategoryRead(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    name: str
    icon: str | None
    sort_order: int

    model_config = {"from_attributes": True}
