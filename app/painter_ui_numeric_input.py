"""Safe arithmetic evaluation for Figma-style Painter numeric fields."""
from __future__ import annotations

import ast
import math
import operator


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _evaluate_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(
        node.value,
        (int, float),
    ):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        return float(
            _BINARY_OPERATORS[type(node.op)](
                _evaluate_node(node.left),
                _evaluate_node(node.right),
            )
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return float(
            _UNARY_OPERATORS[type(node.op)](
                _evaluate_node(node.operand)
            )
        )
    raise ValueError("numeric input supports numbers and + - * / only")


def evaluate_painter_numeric_input(
    text: str,
    *,
    origin: float,
) -> float:
    expression = str(text or "").strip().replace("×", "*").replace("÷", "/")
    if not expression:
        raise ValueError("numeric input is empty")
    if expression.endswith("%"):
        percentage = evaluate_painter_numeric_input(
            expression[:-1],
            origin=origin,
        )
        result = float(origin) * percentage / 100.0
    else:
        if expression[0] in {"+", "*", "/"}:
            expression = f"({float(origin)}){expression}"
        try:
            tree = ast.parse(expression, mode="eval")
            result = _evaluate_node(tree)
        except (SyntaxError, TypeError, ZeroDivisionError) as exc:
            raise ValueError("invalid numeric expression") from exc
    if not math.isfinite(result):
        raise ValueError("numeric expression must be finite")
    return float(result)
