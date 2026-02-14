from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from typing import Any, Dict, List

from app.config import settings

_feedback_lock = threading.Lock()
_feedback_loaded = False
_feedback_entries: List[Dict[str, Any]] = []


def _feedback_file_path() -> str:
    return str(settings.feedback_events_path)


def _ensure_feedback_loaded() -> None:
    global _feedback_loaded
    if _feedback_loaded:
        return

    settings.ensure_dirs()
    path = settings.feedback_events_path
    if path.exists():
        with path.open("r", encoding="utf-8") as file_handle:
            for line in file_handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    _feedback_entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    _feedback_loaded = True


def record_feedback(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query", "")).strip()
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": payload.get("event_type", "click"),
        "query": query,
        "query_hash": hashlib.sha256(query.encode("utf-8")).hexdigest()[:16] if query else "",
        "job_id": payload.get("job_id"),
        "rank": payload.get("rank"),
        "score": payload.get("score"),
        "source": payload.get("source", "search"),
        "context": payload.get("context"),
        "matched_signals": payload.get("matched_signals", []),
        "score_breakdown": payload.get("score_breakdown"),
    }

    with _feedback_lock:
        _ensure_feedback_loaded()
        _feedback_entries.append(entry)
        with settings.feedback_events_path.open("a", encoding="utf-8") as file_handle:
            file_handle.write(json.dumps(entry) + "\n")

    return entry


def get_feedback_summary(recent_limit: int = 50) -> Dict[str, Any]:
    bounded_limit = min(max(int(recent_limit), 1), 200)

    with _feedback_lock:
        _ensure_feedback_loaded()
        entries = list(_feedback_entries)

    recent = list(reversed(entries[-bounded_limit:]))
    totals = {
        "events": len(entries),
    }

    return {
        "feedback_file": _feedback_file_path(),
        "totals": totals,
        "recent_events": recent,
    }
