from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from statistics import mean
from typing import Dict, List

from app.config import settings
from app.search import parse_signals, search_jobs


@dataclass(frozen=True)
class EvalQuery:
    text: str
    description: str


@dataclass
class EvalResult:
    query: str
    description: str
    top_k: int
    top_score: float
    avg_top5_score: float
    keyword_hit_rate: float
    exclusion_violations: int
    remote_hit_rate: float | None
    elapsed_ms: int
    tokens_used: int


def _hit_rate(results, term: str) -> float:
    if not results:
        return 0.0
    lowered = term.lower()
    hits = 0
    for item in results:
        haystack = f"{item.title} {item.company} {item.location} {item.preview}".lower()
        if lowered in haystack:
            hits += 1
    return round(hits / len(results), 4)


def evaluate_queries(queries: List[EvalQuery], top_k: int = 10) -> List[EvalResult]:
    reports: List[EvalResult] = []

    for query in queries:
        response = search_jobs(query.text, top_k=top_k)
        signals = parse_signals(query.text)

        top_score = response.results[0].score if response.results else 0.0
        avg_top5 = mean([item.score for item in response.results[:5]]) if response.results else 0.0

        keyword_rates = []
        for keyword in signals.keywords[:6]:
            keyword_rates.append(_hit_rate(response.results, keyword))
        keyword_hit_rate = round(mean(keyword_rates), 4) if keyword_rates else 0.0

        exclusion_violations = 0
        for excluded in signals.excluded_keywords:
            for item in response.results:
                haystack = f"{item.title} {item.company} {item.location} {item.preview}".lower()
                if excluded in haystack:
                    exclusion_violations += 1

        remote_hit_rate = _hit_rate(response.results, "remote") if signals.remote else None

        reports.append(
            EvalResult(
                query=query.text,
                description=query.description,
                top_k=top_k,
                top_score=round(top_score, 4),
                avg_top5_score=round(avg_top5, 4),
                keyword_hit_rate=keyword_hit_rate,
                exclusion_violations=exclusion_violations,
                remote_hit_rate=remote_hit_rate,
                elapsed_ms=response.elapsed_ms,
                tokens_used=response.tokens_used,
            )
        )

    return reports


def default_queries() -> List[EvalQuery]:
    return [
        EvalQuery("data science jobs", "broad semantic intent"),
        EvalQuery("senior remote machine learning engineer", "constraint-heavy search"),
        EvalQuery("frontend react roles in canada startup", "location + org intent"),
        EvalQuery("social impact nonprofit data analyst", "mission-driven + function"),
        EvalQuery("backend python jobs not management", "negation handling"),
        EvalQuery("don't include director roles for product", "contraction negation"),
        EvalQuery("neither executive nor vp data roles", "neither/nor negation"),
        EvalQuery("less onsite and more remote engineering roles", "comparative negation cue"),
        EvalQuery("entry level analyst jobs", "seniority/experience intent"),
        EvalQuery("staff platform engineer", "title precision"),
    ]


def summarize(results: List[EvalResult]) -> Dict[str, float]:
    if not results:
        return {
            "queries": 0,
            "mean_top_score": 0.0,
            "mean_avg_top5_score": 0.0,
            "mean_keyword_hit_rate": 0.0,
            "total_exclusion_violations": 0,
            "mean_elapsed_ms": 0.0,
            "total_tokens_used": 0,
        }

    return {
        "queries": len(results),
        "mean_top_score": round(mean([r.top_score for r in results]), 4),
        "mean_avg_top5_score": round(mean([r.avg_top5_score for r in results]), 4),
        "mean_keyword_hit_rate": round(mean([r.keyword_hit_rate for r in results]), 4),
        "total_exclusion_violations": int(sum(r.exclusion_violations for r in results)),
        "mean_elapsed_ms": round(mean([r.elapsed_ms for r in results]), 2),
        "total_tokens_used": int(sum(r.tokens_used for r in results)),
    }


def write_report(results: List[EvalResult], output_path: Path) -> None:
    payload = {
        "summary": summarize(results),
        "results": [asdict(item) for item in results],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    report_path = settings.data_dir / "eval-report.json"
    queries = default_queries()
    results = evaluate_queries(queries, top_k=10)
    write_report(results, report_path)

    summary = summarize(results)
    print("Evaluation complete")
    print(f"- Queries: {summary['queries']}")
    print(f"- Mean top score: {summary['mean_top_score']}")
    print(f"- Mean avg@5 score: {summary['mean_avg_top5_score']}")
    print(f"- Mean keyword hit rate: {summary['mean_keyword_hit_rate']}")
    print(f"- Exclusion violations: {summary['total_exclusion_violations']}")
    print(f"- Mean elapsed ms: {summary['mean_elapsed_ms']}")
    print(f"- Total tokens used: {summary['total_tokens_used']}")
    print(f"- Report: {report_path}")


if __name__ == "__main__":
    main()
