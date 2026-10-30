import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class IngredientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    unit: str = Field(min_length=1, max_length=20)
    category: str | None = Field(default=None, max_length=100)
    min_stock: float = Field(default=0, ge=0)
    cost_price: int = Field(default=0, ge=0)
    initial_stock: float = Field(default=0, ge=0)


class IngredientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    category: str | None = Field(default=None, max_length=100)
    min_stock: float | None = Field(default=None, ge=0)
    cost_price: int | None = Field(default=None, ge=0)


class IngredientRead(BaseModel):
    id: uuid.UUID
    name: str
    unit: str
    category: str | None
    stock: float
    min_stock: float
    cost_price: int

    model_config = {"from_attributes": True}


class RestockIn(BaseModel):
    quantity: float = Field(gt=0)
    cost_price: int | None = Field(default=None, ge=0)  # updates the ingredient's unit cost
    note: str | None = Field(default=None, max_length=255)


class OpnameLine(BaseModel):
    ingredient_id: uuid.UUID
    counted: float = Field(ge=0)


class OpnameIn(BaseModel):
    lines: list[OpnameLine] = Field(min_length=1)


class OpnameResult(BaseModel):
    adjusted: int


class MovementRead(BaseModel):
    id: uuid.UUID
    ingredient_id: uuid.UUID
    ingredient_name: str
    unit: str
    type: str
    quantity: float
    balance_after: float
    note: str | None
    order_id: uuid.UUID | None
    created_at: datetime


class RecipeLineIn(BaseModel):
    ingredient_id: uuid.UUID
    quantity: float = Field(gt=0)


class RecipeUpdate(BaseModel):
    lines: list[RecipeLineIn]


class RecipeLineRead(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    unit: str
    quantity: float
    cost_price: int


class IngredientSummary(BaseModel):
    count: int
    low_count: int
    stock_value: int
    categories: list[str]
