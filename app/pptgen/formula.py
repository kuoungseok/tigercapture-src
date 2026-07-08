"""Small spreadsheet-style formula helpers for PPT table and chart data."""
from __future__ import annotations

import ast
import operator
import re
from collections.abc import Sequence
from typing import Any


_CELL_RE = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")
_OPS: dict[type[ast.operator], object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY_OPS: dict[type[ast.unaryop], object] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _column_index(text: str) -> int:
    total = 0
    for char in text.upper():
        total = total * 26 + (ord(char) - ord("A") + 1)
    return total - 1


def _cell_raw_value(ref: str, cells: Sequence[Sequence[Any]] | None) -> Any:
    match = _CELL_RE.match(str(ref or "").upper())
    if not match or cells is None:
        raise ValueError(f"unknown cell reference: {ref}")
    col = _column_index(match.group(1))
    row = int(match.group(2)) - 1
    try:
        return cells[row][col]
    except Exception as exc:
        raise ValueError(f"cell reference out of range: {ref}") from exc


def _flatten(values: Sequence[Any]) -> list[float]:
    out: list[float] = []
    for value in values:
        if isinstance(value, (list, tuple)):
            out.extend(_flatten(value))
        else:
            out.append(float(value))
    return out


def _call(name: str, values: Sequence[Any]) -> float:
    nums = _flatten(values)
    upper = name.upper()
    if upper == "SUM":
        return float(sum(nums))
    if upper in {"AVG", "AVERAGE"}:
        return float(sum(nums) / max(1, len(nums)))
    if upper == "MIN":
        return float(min(nums)) if nums else 0.0
    if upper == "MAX":
        return float(max(nums)) if nums else 0.0
    if upper == "ROUND":
        if not nums:
            return 0.0
        digits = int(nums[1]) if len(nums) > 1 else 0
        return float(round(nums[0], digits))
    if upper == "ABS":
        return float(abs(nums[0])) if nums else 0.0
    raise ValueError(f"unsupported formula function: {name}")


def _eval_node(node: ast.AST, cells: Sequence[Sequence[Any]] | None, stack: set[str]) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, cells, stack)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return float(_UNARY_OPS[type(node.op)](_eval_node(node.operand, cells, stack)))  # type: ignore[index]
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left = _eval_node(node.left, cells, stack)
        right = _eval_node(node.right, cells, stack)
        return float(_OPS[type(node.op)](left, right))  # type: ignore[index]
    if isinstance(node, ast.Name):
        ref = node.id.upper()
        if ref in stack:
            raise ValueError(f"circular cell reference: {ref}")
        raw = _cell_raw_value(ref, cells)
        return evaluate_numeric_formula(raw, cells=cells, stack={*stack, ref})
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        args = [_eval_node(arg, cells, stack) for arg in node.args]
        return _call(node.func.id, args)
    raise ValueError("unsupported formula syntax")


def evaluate_numeric_formula(
    value: Any,
    *,
    cells: Sequence[Sequence[Any]] | None = None,
    fallback: float = 0.0,
    stack: set[str] | None = None,
) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return float(fallback)
    if not text.startswith("="):
        try:
            return float(text.replace(",", ""))
        except Exception:
            return float(fallback)
    expression = text[1:].strip()
    if not expression:
        return float(fallback)
    tree = ast.parse(expression, mode="eval")
    return float(_eval_node(tree, cells, set(stack or set())))


def format_formula_value(value: Any, *, cells: Sequence[Sequence[Any]] | None = None) -> str:
    text = str(value or "")
    if not text.strip().startswith("="):
        return text
    try:
        number = evaluate_numeric_formula(text, cells=cells)
    except Exception:
        return "#ERR"
    if abs(number - round(number)) < 1e-7:
        return str(int(round(number)))
    return f"{number:.2f}".rstrip("0").rstrip(".")


__all__ = ["evaluate_numeric_formula", "format_formula_value"]
