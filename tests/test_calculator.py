import pytest

from reliablebiz.calculator import CalculatorError, calculate


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("2 + 3", "5"),
        ("12 * 3.5 + 4", "46"),
        ("0.1 + 0.2", "0.3"),
        ("(2 + 3) * 4", "20"),
        ("-5 + 2", "-3"),
        ("10 / 4", "2.5"),
        ("10 // 3", "3"),
        ("10 % 3", "1"),
        ("1 / 3", "0.3333333333"),
    ],
)
def test_valid_expressions(expr, expected):
    assert calculate(expr) == expected


def test_division_by_zero_is_reported():
    with pytest.raises(CalculatorError) as err:
        calculate("10 / 0")
    assert err.value.code == "division_by_zero"


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('echo hi')",
        "open('x')",
        "abs(-1)",
        "a + 1",
        "'a' * 3",
        "True + 1",
        "1 +",
        "1.2.3 + 4",
        "",
        "   ",
        "2 ** 10",
        "(1 if 1 else 2)",
        "[1, 2]",
        "1; 2",
    ],
)
def test_unsafe_or_invalid_expressions_are_rejected(expr):
    with pytest.raises(CalculatorError) as err:
        calculate(expr)
    assert err.value.code == "invalid_expression"


def test_huge_results_are_rejected():
    with pytest.raises(CalculatorError) as err:
        calculate("999999999999 * 999999999999")
    assert err.value.code == "out_of_range"


def test_overlong_and_deeply_nested_input_is_rejected():
    with pytest.raises(CalculatorError):
        calculate("1+" * 150 + "1")
    with pytest.raises(CalculatorError):
        calculate("(" * 100 + "1" + ")" * 100)
