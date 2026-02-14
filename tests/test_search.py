from __future__ import annotations

import pytest

from app.schema import SearchSignals
from app.search import keyword_score, merge_signals, parse_signals, signal_boost


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
