"""Turns an executor result into a plain-English answer (deterministic templates)."""

from __future__ import annotations

from .executor import ExecutionResult


def _money(amount: float, currency: str = "USD") -> str:
    symbol = "$" if currency == "USD" else f"{currency} "
    return f"{symbol}{amount:,.2f}"


_STATUS_TEXT = {
    "out_of_stock": "OUT OF STOCK",
    "low_stock": "low stock",
    "in_stock": "in stock",
}


def compose_answer(result: ExecutionResult) -> str:
    if result.status == "rejected_unknown_tool":
        return "I can't run that: it is not one of the allowed tools."

    if result.status == "invalid_arguments":
        problems = "; ".join(f"'{i.field}' {i.problem}" for i in result.issues)
        return f"I couldn't run {result.tool_name} because the request was incomplete or invalid: {problems}. Please fix this and try again."

    if result.status == "tool_error" or result.outcome is None:
        return f"Sorry, {result.tool_name} failed unexpectedly. Nothing was changed."

    out = result.outcome
    if not out.ok:
        return out.message

    data = out.data
    if result.tool_name == "inventory_lookup":
        lines = [
            f"{i['name']} ({i['sku']}): {i['quantity']} units, {_STATUS_TEXT[i['stock_status']]}, "
            f"{_money(i['unit_price'])} each, {i['location']}."
            for i in data["items"]
        ]
        return "\n".join(lines)

    if result.tool_name == "order_lookup":
        items = ", ".join(f"{l['quantity']} x {l['name']}" for l in data["items"])
        return (
            f"Order {data['order_id']} for {data['customer_name']} is {data['status']} "
            f"(placed {data['order_date']}). Items: {items}. Total {_money(data['total_amount'], data['currency'])}."
        )

    if result.tool_name == "calculator":
        return f"{data['expression']} = {data['result']}"

    return out.message
