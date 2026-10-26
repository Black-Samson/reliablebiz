from reliablebiz.executor import execute_tool_call
from reliablebiz.tools import TOOL_REGISTRY, tool_catalog


def test_registry_is_exactly_the_three_allowed_tools():
    assert set(TOOL_REGISTRY) == {"inventory_lookup", "order_lookup", "calculator"}
    assert {t["name"] for t in tool_catalog()} == set(TOOL_REGISTRY)


def test_inventory_found_by_name_and_sku(store):
    by_name = execute_tool_call("inventory_lookup", {"item": "usb-c cable"}, store)
    by_sku = execute_tool_call("inventory_lookup", {"item": "cab-001"}, store)
    assert by_name.status == by_sku.status == "executed"
    assert by_name.outcome.data["items"][0]["sku"] == "CAB-001"
    assert by_sku.outcome.data["items"][0]["quantity"] == 120


def test_inventory_nonexistent_item_is_not_found(store):
    res = execute_tool_call("inventory_lookup", {"item": "flux capacitor"}, store)
    assert res.status == "executed"
    assert res.outcome.ok is False and res.outcome.code == "not_found"


def test_inventory_out_of_stock_status(store):
    res = execute_tool_call("inventory_lookup", {"item": "PWR-001"}, store)
    assert res.outcome.data["items"][0]["stock_status"] == "out_of_stock"


def test_order_lookup_success(store):
    res = execute_tool_call("order_lookup", {"order_id": "ord-1001"}, store)
    assert res.outcome.ok and res.outcome.data["status"] == "shipped"
    assert res.validated_arguments == {"order_id": "ORD-1001"}


def test_unknown_order_id_is_not_found(store):
    res = execute_tool_call("order_lookup", {"order_id": "ORD-9999"}, store)
    assert res.status == "executed" and res.outcome.code == "not_found"


def test_missing_and_invalid_arguments_block_execution(store):
    missing = execute_tool_call("order_lookup", {}, store)
    invalid = execute_tool_call("order_lookup", {"order_id": "banana"}, store)
    for res in (missing, invalid):
        assert res.status == "invalid_arguments"
        assert res.outcome is None
        assert res.issues
    assert "required" in missing.issues[0].problem


def test_unknown_or_dangerous_tool_names_are_rejected(store):
    for name in ("refund_order", "shell", "__import__", "", None, 42):
        res = execute_tool_call(name, {"x": 1}, store)
        assert res.status == "rejected_unknown_tool"
        assert res.outcome is None


def test_non_dict_arguments_rejected(store):
    assert execute_tool_call("calculator", "2+2", store).status == "invalid_arguments"
    assert execute_tool_call("calculator", ["2+2"], store).status == "invalid_arguments"


def test_calculator_through_executor(store):
    ok = execute_tool_call("calculator", {"expression": "12 * 3.5"}, store)
    assert ok.outcome.data["result"] == "42"
    zero = execute_tool_call("calculator", {"expression": "1 / 0"}, store)
    assert zero.outcome.code == "division_by_zero"
    bad = execute_tool_call("calculator", {"expression": "1.2.3 + 1"}, store)
    assert bad.outcome.code == "invalid_expression"
    code = execute_tool_call("calculator", {"expression": "__import__('os')"}, store)
    assert code.status == "invalid_arguments"


def test_tool_crash_is_contained(store, monkeypatch):
    from reliablebiz import tools
    from dataclasses import replace

    def boom(args, store):
        raise RuntimeError("bug")

    monkeypatch.setitem(tools.TOOL_REGISTRY, "calculator", replace(tools.TOOL_REGISTRY["calculator"], handler=boom))
    res = execute_tool_call("calculator", {"expression": "1+1"}, store)
    assert res.status == "tool_error" and res.outcome is None
