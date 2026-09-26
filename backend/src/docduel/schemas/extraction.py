"""Output contracts (Plan Section 9). Missing values are null, never omitted."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    quantity: float | None
    unit_price: float | None
    amount: float | None


class ReceiptExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: str | None
    document_date: str | None  # ISO YYYY-MM-DD
    document_number: str | None
    currency: str | None  # ISO 4217
    line_items: list[LineItem]
    subtotal: float | None
    tax: float | None
    service_charge: float | None
    discount: float | None  # positive number
    total: float | None
    payment_method: str | None


CATEGORIES = (
    "Groceries",
    "Dining",
    "Transport",
    "Utilities",
    "Shopping",
    "Health",
    "Entertainment",
    "Other",
)
Category = Literal[
    "Groceries", "Dining", "Transport", "Utilities", "Shopping", "Health", "Entertainment", "Other"
]


class TransactionCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_id: int
    category: Category


class TransactionCategories(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TransactionCategory]


class SummaryOutput(BaseModel):
    """summarise task (Plan 9.3): exactly three bullets."""

    model_config = ConfigDict(extra="forbid")

    bullets: Annotated[list[str], Field(min_length=3, max_length=3)]
