"""Candidate scoring, ranking, reranking, and confidence assessment.

This module turns raw candidate rows into scored ``JobResult`` objects by:

- **Keyword scoring** - simple coverage ratio of query tokens in job text.
- **Signal boosting** - additive score adjustments for remote, seniority,
  org-type, location, and mission-driven matches.
- **Hybrid ranking** - blend vector score, keyword score, and signal boosts.
- **Lightweight reranking** - phrase / title-aware second pass.
- **Confidence assessment** - detect low-quality result sets for retry logic.
- **Refinement suggestions** - generate follow-up prompts from missing signals.
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Dict, Iterable, List, Tuple

from app.constants import (
    CONFIDENCE_MIN_SPREAD,
    CONFIDENCE_MIN_TOP_SCORE,
    CONFIDENCE_TOP_WINDOW,
    KEYWORD_WEIGHT,
    LOCATION_BOOST,
    MAX_SIGNAL_BOOST,
    MISSION_BOOST,
    MISSION_MATCH_TERMS,
    MISSION_ORG_PATTERNS,
    NEGATION_PENALTY,
    ORG_TYPE_BOOST,
    RERANK_BLEND,
    RERANK_TOP_N,
    REMOTE_BOOST,
    SENIORITY_BOOST,
    VECTOR_WEIGHT,
)
from app.query_parser import normalize_query, tokenize
from app.schema import JobResult, RefinementSuggestion, ScoreBreakdown, SearchSignals


# ---------------------------------------------------------------------------
# Keyword scoring
# ---------------------------------------------------------------------------


def keyword_score(text: str, keywords: Iterable[str]) -> float:
    """Compute the fraction of *keywords* that appear in *text*.

    Args:
        text: Candidate job text (title + preview).
        keywords: Tokens extracted from the user query.

    Returns:
        Float in ``[0.0, 1.0]`` representing keyword coverage.
    """
    keywords_list = list(keywords)
    if not keywords_list:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for k in keywords_list if k in text_lower)
    return hits / max(len(keywords_list), 1)


# ---------------------------------------------------------------------------
# Signal boost
# ---------------------------------------------------------------------------


def signal_boost(row: Dict[str, Any], signals: SearchSignals) -> Tuple[float, List[str]]:
    """Compute additive boosts and identify which signals matched.

    Checks remote, seniority, org-type (with mission-driven expansion),
    location, and negation penalties.

    Args:
        row: Candidate job dict with keys ``title``, ``company``,
            ``location``, ``preview``.
        signals: Parsed search signals from the query.

    Returns:
        Tuple of ``(net_boost, matched_labels)`` where ``net_boost`` is
        capped at ``MAX_SIGNAL_BOOST`` minus any negation penalties.
    """
    boost = 0.0
    matched: List[str] = []
    haystack = f"{row['title']} {row['company']} {row['location']} {row['preview']}".lower()

    if signals.remote and "remote" in haystack:
        boost += REMOTE_BOOST
        matched.append("remote")
    if signals.seniority and signals.seniority in haystack:
        boost += SENIORITY_BOOST
        matched.append(signals.seniority)

    negation_penalty = 0.0
    for excluded in signals.excluded_keywords:
        if excluded in haystack:
            negation_penalty += NEGATION_PENALTY
            matched.append(f"exclude:{excluded}")

    for org in signals.org_types:
        if org == "mission-driven":
            if any(term in haystack for term in MISSION_MATCH_TERMS) or any(
                pat in haystack for pat in MISSION_ORG_PATTERNS
            ):
                boost += MISSION_BOOST
                matched.append("mission-driven")
            continue
        if org in haystack:
            boost += ORG_TYPE_BOOST
            matched.append(org)

    for loc in signals.location_terms:
        if loc in haystack:
            boost += LOCATION_BOOST
            matched.append(loc)

    return min(boost, MAX_SIGNAL_BOOST) - negation_penalty, matched


# ---------------------------------------------------------------------------
# Rank candidates (hybrid blend)
# ---------------------------------------------------------------------------


def rank_candidates(
    candidates: List[Dict[str, Any]],
    score_map: Dict[int, float],
    signals: SearchSignals,
) -> List[JobResult]:
    """Score candidates using the hybrid vector + keyword + signal formula.

    ``final = VECTOR_WEIGHT * vec + KEYWORD_WEIGHT * kw + signal_boost``

    Args:
        candidates: Raw job dicts from ``fetch_rows``.
        score_map: ``{row_index: cosine_similarity}`` from FAISS.
        signals: Parsed search signals.

    Returns:
        Descending-score list of ``JobResult`` objects.
    """
    ranked: List[JobResult] = []
    for row in candidates:
        text = f"{row['title']} {row['preview']}"
        kw_score = keyword_score(text, signals.keywords)
        vec_score = score_map.get(row["row_index"], 0.0)
        boost, matched = signal_boost(row, signals)
        score = VECTOR_WEIGHT * vec_score + KEYWORD_WEIGHT * kw_score + boost
        rounded_score = round(score, 4)
        ranked.append(
            JobResult(
                id=row["id"],
                title=row["title"],
                company=row["company"],
                location=row["location"],
                apply_url=row["apply_url"],
                score=rounded_score,
                preview=row["preview"],
                matched_signals=matched,
                score_breakdown=ScoreBreakdown(
                    vector_score=round(vec_score, 4),
                    keyword_score=round(kw_score, 4),
                    signal_adjustment=round(boost, 4),
                    rerank_adjustment=0.0,
                    final_score=rounded_score,
                ),
            )
        )
    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked


# ---------------------------------------------------------------------------
# Lightweight reranker
# ---------------------------------------------------------------------------


def _query_ngrams(query: str) -> List[str]:
    """Return bigrams from the query for phrase-level matching."""
    terms = tokenize(normalize_query(query))
    return [f"{terms[i]} {terms[i + 1]}" for i in range(len(terms) - 1)]


def rerank_results(
    results: List[JobResult], query: str, top_n: int = RERANK_TOP_N
) -> List[JobResult]:
    """Apply a phrase / title-aware reranker to the top-N candidates.

    Computes bigram overlap, title keyword coverage, and a small bonus for
    the number of matched signals, then blends into the existing score.

    Args:
        results: Pre-ranked ``JobResult`` list.
        query: Original user query.
        top_n: How many top results to rerank (rest are passed through).

    Returns:
        Re-sorted list with updated scores and ``rerank_adjustment`` in breakdown.
    """
    if not results:
        return results

    limit = min(top_n, len(results))
    query_terms = tokenize(normalize_query(query))[:8]
    query_bigrams = _query_ngrams(query)

    reranked: List[JobResult] = []
    for item in results[:limit]:
        haystack = f"{item.title} {item.company} {item.location} {item.preview}".lower()
        title_lower = item.title.lower()

        bigram_hits = sum(1 for phrase in query_bigrams if phrase in haystack)
        bigram_score = bigram_hits / max(len(query_bigrams), 1) if query_bigrams else 0.0
        title_coverage = keyword_score(title_lower, query_terms)
        signal_count_bonus = min(len(item.matched_signals) * 0.01, 0.04)

        rerank_signal = 0.6 * bigram_score + 0.3 * title_coverage + signal_count_bonus
        rerank_adjustment = round(RERANK_BLEND * rerank_signal, 4)
        item.score = round(item.score + rerank_adjustment, 4)
        if item.score_breakdown is not None:
            item.score_breakdown.rerank_adjustment = rerank_adjustment
            item.score_breakdown.final_score = item.score
        reranked.append(item)

    reranked.extend(results[limit:])
    reranked.sort(key=lambda r: r.score, reverse=True)
    return reranked


# ---------------------------------------------------------------------------
# Confidence assessment
# ---------------------------------------------------------------------------


def assess_ranking_confidence(
    results: List[JobResult],
) -> Tuple[bool, Dict[str, float]]:
    """Determine whether a result set looks trustworthy.

    Flags low confidence when the top score is below a threshold or the
    score spread across the top window is too narrow.

    Args:
        results: Ranked ``JobResult`` list (descending score).

    Returns:
        ``(is_low_confidence, metrics_dict)`` where *metrics_dict* contains
        ``top_score``, ``window_mean``, and ``spread``.
    """
    if not results:
        return True, {"top_score": 0.0, "window_mean": 0.0, "spread": 0.0}

    window = min(CONFIDENCE_TOP_WINDOW, len(results))
    top_score = float(results[0].score)
    window_scores = [float(item.score) for item in results[:window]]
    window_mean = float(mean(window_scores))
    spread = float(results[0].score - results[window - 1].score)
    is_low_confidence = top_score < CONFIDENCE_MIN_TOP_SCORE or spread < CONFIDENCE_MIN_SPREAD
    return is_low_confidence, {
        "top_score": round(top_score, 4),
        "window_mean": round(window_mean, 4),
        "spread": round(spread, 4),
    }


# ---------------------------------------------------------------------------
# Refinement suggestions
# ---------------------------------------------------------------------------


def suggest_refinements(signals: SearchSignals) -> List[RefinementSuggestion]:
    """Produce next-step refinement prompts based on missing signal slots.

    Args:
        signals: Current search signals.

    Returns:
        Up to 3 suggestion objects the UI can display as follow-up chips.
    """
    suggestions: List[RefinementSuggestion] = []
    if not signals.remote:
        suggestions.append(
            RefinementSuggestion(text="make it remote", reason="Add remote preference")
        )
    if not signals.seniority:
        suggestions.append(
            RefinementSuggestion(text="senior roles only", reason="Specify seniority")
        )
    if not signals.org_types:
        suggestions.append(
            RefinementSuggestion(
                text="mission-driven nonprofits", reason="Filter by org type"
            )
        )
    return suggestions
