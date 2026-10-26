import json

import pytest

from reliablebiz.pipeline import handle_request
from reliablebiz.planner import MockPlanner
from reliablebiz.request_log import RequestLogger

planner = MockPlanner()


def test_mock_planner_is_labelled_not_fine_tuned():
    assert planner.is_fine_tuned is False
    assert "MOCK" in planner.name


@pytest.mark.parametrize(
    "text,tool,args",
    [
        ("Where is order ORD-1001?", "order_lookup", {"order_id": "ORD-1001"}),
        ("status of order 1002 please", "order_lookup", {"order_id": "ORD-1002"}),
        ("Do we have USB-C cables in stock?", "inventory_lookup", {"item": "USB-C cables"}),
        ("How many wireless mice are left?", "inventory_lookup", {"item": "wireless mice"}),
        ("stock of CAB-001", "inventory_lookup", {"item": "CAB-001"}),
        ("Calculate 12 * 3.5 + 4", "calculator", {"expression": "12 * 3.5 + 4"}),
        ("What is 15% of 240?", "calculator", {"expression": "240 * 15 / 100"}),
        ("what is 6 times 7", "calculator", {"expression": "6 * 7"}),
    ],
)
def test_planner_routes_to_expected_tool(text, tool, args):
    plan = planner.plan(text)
    assert plan.action == "call_tool"
    assert plan.tool_name == tool
    assert plan.arguments == args


@pytest.mark.parametrize(
    "text",
    ["Refund order ORD-1002", "please delete order ORD-1001", "run a powershell command",
     "DROP TABLE orders", "send an email to the customer", "pay the invoice"],
)
def test_unsafe_requests_are_refused_without_a_tool(text, store):
    trace = handle_request(text, planner, store)
    assert trace.plan.action == "refuse"
    assert trace.execution is None
    assert "can't" in trace.final_answer.lower()


def test_gibberish_and_empty_ask_for_clarification(store):
    for text in ("blah blah", "", "   "):
        trace = handle_request(text, planner, store)
        assert trace.plan.action == "clarify" and trace.execution is None


def test_end_to_end_answers(store):
    assert "shipped" in handle_request("Where is order ORD-1001?", planner, store).final_answer
    assert "46" in handle_request("Calculate 12 * 3.5 + 4", planner, store).final_answer
    assert "OUT OF STOCK" in handle_request("is the power bank available?", planner, store).final_answer
    assert "No order with ID ORD-9999" in handle_request("order ORD-9999", planner, store).final_answer
    assert "No inventory item" in handle_request("do we have flux capacitors in stock", planner, store).final_answer


def test_missing_field_flows_through_validator(store):
    trace = handle_request("Where is my order?", planner, store)
    assert trace.plan.action == "call_tool" and trace.plan.arguments == {}
    assert trace.execution.status == "invalid_arguments"
    assert "order_id" in trace.final_answer and "required" in trace.final_answer


def test_invalid_number_and_div_zero_handled(store):
    assert "zero" in handle_request("calculate 10 / 0", planner, store).final_answer.lower()
    trace = handle_request("calculate 12 / abc", planner, store)
    assert trace.execution.outcome is None or not trace.execution.outcome.ok


def test_overlong_input_rejected_before_planner(store):
    trace = handle_request("calculate " + "1+" * 400 + "1", planner, store, max_input_chars=100)
    assert trace.plan.action == "clarify" and "too long" in trace.final_answer


def test_requests_are_logged_as_jsonl(store, tmp_path):
    log = RequestLogger(tmp_path)
    handle_request("Where is order ORD-1001?", planner, store, log)
    handle_request("Refund order ORD-1002", planner, store, log)
    lines = log.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["plan"]["tool_name"] == "order_lookup"
    assert first["planner_is_fine_tuned"] is False
    assert json.loads(lines[1])["plan"]["action"] == "refuse"


def test_logger_failure_does_not_break_requests(store, tmp_path):
    blocker = tmp_path / "file.txt"
    blocker.write_text("x", encoding="utf-8")
    log = RequestLogger(blocker)  # a *file* where a directory is needed
    trace = handle_request("order ORD-1001", planner, store, log)
    assert "shipped" in trace.final_answer
