"""Minimal tool registry.

Every module in ``tools/`` decorates its entry point with::

    @register_tool(name="astro_all", description="...")
    def run(...) -> dict[str, Any]: ...

The API and the pipe look tools up here by name instead of importing them directly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ToolFunc = Callable[..., dict[str, Any]]

_TOOLS: dict[str, ToolFunc] = {}


def register_tool(name: str, description: str = "") -> Callable[[ToolFunc], ToolFunc]:
    """Register ``fn`` under ``name`` and tag it with its metadata."""

    def decorator(fn: ToolFunc) -> ToolFunc:
        fn.tool_name = name  # type: ignore[attr-defined]
        fn.tool_description = description  # type: ignore[attr-defined]
        _TOOLS[name] = fn
        return fn

    return decorator


def get_tool(name: str) -> ToolFunc:
    """Return the tool registered as ``name`` or raise ``KeyError``."""
    return _TOOLS[name]


def list_tools() -> dict[str, str]:
    """Map every registered tool name to its description."""
    return {name: getattr(fn, "tool_description", "") for name, fn in _TOOLS.items()}
