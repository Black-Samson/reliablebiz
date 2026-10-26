"""Safe tool executor: allow-list lookup -> schema validation -> execution.

A planner (mock now, a model later) only *proposes* a call. This module is the
single place where a call is allowed to run, and it never raises to the caller.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from .datastore import DataStore
from .schemas import FieldIssue, ToolOutcome
from .tools import TOOL_REGISTRY

logger = logging.getLogger("reliablebiz.executor")

ExecutionStatus = Literal["executed", "rejected_unknown_tool", "invalid_arguments", "tool_error"]


class ExecutionResult(BaseModel):
    status: ExecutionStatus
    tool_name: str
    validated_arguments: dict[str, Any] | None = None
    issues: list[FieldIssue] = Field(default_factory=list)
    outcome: ToolOutcome | None = None

    @property
    def validation_passed(self) -> bool:
        return self.status in ("executed", "tool_error")


def _friendly_issues(err: ValidationError) -> list[FieldIssue]:
    issues: list[FieldIssue] = []
    for e in err.errors():
        field = ".".join(str(p) for p in e.get("loc", ())) or "(arguments)"
        kind = e.get("type", "")
        if kind == "missing":
            problem = "this field is required but was not provided"
        elif kind == "extra_forbidden":
            problem = "unexpected field (not part of this tool's schema)"
        else:
            problem = str(e.get("msg", "invalid value")).removeprefix("Value error, ")
        issues.append(FieldIssue(field=field, problem=problem))
    return issues


def execute_tool_call(name: Any, arguments: Any, store: DataStore) -> ExecutionResult:
    """Validate and run one proposed tool call. Never raises."""
    tool_name = name if isinstance(name, str) else repr(name)

    spec = TOOL_REGISTRY.get(name) if isinstance(name, str) else None
    if spec is None:
        return ExecutionResult(
            status="rejected_unknown_tool",
            tool_name=tool_name,
            issues=[FieldIssue(field="tool", problem=f"'{tool_name}' is not an allowed tool")],
        )

    if not isinstance(arguments, dict):
        return ExecutionResult(
            status="invalid_arguments",
            tool_name=tool_name,
            issues=[FieldIssue(field="(arguments)", problem="arguments must be a JSON object")],
        )

    try:
        validated = spec.args_model.model_validate(arguments)
    except ValidationError as err:
        return ExecutionResult(status="invalid_arguments", tool_name=tool_name, issues=_friendly_issues(err))

    validated_dict = validated.model_dump()
    try:
        outcome = spec.handler(validated, store)
    except Exception:  # last-resort guard: a tool bug must not crash the app
        logger.exception("Tool %s raised unexpectedly", tool_name)
        return ExecutionResult(
            status="tool_error",
            tool_name=tool_name,
            validated_arguments=validated_dict,
            issues=[FieldIssue(field="(tool)", problem="the tool failed unexpectedly")],
        )
    return ExecutionResult(
        status="executed", tool_name=tool_name, validated_arguments=validated_dict, outcome=outcome
    )
