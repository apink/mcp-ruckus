"""Response shaping helpers — keep MCP payloads small for small-context models."""
from __future__ import annotations

import os
from typing import Any, Sequence

DEFAULT_MAX_ITEMS = 50


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def max_items() -> int:
    """Hard cap on returned list length, from MCP_MAX_ITEMS (default 50)."""
    return _env_int("MCP_MAX_ITEMS", DEFAULT_MAX_ITEMS)


def cap(items: Sequence[Any], limit: int | None = None) -> tuple[list[Any], int, bool]:
    """Slice a list to a hard cap; return (items, total_before_cap, truncated)."""
    total = len(items)
    hard = max_items()
    if limit is None or limit < 0:
        limit = hard
    limit = min(limit, hard)
    return list(items[:limit]), total, (total > limit)


def list_result(items: Sequence[Any], limit: int | None = None, hint: str = "") -> dict[str, Any]:
    """Standard envelope for list-returning tools.

    Returns {"items", "total", "returned", "truncated"} plus optional "hint".
    """
    sliced, total, truncated = cap(items, limit)
    result: dict[str, Any] = {
        "items": sliced,
        "total": total,
        "returned": len(sliced),
        "truncated": truncated,
    }
    if hint:
        result["hint"] = hint
    return result
