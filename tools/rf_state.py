"""In-memory cache for RF optimization results.

Stores optimization results with a TTL so the apply tool can reference
them via optimization_id without re-running the optimizer.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

_OPT_CACHE: dict[str, dict[str, Any]] = {}
_TTL: int = 1800  # 30 minutes


def save_optimization(result: dict[str, Any]) -> str:
    """Save optimization result to cache, return unique optimization_id."""
    opt_id = f"opt_{uuid.uuid4().hex[:8]}"
    result["_saved_at"] = time.time()
    _OPT_CACHE[opt_id] = result
    _cleanup_stale()
    logger.info("RF optimization saved: %s", opt_id)
    return opt_id


def load_optimization(opt_id: str) -> dict[str, Any] | None:
    """Load optimization result by ID. Returns None if expired/not found."""
    data = _OPT_CACHE.get(opt_id)
    if not data:
        return None
    if time.time() - data.get("_saved_at", 0) > _TTL:
        _OPT_CACHE.pop(opt_id, None)
        logger.warning("RF optimization %s expired", opt_id)
        return None
    return data


def _cleanup_stale() -> None:
    """Remove expired entries from cache."""
    now = time.time()
    stale = [k for k, v in _OPT_CACHE.items() if now - v.get("_saved_at", 0) > _TTL]
    for k in stale:
        del _OPT_CACHE[k]
