"""Planner interface plus the MOCK/DEMO planner.

!! The MockPlanner is a hand-written keyword/regex router. It is NOT a language
!! model and NOT fine-tuned. It exists so the rest of the app can be built and
!! tested. A real model planner can later implement the same `Planner` protocol.
"""

from __future__ import annotations

import re
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class PlanResult(BaseModel):
    """What any planner returns for one user message."""

    action: Literal["call_tool", "clarify", "refuse"]
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None  # used for clarify / refuse
    rationale: str = ""


class Planner(Protocol):
    name: str
    is_fine_tuned: bool

    def plan(self, user_text: str) -> PlanResult: ...


# ----- patterns ---------------------------------------------------------------

_UNSAFE = re.compile(
    r"\b(refund|cancel|delete|remove|update|change|edit|modify|pay|payment|charge|"
    r"transfer|ship\s+it|dispatch|email|send|reorder|re-order|buy|purchase|"
    r"place\s+an?\s+order|create\s+an?\s+order|sudo|powershell|bash|cmd|shell|exec|"
    r"eval|drop\s+table|select\s+\*|insert\s+into|rm\s+-rf|password|api\s*key)\b",
    re.IGNORECASE,
)
_ORDER_ID = re.compile(r"\bORD[-\s]?(\d{1,8})\b", re.IGNORECASE)
_ORDER_WORD_NUM = re.compile(r"\border\s*(?:number|no\.?|#)?\s*#?\s*(\d{1,8})\b", re.IGNORECASE)
_SKU = re.compile(r"\b[A-Za-z]{3}-\d{3}\b")
_PERCENT_OF = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_CALC_TRIGGER = re.compile(
    r"^\s*(?:please\s+)?(?:calculate|compute|work\s+out|what\s+is|what's|whats|how\s+much\s+is)\b[:\s]*(.*)$",
    re.IGNORECASE,
)
_MATH_SPAN = re.compile(r"[\d\s+\-*/().%]*\d[\d\s+\-*/().%]*")
_WORD_OPS = [
    (re.compile(r"\bmultiplied\s+by\b|\btimes\b", re.IGNORECASE), "*"),
    (re.compile(r"\bdivided\s+by\b|\bover\b", re.IGNORECASE), "/"),
    (re.compile(r"\bplus\b", re.IGNORECASE), "+"),
    (re.compile(r"\bminus\b", re.IGNORECASE), "-"),
]
_STOCK_PATTERNS = [
    re.compile(r"how\s+many\s+(?:units\s+of\s+)?(.+?)\s+(?:do\s+we\s+have|are\s+(?:in\s+stock|left|available)|in\s+stock|left|available)\b", re.IGNORECASE),
    re.compile(r"(?:do\s+we\s+have|have\s+we\s+got|is\s+there|are\s+there)\s+(?:any\s+)?(.+?)(?:\s+in\s+stock)?\s*\??\s*$", re.IGNORECASE),
    re.compile(r"(?:is|are)\s+(.+?)\s+(?:in\s+stock|available)\b", re.IGNORECASE),
    re.compile(r"(?:stock|inventory|quantity|availability)\s+(?:levels?\s+)?(?:of|for|on)?\s*(.+)$", re.IGNORECASE),
]
_STOCK_HINT = re.compile(r"\b(stock|inventory|in\s+stock|how\s+many|do\s+we\s+have|available|availability|quantity|units)\b", re.IGNORECASE)
_ORDER_HINT = re.compile(r"\b(order|tracking|track|shipment|delivery)\b", re.IGNORECASE)
_LEADING_JUNK = re.compile(r"^(?:the|a|an|any|some|units?\s+of)\s+", re.IGNORECASE)

SUPPORTED_HELP = (
    "I can look up inventory (e.g. 'Do we have USB-C cables in stock?'), "
    "look up an order (e.g. 'Where is order ORD-1001?'), or do arithmetic "
    "(e.g. 'Calculate 12 * 3.5')."
)


def _clean_item(text: str) -> str:
    text = text.strip().strip("?.!,;:\"' ")
    prev = None
    while prev != text:  # strip stacked filler words ("any units of ...")
        prev = text
        text = _LEADING_JUNK.sub("", text).strip()
    return text


def _extract_expression(remainder: str) -> str:
    remainder = remainder.strip().rstrip("?=").strip()
    percent = _PERCENT_OF.search(remainder)
    if percent:
        return f"{percent.group(2)} * {percent.group(1)} / 100"
    text = remainder.replace("×", "*").replace("÷", "/").replace("^", "**")
    for pattern, symbol in _WORD_OPS:
        text = pattern.sub(f" {symbol} ", text)
    text = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", " * ", text)
    candidates = [m.group(0).strip() for m in _MATH_SPAN.finditer(text)]
    with_operator = [c for c in candidates if re.search(r"[+\-*/%]", c)]
    pool = with_operator or candidates
    if pool:
        return re.sub(r"\s+", " ", max(pool, key=len)).strip()
    return remainder  # nothing numeric found: let the validator reject it


class MockPlanner:
    """Deterministic keyword/regex planner used for demos and tests."""

    name = "MOCK demo planner (rule-based)"
    is_fine_tuned = False

    def plan(self, user_text: str) -> PlanResult:
        text = (user_text or "").strip()
        if not text:
            return PlanResult(action="clarify", message="Please type a request. " + SUPPORTED_HELP,
                              rationale="Empty input.")

        if _UNSAFE.search(text):
            return PlanResult(
                action="refuse",
                message=(
                    "I can't do that. ReliableBiz is read-only: it can look things up and do "
                    "arithmetic, but it cannot change data, make payments, send messages or run commands."
                ),
                rationale="Request matched an unsafe/unauthorised action keyword; no tool was selected.",
            )

        order_match = _ORDER_ID.search(text) or _ORDER_WORD_NUM.search(text)
        if order_match or (_ORDER_HINT.search(text) and not _CALC_TRIGGER.match(text) and not _SKU.search(text)):
            if order_match:
                digits = order_match.group(1)
                return PlanResult(
                    action="call_tool", tool_name="order_lookup",
                    arguments={"order_id": f"ORD-{digits}"},
                    rationale="Found an order number, so selected order_lookup.",
                )
            return PlanResult(
                action="call_tool", tool_name="order_lookup", arguments={},
                rationale="Looks like an order question but no order ID was found; the validator will flag the missing field.",
            )

        calc = _CALC_TRIGGER.match(text)
        if calc or _PERCENT_OF.search(text) or re.search(r"\d\s*[-+*/×÷]\s*\d", text):
            remainder = calc.group(1) if calc else text
            if calc and not re.search(r"\d", remainder) and _STOCK_HINT.search(text):
                pass  # "what is the stock of X" is an inventory question, handled below
            else:
                expression = _extract_expression(remainder)
                args = {"expression": expression} if expression else {}
                return PlanResult(
                    action="call_tool", tool_name="calculator", arguments=args,
                    rationale="Looks like arithmetic, so selected calculator.",
                )

        sku = _SKU.search(text)
        if sku:
            return PlanResult(action="call_tool", tool_name="inventory_lookup",
                              arguments={"item": sku.group(0).upper()},
                              rationale="Found a SKU, so selected inventory_lookup.")
        if _STOCK_HINT.search(text):
            for pattern in _STOCK_PATTERNS:
                found = pattern.search(text)
                if found:
                    item = _clean_item(found.group(1))
                    if item:
                        return PlanResult(action="call_tool", tool_name="inventory_lookup",
                                          arguments={"item": item},
                                          rationale="Looks like a stock question, so selected inventory_lookup.")
            return PlanResult(action="call_tool", tool_name="inventory_lookup", arguments={},
                              rationale="Looks like a stock question but no product was found; the validator will flag the missing field.")

        return PlanResult(
            action="clarify",
            message="I'm not sure what you'd like me to do. " + SUPPORTED_HELP,
            rationale="No tool matched this request.",
        )
