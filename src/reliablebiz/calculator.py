"""Safe arithmetic evaluator. Parses with `ast` and walks an allow-list of nodes.

There is no eval()/exec(), no names, no attribute access and no function calls:
anything that is not a plain number or an allowed operator is rejected.
Decimal arithmetic avoids float artefacts such as 0.1 + 0.2 = 0.30000000000000004.
"""

from __future__ import annotations

import ast
import decimal
import operator
from decimal import Decimal

MAX_EXPRESSION_CHARS = 200
MAX_ABS_RESULT = Decimal("1e15")
MAX_EXPONENT = 100
MAX_DEPTH = 40


class CalculatorError(Exception):
    """Raised for any expression we refuse or cannot compute."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _check_range(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise CalculatorError("out_of_range", "The result is not a finite number.")
    if abs(value) > MAX_ABS_RESULT:
        raise CalculatorError("out_of_range", "The result is too large (limit is 1e15).")
    return value


def _eval_node(node: ast.AST, depth: int = 0) -> Decimal:
    if depth > MAX_DEPTH:
        raise CalculatorError("invalid_expression", "The expression is nested too deeply.")

    if isinstance(node, ast.Expression):
        return _eval_node(node.body, depth + 1)

    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CalculatorError("invalid_expression", "Only plain numbers are allowed.")
        try:
            number = Decimal(str(value))
        except decimal.InvalidOperation as exc:
            raise CalculatorError("invalid_expression", "Invalid number.") from exc
        return _check_range(number)

    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _check_range(_UNARY_OPS[type(node.op)](_eval_node(node.operand, depth + 1)))

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, depth + 1)
        right = _eval_node(node.right, depth + 1)
        op_type = type(node.op)
        if op_type is ast.Pow:  # '**' passes the character filter, so reject it explicitly
            raise CalculatorError("invalid_expression", "Exponent (**) is not supported.")
        if op_type not in _BINARY_OPS:
            raise CalculatorError("invalid_expression", "That operator is not supported.")
        try:
            return _check_range(_BINARY_OPS[op_type](left, right))
        except decimal.DivisionByZero as exc:
            raise CalculatorError("division_by_zero", "Division by zero is not allowed.") from exc
        except ZeroDivisionError as exc:
            raise CalculatorError("division_by_zero", "Division by zero is not allowed.") from exc
        except ArithmeticError as exc:
            raise CalculatorError("out_of_range", "That calculation is out of range.") from exc

    raise CalculatorError("invalid_expression", "Only numbers and + - * / % ( ) are allowed.")


def _format(value: Decimal) -> str:
    quantised = value.quantize(Decimal("0.0000000001"))
    if quantised == 0:
        return "0"
    return format(quantised.normalize(), "f")


def calculate(expression: str) -> str:
    """Evaluate `expression` safely and return the result as a plain string."""
    if not isinstance(expression, str) or not expression.strip():
        raise CalculatorError("invalid_expression", "The expression is empty.")
    if len(expression) > MAX_EXPRESSION_CHARS:
        raise CalculatorError("invalid_expression", "The expression is too long.")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise CalculatorError("invalid_expression", "That is not a valid arithmetic expression.") from exc
    except (RecursionError, MemoryError) as exc:
        raise CalculatorError("invalid_expression", "The expression is too complex.") from exc
    try:
        with decimal.localcontext() as ctx:
            ctx.prec = 28
            return _format(_eval_node(tree))
    except RecursionError as exc:
        raise CalculatorError("invalid_expression", "The expression is too complex.") from exc
    except decimal.InvalidOperation as exc:
        raise CalculatorError("out_of_range", "That calculation is out of range.") from exc
