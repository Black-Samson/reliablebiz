import pytest
from pydantic import ValidationError

from reliablebiz.schemas import CalculatorArgs, InventoryLookupArgs, OrderLookupArgs


def test_order_id_is_normalised_to_uppercase():
    assert OrderLookupArgs(order_id=" ord-1001 ").order_id == "ORD-1001"


@pytest.mark.parametrize("bad", ["1001", "ORD-12", "ORD-12345", "ORD-ABCD", "", "ORD-1001; DROP TABLE"])
def test_bad_order_ids_rejected(bad):
    with pytest.raises(ValidationError):
        OrderLookupArgs(order_id=bad)


def test_missing_required_fields_rejected():
    for model in (OrderLookupArgs, InventoryLookupArgs, CalculatorArgs):
        with pytest.raises(ValidationError):
            model()


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        OrderLookupArgs(order_id="ORD-1001", refund=True)


@pytest.mark.parametrize("bad", ["'; DROP TABLE items; --", "cable<script>", "x" * 81, "   "])
def test_inventory_item_rejects_hostile_or_oversized_text(bad):
    with pytest.raises(ValidationError):
        InventoryLookupArgs(item=bad)


def test_calculator_rejects_letters_and_calls():
    for bad in ("abs(3)", "2 ** a", "__import__('os')"):
        with pytest.raises(ValidationError):
            CalculatorArgs(expression=bad)
