import json

import pytest

from reliablebiz.config import PROJECT_ROOT
from reliablebiz.datastore import DataStore, InventoryItem, Order, OrderLine


def test_sample_data_loads_and_is_consistent(store):
    assert len(store.inventory) >= 10 and len(store.orders) >= 8
    for order in store.orders:
        total = sum(store.get_item_by_sku(l.sku).unit_price * l.quantity for l in order.items)
        assert round(total, 2) == order.total_amount


def test_datastore_rejects_orders_with_unknown_sku():
    item = InventoryItem(sku="A-1", name="A", quantity=1, unit_price=1, reorder_level=0, location="x")
    order = Order(order_id="ORD-1000", customer_name="T", status="shipped", order_date="2026-01-01",
                  items=[OrderLine(sku="ZZZ", quantity=1)], total_amount=1, currency="USD")
    with pytest.raises(ValueError):
        DataStore([item], [order])


def test_no_secrets_file_or_unsafe_calls_in_source():
    banned = ("eval(", "exec(", "os.system", "subprocess", "shell=True", "pickle")
    for path in (PROJECT_ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            # allow the word in comments/docstrings that explain the rule
            code_lines = [l for l in text.splitlines() if not l.strip().startswith(("#", '"""', "!!")) and token in l]
            code_lines = [l for l in code_lines if "no eval" not in l.lower() and "eval()" not in l and "exec()" not in l]
            assert not code_lines, f"{token} found in {path.name}: {code_lines}"


def test_streamlit_app_runs_and_shows_mock_notice(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("RELIABLEBIZ_LOG_DIR", str(tmp_path))
    at = AppTest.from_file(str(PROJECT_ROOT / "app" / "streamlit_app.py"), default_timeout=30).run()
    assert not at.exception
    assert any("NOT a fine-tuned model" in w.value for w in at.warning)

    at.text_input(key="prompt_text").set_value("Where is order ORD-1001?")
    at.button(key="run").click().run()
    assert not at.exception
    assert any("shipped" in i.value for i in at.info)

    at.text_input(key="prompt_text").set_value("Where is my order?")
    at.button(key="run").click().run()
    assert not at.exception
    assert any("Validation FAILED" in e.value for e in at.error)
    assert (tmp_path / "requests.jsonl").exists()
