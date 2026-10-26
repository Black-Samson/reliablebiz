"""The three business tools and the allow-list registry.

Every tool is a pure, read-only function over the in-memory sample data.
There is no network, file-write, shell, SQL or payment capability here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel

from .calculator import CalculatorError, calculate
from .datastore import DataStore, InventoryItem
from .schemas import CalculatorArgs, InventoryLookupArgs, OrderLookupArgs, ToolOutcome


def _item_view(item: InventoryItem) -> dict:
    return {
        "sku": item.sku,
        "name": item.name,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "stock_status": item.stock_status,
        "location": item.location,
    }


def inventory_lookup(args: InventoryLookupArgs, store: DataStore) -> ToolOutcome:
    matches = store.search_items(args.item)
    if not matches:
        return ToolOutcome(
            ok=False,
            code="not_found",
            message=f"No inventory item matches '{args.item}'.",
            data={"query": args.item},
        )
    return ToolOutcome(
        ok=True,
        code="ok",
        message=f"Found {len(matches)} matching item(s).",
        data={"query": args.item, "items": [_item_view(i) for i in matches]},
    )


def order_lookup(args: OrderLookupArgs, store: DataStore) -> ToolOutcome:
    order = store.get_order(args.order_id)
    if order is None:
        return ToolOutcome(
            ok=False,
            code="not_found",
            message=f"No order with ID {args.order_id} exists.",
            data={"order_id": args.order_id},
        )
    lines = []
    for line in order.items:
        item = store.get_item_by_sku(line.sku)
        lines.append({"sku": line.sku, "name": item.name if item else line.sku, "quantity": line.quantity})
    return ToolOutcome(
        ok=True,
        code="ok",
        message=f"Order {order.order_id} found.",
        data={
            "order_id": order.order_id,
            "customer_name": order.customer_name,
            "status": order.status,
            "order_date": order.order_date,
            "items": lines,
            "total_amount": order.total_amount,
            "currency": order.currency,
        },
    )


def calculator(args: CalculatorArgs, store: DataStore) -> ToolOutcome:
    try:
        result = calculate(args.expression)
    except CalculatorError as err:
        return ToolOutcome(ok=False, code=err.code, message=err.message, data={"expression": args.expression})
    return ToolOutcome(
        ok=True,
        code="ok",
        message="Calculated.",
        data={"expression": args.expression, "result": result},
    )


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[..., ToolOutcome]


TOOL_REGISTRY: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec("inventory_lookup", "Look up stock level and price for a product by name or SKU.", InventoryLookupArgs, inventory_lookup),
        ToolSpec("order_lookup", "Look up the status and contents of an order by order ID.", OrderLookupArgs, order_lookup),
        ToolSpec("calculator", "Evaluate a basic arithmetic expression safely.", CalculatorArgs, calculator),
    )
}


def tool_catalog() -> list[dict]:
    """JSON-schema description of every tool (useful later for model prompts)."""
    return [
        {"name": s.name, "description": s.description, "parameters": s.args_model.model_json_schema()}
        for s in TOOL_REGISTRY.values()
    ]
