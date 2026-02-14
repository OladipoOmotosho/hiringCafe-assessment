from __future__ import annotations

import pytest

from app.schema import JobResult, SearchSignals
from app.search import (
    apply_hard_exclusions,
    assess_ranking_confidence,
    build_retrieval_queries,
    build_focus_query,
    keyword_score,
    merge_row_ids,
    merge_ranked_results,
    merge_signals,
    parse_signals,
    rerank_results,
    signal_boost,
)


def test_parse_signals_supports_abbreviation_mission_and_negation() -> None:
    query = "remote senior ml roles at mission-driven companies in california not management"
    signals = parse_signals(query)

    assert signals.remote is True
    assert signals.seniority == "senior"
    assert "machine" in signals.keywords
    assert "learning" in signals.keywords
    assert "mission-driven" in signals.org_types
    assert "management" in signals.excluded_keywords
    assert "california" in signals.location_terms


def test_parse_signals_supports_broader_negation_cues() -> None:
    query = "I don't want manager roles, shouldnt include director titles, neither executive nor vp, and less onsite work"

    signals = parse_signals(query)

    assert "manager" in signals.excluded_keywords
    assert "director" in signals.excluded_keywords
    assert "executive" in signals.excluded_keywords
    assert "vp" in signals.excluded_keywords
    assert "onsite" in signals.excluded_keywords


def test_parse_signals_does_not_treat_include_as_exclusion_target() -> None:
    query = "don't include director roles for product"

    signals = parse_signals(query)

    assert "director" in signals.excluded_keywords
    assert "include" not in signals.excluded_keywords


def test_merge_signals_unions_and_preserves_sticky_values() -> None:
    base = SearchSignals(
        keywords=["data", "science"],
        excluded_keywords=["management"],
        remote=True,
        seniority="mid",
        org_types=["nonprofit"],
        location_terms=["new york"],
    )
    incoming = SearchSignals(
        keywords=["science", "python"],
        excluded_keywords=["director"],
        remote=False,
        seniority="senior",
        org_types=["mission-driven"],
        location_terms=["california"],
    )

    merged = merge_signals(base, incoming)

    assert merged.keywords == ["data", "science", "python"]
    assert merged.excluded_keywords == ["management", "director"]
    assert merged.remote is True
    assert merged.seniority == "senior"
    assert merged.org_types == ["nonprofit", "mission-driven"]
    assert merged.location_terms == ["new york", "california"]


def test_keyword_score_computes_coverage_ratio() -> None:
    text = "Senior machine learning engineer with remote options"
    keywords = ["senior", "machine", "california"]

    score = keyword_score(text, keywords)

    assert score == 2 / 3


def test_signal_boost_applies_caps_and_negation_penalty() -> None:
    row = {
        "title": "Senior Data Scientist",
        "company": "Impact Nonprofit",
        "location": "Boston",
        "preview": "Remote role focused on mission impact and management of analytics teams",
    }
    signals = SearchSignals(
        remote=True,
        seniority="senior",
        org_types=["mission-driven"],
        location_terms=["boston"],
        excluded_keywords=["management"],
    )

    boost, matched = signal_boost(row, signals)

    assert boost == pytest.approx(0.1)
    assert "remote" in matched
    assert "senior" in matched
    assert "mission-driven" in matched
    assert "boston" in matched
    assert "exclude:management" in matched


def test_assess_ranking_confidence_flags_low_when_scores_flat() -> None:
    results = [
        JobResult(
            id=f"id-{index}",
            title="Role",
            company="Company",
            location="Remote",
            apply_url="https://example.com",
            score=score,
            preview="Preview",
            matched_signals=[],
        )
        for index, score in enumerate([0.31, 0.305, 0.302, 0.301, 0.3])
    ]

    low_confidence, metrics = assess_ranking_confidence(results)

    assert low_confidence is True
    assert metrics["top_score"] == pytest.approx(0.31)
    assert metrics["spread"] == pytest.approx(0.01)


def test_build_focus_query_prioritizes_core_signals() -> None:
    signals = SearchSignals(
        keywords=["frontend", "react", "typescript"],
        remote=True,
        seniority="senior",
        org_types=["startup", "mission-driven"],
        location_terms=["canada"],
    )

    query = build_focus_query("i am looking for something", signals)

    assert "senior" in query
    assert "remote" in query
    assert "frontend" in query
    assert "react" in query
    assert "social impact" in query
    assert "in canada" in query


def test_build_retrieval_queries_creates_unique_compact_rewrites() -> None:
    signals = SearchSignals(
        keywords=["machine", "learning", "engineer", "python"],
        remote=True,
        seniority="senior",
        org_types=["mission-driven"],
        location_terms=["canada"],
    )

    rewrites = build_retrieval_queries("Senior remote ML engineer in Canada", signals)

    assert len(rewrites) >= 2
    assert len(rewrites) == len(set(rewrites))
    assert any("social impact" in rewrite for rewrite in rewrites)


def test_rerank_results_boosts_phrase_and_title_alignment() -> None:
    first = JobResult(
        id="job-1",
        title="Senior Machine Learning Engineer",
        company="A",
        location="Remote",
        apply_url="https://example.com/1",
        score=0.40,
        preview="Build machine learning systems",
        matched_signals=["remote", "senior"],
    )
    second = JobResult(
        id="job-2",
        title="Generalist Engineer",
        company="B",
        location="Remote",
        apply_url="https://example.com/2",
        score=0.40,
        preview="Cross-functional product engineering",
        matched_signals=[],
    )

    reranked = rerank_results([first, second], "senior machine learning engineer", top_n=2)

    assert reranked[0].id == "job-1"
    assert reranked[0].score >= 0.40


def test_merge_ranked_results_keeps_highest_per_job() -> None:
    primary = [
        JobResult(
            id="job-1",
            title="Role",
            company="Company",
            location="Remote",
            apply_url="https://example.com/1",
            score=0.41,
            preview="Preview",
            matched_signals=[],
        )
    ]
    secondary = [
        JobResult(
            id="job-1",
            title="Role",
            company="Company",
            location="Remote",
            apply_url="https://example.com/1",
            score=0.45,
            preview="Preview",
            matched_signals=[],
        ),
        JobResult(
            id="job-2",
            title="Role 2",
            company="Company",
            location="Remote",
            apply_url="https://example.com/2",
            score=0.43,
            preview="Preview",
            matched_signals=[],
        ),
    ]

    merged = merge_ranked_results(primary, secondary)

    assert [item.id for item in merged] == ["job-1", "job-2"]
    assert merged[0].score == pytest.approx(0.45)


def test_merge_row_ids_deduplicates_with_source_priority() -> None:
    primary = [10, 20, 30]
    secondary = [30, 40, 50]

    merged = merge_row_ids(primary, secondary, limit=4)

    assert merged == [10, 20, 30, 40]


def test_apply_hard_exclusions_filters_variant_terms() -> None:
    signals = SearchSignals(excluded_keywords=["director"])
    candidates = [
        {
            "row_index": 1,
            "id": "job-1",
            "title": "Product Director",
            "company": "A",
            "location": "Remote",
            "apply_url": "https://example.com/1",
            "preview": "Lead product strategy",
        },
        {
            "row_index": 2,
            "id": "job-2",
            "title": "Senior Product Manager",
            "company": "B",
            "location": "Remote",
            "apply_url": "https://example.com/2",
            "preview": "Own roadmap",
        },
    ]

    filtered = apply_hard_exclusions(candidates, signals)

    assert [row["id"] for row in filtered] == ["job-2"]
