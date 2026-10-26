"""Pydantic input schemas for every tool, plus shared result models.

The schemas are the contract between a planner (mock today, a model later)
and the executor. Unknown fields are rejected, strings are length-limited and
character-limited, so malformed or hostile input never reaches a tool.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ITEM_QUERY_RE = re.compile(r"^[\w\s\-./&']+$")
_ORDER_ID_RE = re.compile(r"^ORD-\d{4}$")
_EXPRESSION_RE = re.compile(r"^[0-9+\-*/().%\s]+$")


class _StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InventoryLookupArgs(_StrictArgs):
    item: str = Field(
        min_length=1,
        max_length=80,
        description="Product name, partial name, or SKU (e.g. 'USB-C Cable' or 'CAB-001').",
    )

    @field_validator("item")
    @classmethod
    def _safe_characters(cls, value: str) -> str:
        if not _ITEM_QUERY_RE.match(value):
            raise ValueError("item may only contain letters, digits, spaces and - _ . / & '")
        return value


class OrderLookupArgs(_StrictArgs):
    order_id: str = Field(description="Order ID in the form ORD-1234.")

    @field_validator("order_id")
    @classmethod
    def _normalise_and_check(cls, value: str) -> str:
        value = value.upper()
        if not _ORDER_ID_RE.match(value):
            raise ValueError("order_id must look like ORD-1234 (ORD- followed by 4 digits)")
        return value


class CalculatorArgs(_StrictArgs):
    expression: str = Field(
        min_length=1,
        max_length=200,
        description="Arithmetic using numbers, + - * / % ( ) and decimal points. '%' is modulo.",
    )

    @field_validator("expression")
    @classmethod
    def _allowed_characters(cls, value: str) -> str:
        if not _EXPRESSION_RE.match(value):
            raise ValueError("expression may only contain digits, spaces and + - * / % ( ) .")
        return value


# ----- shared result models ---------------------------------------------------

class FieldIssue(BaseModel):
    """One human-readable validation problem."""

    field: str
    problem: str


class ToolOutcome(BaseModel):
    """What a tool returns. `code` is a stable machine-readable label."""

    ok: bool
    code: Literal[
        "ok",
        "not_found",
        "invalid_expression",
        "division_by_zero",
        "out_of_range",
    ]
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A proposed tool call, exactly as a planner (or later a model) emits it."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
