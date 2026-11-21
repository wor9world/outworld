"""The pipe: message -> intent -> plan -> tool calls -> answer.

Rules live in ``data/intent.yaml`` and ``data/plan_cheat.yaml``. This module owns only
the matcher, the deterministic slot transforms and the executor (SPEC §14).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from tools import registry

from . import config, toolcall
from .api.tools import audit

TRIGGERS = re.compile(
    r"(?i)^\s*(ช่วยวางแผน|วางแผน|plan|ค้นโน้ต|โน้ต|note|ค้นหา|หา|search|find|"
    r"รันสคริปต์|รันสคริป|run script|script|"
    r"สร้างโปรเจ[คก](?:ต์)?|new project|scaffold|"
    r"ตรวจโปรเจ[คก](?:ต์)?|verify project|test project)\s*"
)

CONDITIONS = ("regex", "not_regex", "contains", "startswith", "equals")
TRANSFORMS = (
    "keep",
    "strip_prefix",
    "strip_question",
    "strip_eq_question",
    "extract_name",
    "extract_template",
    "extract_date",
    "extract_time",
    "extract_location",
)

DATE_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4})"
)
TIME_RE = re.compile(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b")


@dataclass
class Rule:
    id: str
    intent: str
    priority: int
    all: list[dict[str, str]] = field(default_factory=list)
    any: list[dict[str, str]] = field(default_factory=list)
    slots: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class Plan:
    intent: str
    steps: list[dict[str, Any]]
    answer: str


_rules: list[Rule] | None = None
_plans: dict[str, Plan] | None = None
_load_error: str | None = None


def rules_dir() -> Path:
    import os

    return Path(os.environ.get("OUTWORLD_RULES", str(config.ROOT / "data")))


def _check_condition(condition: dict[str, str]) -> None:
    keys = [key for key in condition if key in CONDITIONS]
    if len(keys) != 1:
        raise ValueError(f"condition must have exactly one of {CONDITIONS}: {condition}")


def load_rules() -> list[Rule]:
    path = rules_dir() / "intent.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules: list[Rule] = []
    for item in raw.get("rules", []):
        when = item.get("when", {})
        all_list = when.get("all", []) or []
        any_list = when.get("any", []) or []
        if not all_list and not any_list:
            raise ValueError(f"rule {item.get('id')} has no conditions")
        for condition in [*all_list, *any_list]:
            _check_condition(condition)
        for slot in (item.get("slots") or {}).values():
            transform = slot.get("transform", "keep")
            if transform not in TRANSFORMS:
                raise ValueError(f"rule {item.get('id')} uses unknown transform {transform}")
        rules.append(
            Rule(
                id=str(item["id"]),
                intent=str(item["intent"]),
                priority=int(item.get("priority", 0)),
                all=all_list,
                any=any_list,
                slots=item.get("slots") or {},
            )
        )
    rules.sort(key=lambda rule: -rule.priority)
    return rules


def load_plans() -> dict[str, Plan]:
    path = rules_dir() / "plan_cheat.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tools = set(registry.public_tools())
    plans: dict[str, Plan] = {}
    for intent, item in (raw.get("plans") or {}).items():
        steps = item.get("steps") or []
        if not steps:
            raise ValueError(f"plan {intent} has no steps")
        for step in steps:
            tool = str(step.get("tool", ""))
            if tool not in tools:
                raise ValueError(f"plan_invalid: {intent} -> {tool}")
        plans[str(intent)] = Plan(
            intent=str(intent), steps=steps, answer=str(item.get("answer", ""))
        )
    return plans


def reload() -> dict[str, int]:
    global _rules, _plans, _load_error
    try:
        _rules = load_rules()
        _plans = load_plans()
        _load_error = None
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        _rules, _plans = [], {}
        _load_error = f"{type(exc).__name__}: {exc}"
        raise
    return {"intents": len(_rules), "plans": len(_plans)}


def rules() -> list[Rule]:
    global _rules
    if _rules is None:
        reload()
    return _rules or []


def plans() -> dict[str, Plan]:
    global _plans
    if _plans is None:
        try:
            reload()
        except Exception:
            return {}
    return _plans or {}


def normalize(message: str) -> str:
    return " ".join((message or "").split())


def _match_condition(condition: dict[str, str], message: str) -> bool:
    if "regex" in condition:
        try:
            return re.search(condition["regex"], message) is not None
        except re.error:
            return False
    if "not_regex" in condition:
        try:
            return re.search(condition["not_regex"], message) is None
        except re.error:
            return False
    if "contains" in condition:
        return condition["contains"].casefold() in message.casefold()
    if "startswith" in condition:
        return message.casefold().startswith(condition["startswith"].casefold())
    if "equals" in condition:
        return message.casefold() == condition["equals"].casefold()
    return False


def _transform(name: str, message: str, default: str | None = None) -> str:
    if name == "keep":
        return message
    if name == "strip_prefix":
        return TRIGGERS.sub("", message, count=1).strip()
    if name in ("strip_question", "strip_eq_question"):
        return re.sub(r"[\s?=]+$", "", message).strip()
    if name == "extract_name":
        rest = TRIGGERS.sub("", message, count=1)
        found = re.search(r"[A-Za-z0-9_\-\u0E00-\u0E7F]+", rest)
        return found.group(0) if found else ""
    if name == "extract_template":
        lowered = message.casefold()
        for candidate in ("python", "static", "svelte"):
            if candidate in lowered:
                return candidate
        return default or "python"
    if name == "extract_date":
        found = DATE_RE.search(message)
        return found.group(1) if found else ""
    if name == "extract_time":
        found = TIME_RE.search(message)
        return found.group(1) if found else "12:00"
    if name == "extract_location":
        clock = TIME_RE.search(message)
        if clock is not None:
            rest = message[clock.end() :]
        else:
            date = DATE_RE.search(message)
            rest = message[date.end() :] if date is not None else TRIGGERS.sub("", message, count=1)
        rest = rest.strip(" ,;-·|")
        return rest or "Bangkok"
    return message


def match(message: str) -> dict[str, Any] | None:
    text = normalize(message)
    if not text:
        return None
    for rule in rules():
        if rule.all and not all(_match_condition(c, text) for c in rule.all):
            continue
        if rule.any and not any(_match_condition(c, text) for c in rule.any):
            continue
        if not rule.all and not rule.any:
            continue
        confidence = 0.9 if rule.all and rule.any else (0.6 if rule.all else 0.7)
        slots = {}
        for slot_name, spec in rule.slots.items():
            slots[slot_name] = _transform(
                str(spec.get("transform", "keep")), text, spec.get("default")
            )
        explain = [
            condition.get("regex")
            or condition.get("contains")
            or condition.get("startswith")
            or condition.get("equals")
            for condition in [*rule.all, *rule.any]
        ]
        return {
            "intent": rule.intent,
            "rule_id": rule.id,
            "confidence": confidence,
            "slots": slots,
            "explain": explain,
        }
    return None


def route(message: str) -> dict[str, Any]:
    hit = match(message)
    if hit is None:
        return {"intent": None, "rule_id": None, "confidence": 0.0, "plan": None, "explain": []}
    plan = plans().get(hit["intent"])
    return {
        "intent": hit["intent"],
        "rule_id": hit["rule_id"],
        "confidence": hit["confidence"],
        "slots": hit["slots"],
        "steps": plan.steps if plan else None,
        "explain": hit["explain"],
        "error": None if plan else f"plan_missing:{hit['intent']}",
    }


def fill(value: Any, slots: dict[str, Any]) -> Any:
    if isinstance(value, str):

        def replace(match_obj: re.Match[str]) -> str:
            body = match_obj.group(1)
            key, _, default = body.partition("|")
            found = slots.get(key.strip())
            if found is None or found == "":
                return default
            return str(found)

        return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace, value)
    if isinstance(value, dict):
        return {key: fill(item, slots) for key, item in value.items()}
    if isinstance(value, list):
        return [fill(item, slots) for item in value]
    return value


def _astro_summary(data: dict[str, Any]) -> str:
    """One readable line for the four-system chart, used by the pipe answer template."""
    resolved = data.get("input_resolved") or {}
    western = data.get("western") or {}
    planets = western.get("planets") or {}
    ascendant = western.get("ascendant") or {}
    day = ((data.get("bazi") or {}).get("pillars") or {}).get("day") or {}

    parts: list[str] = []
    local = str(resolved.get("local_time") or "")
    if local:
        parts.append(local.replace("T", " ")[:16])
    for body in ("Sun", "Moon"):
        planet = planets.get(body)
        if planet:
            parts.append(f"{body} {planet.get('degree')} {planet.get('sign')}")
    if ascendant.get("degree"):
        parts.append(f"Asc {ascendant.get('degree')} {ascendant.get('sign')}")
    if day.get("chinese"):
        parts.append(f"BaZi {day['chinese']}")
    return " · ".join(parts)


def _context(results: list[dict[str, Any]]) -> dict[str, str]:
    ctx: dict[str, str] = {}
    for step in results:
        data = step["result"].get("data")
        if not isinstance(data, dict):
            if data is not None:
                ctx.setdefault("result", str(data))
            continue
        for key, value in data.items():
            if key in {"checks", "hits", "steps", "roots"}:
                continue
            ctx.setdefault(key, str(value))
        if "roots" in data and isinstance(data["roots"], list):
            ctx["roots"] = ", ".join(str(root) for root in data["roots"])
        if "checks" in data and isinstance(data["checks"], list):
            checks = data["checks"]
            passed = sum(1 for check in checks if check.get("ok"))
            ctx["checks"] = f"{passed}/{len(checks)} ok"
        if "hits" in data and isinstance(data["hits"], list):
            ctx["hits"] = f"{len(data['hits'])} hits"
        if "steps" in data and isinstance(data["steps"], list):
            ctx["steps"] = "; ".join(str(item.get("title", "?")) for item in data["steps"])
        if "western" in data and "input_resolved" in data:
            summary = _astro_summary(data)
            if summary:
                ctx["summary"] = summary
    return ctx


def render(template: str, ctx: dict[str, str]) -> str:
    def replace(match_obj: re.Match[str]) -> str:
        key = match_obj.group(1).split("|")[0].strip()
        return ctx.get(key, "")

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace, template).strip()


def run(
    conn,
    message: str,
    chat_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    routed = route(message)
    intent = routed["intent"]
    if intent is None:
        return {
            "intent": None,
            "plan": None,
            "results": [],
            "answer": None,
            "error": "no_route",
            "confidence": 0.0,
        }
    plan = plans().get(intent)
    if plan is None:
        return {**routed, "results": [], "answer": None, "error": f"plan_missing:{intent}"}

    slots = routed.get("slots") or {}
    results: list[dict[str, Any]] = []
    for step in plan.steps:
        tool_id = str(step["tool"])
        args = fill(step.get("args") or {}, slots)
        started = time.perf_counter()
        try:
            result = toolcall.invoke(tool_id, args)
        except TypeError as exc:
            result = {"ok": False, "data": None, "meta": {}, "error": f"bad_args:{exc}"}
        elapsed = int((time.perf_counter() - started) * 1000)
        call_id = audit(
            conn,
            tool_id,
            args,
            result,
            "ok" if result.get("ok") else "error",
            elapsed,
            chat_id,
            run_id,
        )
        results.append(
            {"tool": tool_id, "args": args, "result": result, "ms": elapsed, "call_id": call_id}
        )

    ctx = _context(results)
    answer = render(plan.answer, ctx)
    failed = [step for step in results if not step["result"].get("ok")]
    return {
        "intent": intent,
        "rule_id": routed["rule_id"],
        "confidence": routed["confidence"],
        "plan": {"intent": intent, "steps": plan.steps},
        "results": results,
        "answer": answer,
        "error": None if not failed else f"step_failed:{failed[0]['result'].get('error')}",
    }
