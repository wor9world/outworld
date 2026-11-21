"""One place that turns a public tool id plus args into a real tool call.

The API, the pipe and the agent all go through here, so the astro location bridge and
any future argument preprocessing cannot drift between callers.
"""

from __future__ import annotations

from typing import Any

from tools import registry

from . import locations


def prepare(tool_id: str, args: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(args)
    if tool_id == "astro" and not prepared.get("lat") and prepared.get("location"):
        found = locations.resolve(str(prepared["location"]))
        if found is not None:
            prepared["lat"], prepared["lon"] = found[0], found[1]
            if not prepared.get("tz_name"):
                prepared["tz_name"] = found[2]
    return prepared


def invoke(tool_id: str, args: dict[str, Any], **extra: Any) -> dict[str, Any]:
    fn = registry.get_tool(registry.resolve(tool_id))
    return fn(**{**prepare(tool_id, args), **extra})
