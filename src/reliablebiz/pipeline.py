"""Request pipeline: planner -> (validate + execute) -> answer -> log.

This module knows nothing about Streamlit or about how a planner works, so a
trained model can be dropped in later by implementing `Planner.plan`.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from .answers import compose_answer
from .datastore import DataStore
from .executor import ExecutionResult, execute_tool_call
from .planner import Planner, PlanResult
from .request_log import RequestLogger


class RequestTrace(BaseModel):
    request_id: str
    timestamp_utc: str
    user_input: str
    planner_name: str
    planner_is_fine_tuned: bool
    plan: PlanResult
    execution: ExecutionResult | None = None
    final_answer: str
    latency_ms: float


def handle_request(
    user_text: str,
    planner: Planner,
    store: DataStore,
    logger: RequestLogger | None = None,
    max_input_chars: int = 500,
) -> RequestTrace:
    started = time.perf_counter()
    text = (user_text or "").strip()

    if len(text) > max_input_chars:
        plan = PlanResult(
            action="clarify",
            message=f"That request is too long (limit {max_input_chars} characters). Please shorten it.",
            rationale="Input exceeded the length limit; the planner was not called.",
        )
    else:
        plan = planner.plan(text)

    execution: ExecutionResult | None = None
    if plan.action == "call_tool":
        execution = execute_tool_call(plan.tool_name, plan.arguments, store)
        answer = compose_answer(execution)
    else:
        answer = plan.message or ""

    trace = RequestTrace(
        request_id=uuid.uuid4().hex[:12],
        timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        user_input=text[:max_input_chars],
        planner_name=planner.name,
        planner_is_fine_tuned=planner.is_fine_tuned,
        plan=plan,
        execution=execution,
        final_answer=answer,
        latency_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    if logger is not None:
        logger.write(trace.model_dump(mode="json"))
    return trace
