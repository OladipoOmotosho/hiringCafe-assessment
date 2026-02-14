from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List

from app.config import settings


@dataclass
class FeedbackStats:
    events: int
    with_breakdown: int
    avg_rank: float
    median_rank: float
    avg_score: float
    avg_vector: float | None
    avg_keyword: float | None
    avg_signal: float | None
    avg_rerank: float | None
    top_signals: List[str]


def _load_events(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    events: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _top_signals(events: List[Dict[str, Any]], limit: int = 8) -> List[str]:
    counts: Dict[str, int] = {}
    for event in events:
        for item in event.get("matched_signals", []) or []:
            counts[item] = counts.get(item, 0) + 1
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [name for name, _ in ranked[:limit]]


def compute_stats(events: List[Dict[str, Any]]) -> FeedbackStats:
    if not events:
        return FeedbackStats(
            events=0,
            with_breakdown=0,
            avg_rank=0.0,
            median_rank=0.0,
            avg_score=0.0,
            avg_vector=None,
            avg_keyword=None,
            avg_signal=None,
            avg_rerank=None,
            top_signals=[],
        )

    ranks = [int(e.get("rank", 0)) for e in events if e.get("rank") is not None]
    scores = [float(e.get("score", 0.0)) for e in events if e.get("score") is not None]

    breakdowns = [e.get("score_breakdown") for e in events if e.get("score_breakdown")]
    vectors = [float(b.get("vector_score", 0.0)) for b in breakdowns if b is not None]
    keywords = [float(b.get("keyword_score", 0.0)) for b in breakdowns if b is not None]
    signals = [float(b.get("signal_adjustment", 0.0)) for b in breakdowns if b is not None]
    reranks = [float(b.get("rerank_adjustment", 0.0)) for b in breakdowns if b is not None]

    return FeedbackStats(
        events=len(events),
        with_breakdown=len(breakdowns),
        avg_rank=round(mean(ranks), 3) if ranks else 0.0,
        median_rank=round(median(ranks), 3) if ranks else 0.0,
        avg_score=round(mean(scores), 4) if scores else 0.0,
        avg_vector=round(mean(vectors), 4) if vectors else None,
        avg_keyword=round(mean(keywords), 4) if keywords else None,
        avg_signal=round(mean(signals), 4) if signals else None,
        avg_rerank=round(mean(reranks), 4) if reranks else None,
        top_signals=_top_signals(events),
    )


def tuning_suggestions(stats: FeedbackStats) -> List[str]:
    suggestions: List[str] = []
    if stats.events == 0:
        suggestions.append("No feedback events captured yet. Generate clicks from the UI to enable tuning.")
        return suggestions

    if stats.avg_rank >= 6:
        suggestions.append("Clicks skew lower in the list; consider increasing rerank blend slightly (e.g., +0.05).")
    if stats.avg_keyword is not None and stats.avg_vector is not None:
        if stats.avg_keyword < stats.avg_vector * 0.6:
            suggestions.append("Clicked items lean semantic; consider modestly increasing VECTOR_WEIGHT.")
        elif stats.avg_keyword > stats.avg_vector * 1.2:
            suggestions.append("Clicked items lean lexical; consider modestly increasing KEYWORD_WEIGHT.")
    if stats.avg_signal is not None and stats.avg_signal < 0.03:
        suggestions.append("Intent boosts are low on clicked items; consider increasing signal boosts or keyword parsing.")
    if stats.avg_rerank is not None and stats.avg_rerank <= 0.005:
        suggestions.append("Reranker contribution is small; consider increasing RERANK_BLEND or top-N rerank window.")

    return suggestions or ["No obvious tuning action suggested from current feedback sample."]


def write_report(stats: FeedbackStats, suggestions: List[str], output_path: Path) -> None:
    payload = {
        "summary": {
            "events": stats.events,
            "with_breakdown": stats.with_breakdown,
            "avg_rank": stats.avg_rank,
            "median_rank": stats.median_rank,
            "avg_score": stats.avg_score,
            "avg_vector": stats.avg_vector,
            "avg_keyword": stats.avg_keyword,
            "avg_signal": stats.avg_signal,
            "avg_rerank": stats.avg_rerank,
            "top_signals": stats.top_signals,
        },
        "suggestions": suggestions,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    feedback_path = settings.feedback_events_path
    report_path = settings.data_dir / "feedback-tuning.json"

    events = _load_events(feedback_path)
    stats = compute_stats(events)
    suggestions = tuning_suggestions(stats)
    write_report(stats, suggestions, report_path)

    print("Feedback tuning report")
    print(f"- Events: {stats.events}")
    print(f"- Avg rank: {stats.avg_rank}")
    print(f"- Median rank: {stats.median_rank}")
    print(f"- Avg score: {stats.avg_score}")
    if stats.avg_vector is not None:
        print(f"- Avg vector score: {stats.avg_vector}")
    if stats.avg_keyword is not None:
        print(f"- Avg keyword score: {stats.avg_keyword}")
    if stats.avg_signal is not None:
        print(f"- Avg signal adjustment: {stats.avg_signal}")
    if stats.avg_rerank is not None:
        print(f"- Avg rerank adjustment: {stats.avg_rerank}")
    if suggestions:
        print("- Suggestions:")
        for suggestion in suggestions:
            print(f"  - {suggestion}")
    print(f"- Report: {report_path}")


if __name__ == "__main__":
    main()
