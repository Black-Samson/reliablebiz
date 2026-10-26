"""Read-only in-memory store for the sample inventory and order data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InventoryItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    sku: str
    name: str
    quantity: int = Field(ge=0)
    unit_price: float = Field(ge=0)
    reorder_level: int = Field(ge=0)
    location: str

    @property
    def stock_status(self) -> Literal["out_of_stock", "low_stock", "in_stock"]:
        if self.quantity == 0:
            return "out_of_stock"
        if self.quantity <= self.reorder_level:
            return "low_stock"
        return "in_stock"


class OrderLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    sku: str
    quantity: int = Field(gt=0)


class Order(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str
    customer_name: str
    status: Literal["processing", "shipped", "delivered", "backordered", "cancelled"]
    order_date: str
    items: list[OrderLine]
    total_amount: float = Field(ge=0)
    currency: str


def _read_json(path: Path) -> list[dict]:
    # Explicit UTF-8: Windows would otherwise default to a legacy code page.
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


class DataStore:
    """Holds validated, immutable sample records. Has no write methods."""

    def __init__(self, inventory: list[InventoryItem], orders: list[Order]) -> None:
        self._inventory = tuple(inventory)
        self._orders = {o.order_id: o for o in orders}
        self._by_sku = {i.sku.upper(): i for i in inventory}
        known = set(self._by_sku)
        for order in orders:
            for line in order.items:
                if line.sku.upper() not in known:
                    raise ValueError(f"{order.order_id} references unknown SKU {line.sku}")

    @classmethod
    def from_dir(cls, data_dir: Path) -> "DataStore":
        inventory = [InventoryItem(**row) for row in _read_json(Path(data_dir) / "inventory.json")]
        orders = [Order(**row) for row in _read_json(Path(data_dir) / "orders.json")]
        return cls(inventory, orders)

    @property
    def inventory(self) -> tuple[InventoryItem, ...]:
        return self._inventory

    @property
    def orders(self) -> list[Order]:
        return list(self._orders.values())

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def get_item_by_sku(self, sku: str) -> InventoryItem | None:
        return self._by_sku.get(sku.upper())

    def search_items(self, query: str) -> list[InventoryItem]:
        """Exact SKU, then exact name, then all-words-contained match."""
        q = query.strip().lower()
        if not q:
            return []
        exact_sku = self._by_sku.get(q.upper())
        if exact_sku:
            return [exact_sku]
        exact_name = [i for i in self._inventory if i.name.lower() == q]
        if exact_name:
            return exact_name
        words = q.split()
        return [
            i
            for i in self._inventory
            if all(w in i.name.lower() or w in i.sku.lower() for w in words)
        ]
