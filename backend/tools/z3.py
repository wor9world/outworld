"""`z3` tool: SMT-LIB in, sat/unsat plus a model out."""

from __future__ import annotations

from typing import Any

import z3

from .registry import register_tool


@register_tool(name="z3", description="Solve an SMT-LIB2 formula with the z3 solver")
def run(smt2: str) -> dict[str, Any]:
    if not isinstance(smt2, str) or not smt2.strip():
        return {"ok": False, "data": None, "meta": {}, "error": "smt2_required"}
    try:
        clauses = z3.parse_smt2_string(smt2)
        solver = z3.Solver()
        solver.add(clauses)
        result = solver.check()
    except z3.Z3Exception as exc:
        return {"ok": False, "data": None, "meta": {}, "error": f"z3_error: {exc}"}
    except Exception as exc:
        return {"ok": False, "data": None, "meta": {}, "error": f"{type(exc).__name__}: {exc}"}

    data: dict[str, Any] = {"status": str(result)}
    if result == z3.sat:
        model = solver.model()
        data["model"] = {str(decl.name()): str(model[decl]) for decl in model.decls()}
    return {"ok": True, "data": data, "meta": {}, "error": None}
