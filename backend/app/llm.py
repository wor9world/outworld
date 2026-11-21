"""Provider clients. Two wire protocols, one streaming interface.

``stream()`` is a normal generator so the agent loop can stay synchronous:

    ("delta", "text") ... ("final", {"content": str, "tool_calls": [...]})

Parsers are separate functions taking lines, so they are testable without a network.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterable, Iterator
from typing import Any

import httpx

CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 120.0


class LLMError(Exception):
    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


def list_enabled(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM providers WHERE enabled = 1 AND model <> '' ORDER BY created_at"
    ).fetchall()
    return [dict(row) for row in rows]


def _openai_payload(provider: dict, messages: list[dict], tools: list[dict] | None) -> dict:
    payload: dict[str, Any] = {
        "model": provider["model"],
        "messages": messages,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
    return payload


def parse_openai(lines: Iterable[str]) -> Iterator[tuple[str, Any]]:
    """Yield deltas then one final event from OpenAI-style SSE lines."""
    content: list[str] = []
    calls: dict[int, dict[str, Any]] = {}
    for raw in lines:
        line = raw.strip()
        if not line or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        for choice in chunk.get("choices", []):
            delta = choice.get("delta") or {}
            text = delta.get("content")
            if text:
                content.append(text)
                yield "delta", text
            for index, tool_call in enumerate(delta.get("tool_calls") or []):
                slot = calls.setdefault(int(tool_call.get("index", index)), {
                    "id": "", "name": "", "arguments": ""
                })
                if tool_call.get("id"):
                    slot["id"] = tool_call["id"]
                function = tool_call.get("function") or {}
                if function.get("name"):
                    slot["name"] = function["name"]
                if function.get("arguments"):
                    slot["arguments"] += function["arguments"]
    yield "final", {"content": "".join(content), "tool_calls": list(calls.values())}


def parse_ollama(lines: Iterable[str]) -> Iterator[tuple[str, Any]]:
    """Yield deltas then one final event from Ollama NDJSON lines."""
    content: list[str] = []
    calls: list[dict[str, Any]] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = chunk.get("message") or {}
        text = message.get("content")
        if text:
            content.append(text)
            yield "delta", text
        for tool_call in message.get("tool_calls") or []:
            function = tool_call.get("function") or {}
            calls.append(
                {
                    "id": tool_call.get("id", ""),
                    "name": function.get("name", ""),
                    "arguments": json.dumps(function.get("arguments") or {}, ensure_ascii=False),
                }
            )
        if chunk.get("done"):
            break
    yield "final", {"content": "".join(content), "tool_calls": calls}


def stream(
    provider: dict[str, Any],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> Iterator[tuple[str, Any]]:
    base = str(provider["base_url"]).rstrip("/")
    headers = {"content-type": "application/json"}
    if provider["kind"] == "openai":
        url = f"{base}/chat/completions"
        if provider.get("api_key"):
            headers["authorization"] = f"Bearer {provider['api_key']}"
        payload = _openai_payload(provider, messages, tools)
        parser = parse_openai
    elif provider["kind"] == "ollama":
        url = f"{base}/api/chat"
        payload = {"model": provider["model"], "messages": messages, "stream": True}
        if tools:
            payload["tools"] = tools
        parser = parse_ollama
    else:
        raise LLMError(f"unsupported kind: {provider['kind']}", 400)

    timeout = httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT)
    try:
        with httpx.stream("POST", url, json=payload, headers=headers, timeout=timeout) as response:
            if response.status_code >= 400:
                body = response.read().decode("utf-8", errors="replace")[:500]
                raise LLMError(f"provider {response.status_code}: {body}", 502)
            yield from parser(response.iter_lines())
    except httpx.HTTPError as exc:
        raise LLMError(f"provider unreachable: {exc}", 502) from exc


def probe(provider: dict[str, Any]) -> dict[str, Any]:
    """One non-streaming request, reported as ok + latency."""
    base = str(provider["base_url"]).rstrip("/")
    headers = {"content-type": "application/json"}
    if provider["kind"] == "openai":
        url = f"{base}/chat/completions"
        if provider.get("api_key"):
            headers["authorization"] = f"Bearer {provider['api_key']}"
        payload: dict[str, Any] = {
            "model": provider["model"],
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
            "max_tokens": 8,
        }
    else:
        url = f"{base}/api/chat"
        payload = {
            "model": provider["model"],
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
        }
    started = time.perf_counter()
    try:
        response = httpx.post(
            url, json=payload, headers=headers,
            timeout=httpx.Timeout(30.0, connect=CONNECT_TIMEOUT),
        )
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc)}
    latency = int((time.perf_counter() - started) * 1000)
    if response.status_code >= 400:
        return {"ok": False, "error": f"http_{response.status_code}", "latency_ms": latency}
    return {"ok": True, "model": provider["model"], "latency_ms": latency}
