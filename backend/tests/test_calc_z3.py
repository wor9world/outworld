"""T9 + T10 — calc (exact rationals, solve with scan) and z3."""

from __future__ import annotations


def calc(client, **args):
    return client.post("/api/tools/calc", json=args)


def z3run(client, smt2: str):
    return client.post("/api/tools/z3", json={"smt2": smt2})


def test_float_difference_is_exact(client) -> None:
    """The measured case: plain parsing gives 0.690000000000001, rationalize gives 69/100."""
    body = calc(client, op="eval", expr="9.8-9.11").json()
    assert body["ok"] is True
    assert body["data"]["exact"] == "69/100"
    assert abs(body["data"]["result"] - 0.69) < 1e-12


def test_trig_identity(client) -> None:
    body = calc(client, op="eval", expr="simplify(sin(x)**2 + cos(x)**2)").json()
    assert body["data"]["exact"] == "1"


def test_quadratic_roots(client) -> None:
    body = calc(client, op="solve", expr="x**2 - 4").json()
    roots = sorted(float(r) for r in body["data"]["roots"])
    assert roots == [-2.0, 2.0]


def test_transcendental_roots(client) -> None:
    body = calc(client, op="solve", expr="3**x - x**9").json()
    assert body["ok"] is True
    roots = [float(r) for r in body["data"]["roots"]]
    assert any(abs(r - 27.0) < 1e-9 for r in roots), roots
    assert any(abs(r - 1.150824821) < 1e-6 for r in roots), roots


def test_calc_errors_do_not_raise(client) -> None:
    body = calc(client, op="eval", expr="1/0").json()
    assert body["ok"] is True  # sympy returns zoo; it is not a crash
    bad = calc(client, op="eval", expr="1 +").json()
    assert bad["ok"] is False
    assert bad["error"]


def test_z3_unsat(client) -> None:
    assert z3run(client, "(assert false)").json()["data"]["status"] == "unsat"


def test_z3_sat_with_model(client) -> None:
    body = z3run(client, "(declare-const x Int)(assert (> x 5))(check-sat)").json()
    assert body["data"]["status"] == "sat"
    assert int(body["data"]["model"]["x"]) > 5


def test_z3_bad_input(client) -> None:
    body = z3run(client, "(assert (foo)").json()
    assert body["ok"] is False
    assert "z3_error" in body["error"] or "Error" in body["error"]
