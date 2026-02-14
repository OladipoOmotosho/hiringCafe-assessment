from __future__ import annotations

import hashlib
import json
import threading
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Dict, List

from app.config import settings

_metrics_lock = threading.Lock()
_metrics_loaded = False
_metrics_entries: List[Dict[str, Any]] = []


def _metrics_file_path() -> str:
    """Return the token metrics JSONL file path."""
    return str(settings.token_metrics_path)


def _ensure_metrics_loaded() -> None:
    """Load persisted metrics into memory once per process lifecycle."""
    global _metrics_loaded
    if _metrics_loaded:
        return

    settings.ensure_dirs()
    path = settings.token_metrics_path
    if path.exists():
        with path.open("r", encoding="utf-8") as file_handle:
            for line in file_handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    _metrics_entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    _metrics_loaded = True


def estimate_usd_cost(tokens_used: int) -> float:
    """Estimate request USD cost from token usage and configured token pricing."""
    if tokens_used <= 0:
        return 0.0
    usd_cost = (tokens_used / 1000.0) * settings.embedding_cost_per_1k_tokens
    return round(usd_cost, 8)


def record_token_usage(endpoint: str, query: str, tokens_used: int, elapsed_ms: int) -> Dict[str, Any]:
    """Record token usage for a search/refine request and persist to JSONL."""
    normalized_tokens = max(int(tokens_used), 0)
    query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "endpoint": endpoint,
        "query_hash": query_hash,
        "model": settings.embedding_model,
        "tokens_used": normalized_tokens,
        "estimated_usd_cost": estimate_usd_cost(normalized_tokens),
        "elapsed_ms": max(int(elapsed_ms), 0),
    }

    with _metrics_lock:
        _ensure_metrics_loaded()
        _metrics_entries.append(entry)
        with settings.token_metrics_path.open("a", encoding="utf-8") as file_handle:
            file_handle.write(json.dumps(entry) + "\n")

    return entry


def get_token_metrics(recent_limit: int = 20) -> Dict[str, Any]:
    """Aggregate total and daily token metrics plus recent request history."""
    bounded_limit = min(max(int(recent_limit), 1), 200)

    with _metrics_lock:
        _ensure_metrics_loaded()
        entries = list(_metrics_entries)

    total_tokens = sum(int(entry.get("tokens_used", 0)) for entry in entries)
    total_estimated_usd = round(sum(float(entry.get("estimated_usd_cost", 0.0)) for entry in entries), 8)

    by_day_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"requests": 0, "tokens_used": 0, "estimated_usd_cost": 0.0})
    for entry in entries:
        timestamp = str(entry.get("timestamp", ""))
        day = timestamp.split("T", maxsplit=1)[0] if "T" in timestamp else "unknown"
        by_day_map[day]["requests"] += 1
        by_day_map[day]["tokens_used"] += int(entry.get("tokens_used", 0))
        by_day_map[day]["estimated_usd_cost"] += float(entry.get("estimated_usd_cost", 0.0))

    by_day = [
        {
            "date": day,
            "requests": values["requests"],
            "tokens_used": values["tokens_used"],
            "estimated_usd_cost": round(values["estimated_usd_cost"], 8),
        }
        for day, values in sorted(by_day_map.items(), reverse=True)
    ]

    recent_requests = list(reversed(entries[-bounded_limit:]))

    return {
        "metrics_file": _metrics_file_path(),
        "model": settings.embedding_model,
        "pricing": {
            "embedding_cost_per_1k_tokens": settings.embedding_cost_per_1k_tokens,
            "currency": "USD",
        },
        "totals": {
            "requests": len(entries),
            "tokens_used": total_tokens,
            "estimated_usd_cost": total_estimated_usd,
        },
        "by_day": by_day,
        "recent_requests": recent_requests,
    }
