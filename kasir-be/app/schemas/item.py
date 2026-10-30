import uuid

from pydantic import BaseModel, Field, field_validator, model_validator


class OptionChoiceCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    is_default: bool = False
    sort_order: int = 0


class OptionChoiceRead(BaseModel):
    id: uuid.UUID
    label: str
    is_default: bool
    sort_order: int

    model_config = {"from_attributes": True}


class OptionGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_required: bool = False
    sort_order: int = 0
    choices: list[OptionChoiceCreate] = []


class OptionGroupRead(BaseModel):
    id: uuid.UUID
    name: str
    is_required: bool
    sort_order: int
    choices: list[OptionChoiceRead] = []

    model_config = {"from_attributes": True}


class AddonChoiceCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    extra_price: int = Field(ge=0)
    is_available: bool = True
    sort_order: int = 0


class AddonChoiceRead(BaseModel):
    id: uuid.UUID
    label: str
    extra_price: int
    is_available: bool
    sort_order: int

    model_config = {"from_attributes": True}


class AddonGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_required: bool = False
    min_select: int = Field(default=0, ge=0)
    max_select: int | None = None
    sort_order: int = 0
    choices: list[AddonChoiceCreate] = []


class AddonGroupRead(BaseModel):
    id: uuid.UUID
    name: str
    is_required: bool
    min_select: int
    max_select: int | None
    sort_order: int
    choices: list[AddonChoiceRead] = []

    model_config = {"from_attributes": True}


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    base_price: int = Field(ge=0)
    cost_price: int | None = Field(default=None, ge=0)
    category_id: uuid.UUID | None = None
    is_available: bool = True
    sort_order: int = 0
    stock: int | None = Field(default=None, ge=0)
    icon: str | None = Field(default=None, max_length=16)
    option_groups: list[OptionGroupCreate] = []
    addon_groups: list[AddonGroupCreate] = []


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    base_price: int | None = Field(default=None, ge=0)
    cost_price: int | None = Field(default=None, ge=0)
    category_id: uuid.UUID | None = None
    is_available: bool | None = None
    sort_order: int | None = None
    stock: int | None = Field(default=None, ge=0)
    icon: str | None = Field(default=None, max_length=16)


class StockUpdate(BaseModel):
    stock: int | None

    @model_validator(mode="after")
    def check_non_negative(self) -> "StockUpdate":
        if self.stock is not None and self.stock < 0:
            raise ValueError("stock must be >= 0")
        return self


class PublicItemRead(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    category_id: uuid.UUID | None
    name: str
    description: str | None
    base_price: int
    image_url: str | None
    icon: str | None
    is_available: bool
    sort_order: int
    stock: int | None
    option_groups: list[OptionGroupRead] = []
    addon_groups: list[AddonGroupRead] = []

    model_config = {"from_attributes": True}


class ChannelPricesUpdate(BaseModel):
    prices: dict[str, int | None]  # channel -> manual price; null/0 clears it


class ItemRead(PublicItemRead):
    cost_price: int | None
    channel_prices: dict[str, int] = {}  # manual platform prices, staff only

    @field_validator("channel_prices", mode="before")
    @classmethod
    def rows_to_dict(cls, v):
        if isinstance(v, list):
            return {r.channel: r.price for r in v}
        return v
