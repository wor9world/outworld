"""`calc` tool: exact arithmetic and equation solving via sympy.

Two measured facts drive this module:

* ``parse_expr`` without ``rationalize`` turns ``9.8-9.11`` into the float
  ``0.690000000000001``; with it the answer is exactly ``69/100``.
* ``solve(3**x - x**9)`` returns ``[27, LambertW branch]``; a numeric grid scan finds
  the same roots independently and catches branches ``solve`` omits.
"""

from __future__ import annotations

from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    rationalize,
    standard_transformations,
)

from .registry import register_tool

NAMESPACE: dict[str, Any] = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "sqrt": sp.sqrt,
    "log": sp.log,
    "exp": sp.exp,
    "pi": sp.pi,
    "E": sp.E,
    "I": sp.I,
    "Eq": sp.Eq,
    "Abs": sp.Abs,
    "factorial": sp.factorial,
    "Rational": sp.Rational,
}

TRANSFORMS = standard_transformations + (rationalize,)
MAX_GRID = 40.0
STEP = 0.1
TOL = 1e-6


def parse(expr: str, var: sp.Symbol) -> Any:
    local = {**NAMESPACE, str(var): var}
    return parse_expr(expr, local_dict=local, transformations=TRANSFORMS)


def _num(value: Any) -> float | None:
    try:
        number = float(sp.N(value, 15))
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # reject NaN


def _render(value: float) -> str:
    return f"{value:.12g}"


def _grid_roots(f: Any, var: sp.Symbol) -> list[float]:
    import math

    try:
        numeric = sp.lambdify(var, f, modules=["math"])
    except Exception:  # noqa: BLE001 - a non-lambdifiable expression simply has no scan
        return []
    points: list[tuple[float, float]] = []
    value = STEP
    while value <= MAX_GRID:
        try:
            result = float(numeric(value))
        except Exception:  # noqa: BLE001 - domain errors are expected mid-scan
            value += STEP
            continue
        if math.isfinite(result):
            points.append((value, result))
        value += STEP

    roots: list[float] = []
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if y0 == 0:
            roots.append(x0)
            continue
        if y0 * y1 < 0:
            try:
                root = sp.nsolve(f, (x0 + x1) / 2)
                number = _num(root)
                if number is not None:
                    roots.append(number)
            except Exception:  # noqa: BLE001 - skip brackets nsolve cannot refine
                continue
    return roots


def _dedupe(values: list[float]) -> list[float]:
    out: list[float] = []
    for value in sorted(values):
        if not out or abs(value - out[-1]) > TOL:
            out.append(value)
    return out


def evaluate(expr: str) -> dict[str, Any]:
    var = sp.Symbol("x")
    parsed = parse(expr, var)
    simplified = sp.simplify(parsed)
    numeric = _num(simplified)
    return {
        "exact": str(simplified) if not simplified.free_symbols else None,
        "result": numeric if numeric is not None else str(simplified),
        "input": expr,
    }


def solve_equation(expr: str, var_name: str = "x") -> dict[str, Any]:
    var = sp.Symbol(var_name)
    parsed = parse(expr, var)
    equation = parsed if isinstance(parsed, sp.Eq) else sp.Eq(parsed, 0)
    residual = sp.simplify(equation.lhs - equation.rhs)

    exact_roots: list[Any] = []
    try:
        exact_roots = list(sp.solve(equation, var))
    except Exception:  # noqa: BLE001 - solve is best-effort; the scan is the fallback
        exact_roots = []

    real: list[float] = []
    exact_text: list[str] = []
    for root in exact_roots:
        exact_text.append(str(root))
        value = _num(root)
        if value is not None:
            real.append(value)

    scan = _grid_roots(residual, var)
    roots = _dedupe(real + scan)
    return {
        "var": var_name,
        "expr": expr,
        "roots": [_render(root) for root in roots],
        "exact": exact_text[:4],
        "methods": {"solve": len(real), "scan": len(scan)},
    }


@register_tool(name="calc", description="Exact arithmetic and equation solving with sympy")
def run(op: str = "eval", expr: str = "", var: str = "x") -> dict[str, Any]:
    if not isinstance(expr, str) or not expr.strip():
        return {"ok": False, "data": None, "meta": {}, "error": "expr_required"}
    try:
        if op == "eval":
            data = evaluate(expr)
        elif op == "solve":
            data = solve_equation(expr, var or "x")
        else:
            return {"ok": False, "data": None, "meta": {}, "error": f"unknown_op:{op}"}
    except Exception as exc:  # noqa: BLE001 - sympy raises many shapes; none may escape
        return {"ok": False, "data": None, "meta": {"op": op}, "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "data": data, "meta": {"op": op}, "error": None}
