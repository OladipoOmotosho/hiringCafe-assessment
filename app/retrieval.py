"""Candidate retrieval, query rewriting, merging, and hard-exclusion filters.

This module handles everything between "we have search signals" and "here are
the raw candidate rows ready for scoring":

- **DuckDB keyword retrieval** – dynamic SQL WHERE clauses from signals.
- **Row fetching** – batch-load job metadata by row index.
- **Query rewriting** – build compact FAISS retrieval queries and focus
  queries for low-confidence retries.
- **Result merging** – de-duplicate and union ranked lists / row-id lists.
- **Hard exclusions** – filter rows that violate negated terms using
  morphological variant expansion.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from app.constants import (
    EXCLUSION_VARIANTS,
    MAX_MULTI_QUERIES,
    MISSION_MATCH_TERMS,
    MISSION_ORG_PATTERNS,
)
from app.query_parser import normalize_query
from app.schema import JobResult, SearchSignals


# ---------------------------------------------------------------------------
# DuckDB keyword candidate retrieval
# ---------------------------------------------------------------------------


def keyword_candidates(signals: SearchSignals, limit: int, db_loader: Any = None) -> List[int]:
    """Build a dynamic SQL query from signals and return matching row indices.

    Constructs WHERE clauses for keywords, excluded terms, remote flag,
    org types (including mission-driven expansion), and location terms.

    Args:
        signals: Parsed search signals driving the filter.
        limit: Maximum number of row indices to return.
        db_loader: Callable returning a DuckDB connection (injected by
            ``search.py``; defaults to ``load_db`` at runtime).

    Returns:
        List of integer ``row_index`` values from the jobs table.
    """
    if db_loader is None:
        from app.search import load_db
        db_loader = load_db

    con = db_loader()
    where: List[str] = []
    params: List[object] = []

    if signals.keywords:
        where.append(
            "(" + " OR ".join(["lower(title || ' ' || preview) LIKE ?" for _ in signals.keywords]) + ")"
        )
        params.extend([f"%{k.lower()}%" for k in signals.keywords])

    for excluded in signals.excluded_keywords:
        where.append("lower(title || ' ' || preview || ' ' || company) NOT LIKE ?")
        params.append(f"%{excluded.lower()}%")

    if signals.remote:
        where.append("lower(title || ' ' || preview || ' ' || location) LIKE ?")
        params.append("%remote%")

    for org in signals.org_types:
        if org == "mission-driven":
            all_mission = MISSION_MATCH_TERMS + MISSION_ORG_PATTERNS
            where.append(
                "("
                + " OR ".join(
                    ["lower(title || ' ' || preview || ' ' || company) LIKE ?" for _ in all_mission]
                )
                + ")"
            )
            params.extend([f"%{term}%" for term in all_mission])
            continue
        where.append("lower(title || ' ' || preview || ' ' || company) LIKE ?")
        params.append(f"%{org.lower()}%")

    for loc in signals.location_terms:
        where.append("lower(location) LIKE ?")
        params.append(f"%{loc.lower()}%")

    where_sql = " AND ".join(where) if where else "TRUE"
    sql = f"select row_index from jobs where {where_sql} limit {int(limit)}"
    rows = con.execute(sql, params).fetchall()
    return [int(r[0]) for r in rows]


# ---------------------------------------------------------------------------
# Row fetching
# ---------------------------------------------------------------------------


def fetch_rows(row_ids: List[int], db_loader: Any = None) -> List[Dict[str, Any]]:
    """Fetch full job metadata from DuckDB for a list of row indices.

    Args:
        row_ids: Integer row indices to look up.
        db_loader: Callable returning a DuckDB connection.

    Returns:
        Job dicts in the same order as *row_ids*, skipping any missing rows.
    """
    if not row_ids:
        return []
    if db_loader is None:
        from app.search import load_db
        db_loader = load_db

    con = db_loader()
    values_placeholder = ", ".join(["(?)" for _ in row_ids])
    query = (
        "WITH requested(row_index) AS (VALUES "
        + values_placeholder
        + ") "
        "SELECT j.row_index, j.id, j.title, j.company, j.location, j.apply_url, j.preview "
        "FROM jobs j "
        "JOIN requested r ON j.row_index = r.row_index"
    )
    rows = con.execute(query, row_ids).fetchall()
    row_map = {
        int(r[0]): {
            "row_index": int(r[0]),
            "id": r[1],
            "title": r[2],
            "company": r[3],
            "location": r[4],
            "apply_url": r[5],
            "preview": r[6],
        }
        for r in rows
    }
    return [row_map[row_id] for row_id in row_ids if row_id in row_map]


# ---------------------------------------------------------------------------
# Query rewriting helpers
# ---------------------------------------------------------------------------


def build_focus_query(query: str, signals: SearchSignals) -> str:
    """Build a compact query rewrite for low-confidence retries.

    Prioritises core intent tokens (seniority, remote, keywords, org types,
    location) and drops conversational filler.

    Args:
        query: Original user query (used as fallback).
        signals: Parsed search signals.

    Returns:
        A terse keyword-style query string.
    """
    parts: List[str] = []
    if signals.seniority:
        parts.append(signals.seniority)
    if signals.remote:
        parts.append("remote")
    parts.extend(signals.keywords[:8])
    parts.extend([org for org in signals.org_types if org != "mission-driven"])
    if "mission-driven" in signals.org_types:
        parts.append("social impact")
    for loc in signals.location_terms[:2]:
        parts.append(f"in {loc}")

    compact = " ".join(parts).strip()
    if not compact:
        return normalize_query(query)
    return compact


def build_retrieval_queries(query: str, signals: SearchSignals) -> List[str]:
    """Generate up to ``MAX_MULTI_QUERIES`` distinct retrieval rewrites.

    Produces the normalised query, a focus rewrite, a keyword-structured
    rewrite, and a concise token-only rewrite — all de-duplicated.

    Args:
        query: Original user query.
        signals: Parsed search signals.

    Returns:
        List of unique query strings (max ``MAX_MULTI_QUERIES``).
    """
    normalized = normalize_query(query)
    rewrites: List[str] = [normalized]

    focus = build_focus_query(query, signals)
    if focus and focus != normalized:
        rewrites.append(focus)

    parts: List[str] = []
    if signals.seniority:
        parts.append(signals.seniority)
    if signals.remote:
        parts.append("remote")
    parts.extend(signals.keywords[:6])
    if signals.location_terms:
        parts.append(f"in {signals.location_terms[0]}")
    if "mission-driven" in signals.org_types:
        parts.append("social impact")
    keyword_rewrite = " ".join(parts).strip()
    if keyword_rewrite and keyword_rewrite not in rewrites:
        rewrites.append(keyword_rewrite)

    concise = " ".join(signals.keywords[:4]).strip()
    if concise and concise not in rewrites:
        rewrites.append(concise)

    return list(dict.fromkeys(rewrites))[:MAX_MULTI_QUERIES]


# ---------------------------------------------------------------------------
# Result-set merge helpers
# ---------------------------------------------------------------------------


def merge_ranked_results(
    primary: List[JobResult], secondary: List[JobResult]
) -> List[JobResult]:
    """Merge two ranked lists, keeping the highest score per job id.

    Args:
        primary: First ranked list (usually the main retrieval).
        secondary: Second ranked list (e.g. from a focus-retry).

    Returns:
        Combined descending-score list with unique job ids.
    """
    merged: Dict[str, JobResult] = {}
    for item in [*primary, *secondary]:
        existing = merged.get(item.id)
        if existing is None or item.score > existing.score:
            merged[item.id] = item
    ranked = list(merged.values())
    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked


def merge_row_ids(primary: List[int], secondary: List[int], limit: int) -> List[int]:
    """De-duplicate and merge two row-id lists with source priority.

    Args:
        primary: Higher-priority row ids (appear first).
        secondary: Lower-priority row ids.
        limit: Maximum number of ids to return.

    Returns:
        Merged list capped at *limit*.
    """
    merged = list(dict.fromkeys([*primary, *secondary]))
    return merged[:limit]


# ---------------------------------------------------------------------------
# Hard exclusion filters
# ---------------------------------------------------------------------------


def _exclusion_terms(excluded_keywords: List[str]) -> List[str]:
    """Expand excluded keywords into all morphological variants.

    For example ``"management"`` expands to
    ``["management", "manager", "managers", "managerial", ...]``.

    Args:
        excluded_keywords: Raw excluded terms from ``SearchSignals``.

    Returns:
        Flat de-duplicated list of variant strings.
    """
    expanded: List[str] = []
    for term in excluded_keywords:
        expanded.extend(EXCLUSION_VARIANTS.get(term, [term]))
    return list(dict.fromkeys(expanded))


def violates_hard_exclusions(row: Dict[str, Any], excluded_keywords: List[str]) -> bool:
    """Return ``True`` when any excluded variant appears in the row text.

    Uses word-boundary regex to avoid partial matches (e.g. "analyst"
    should not be caught by "anal").

    Args:
        row: Job dict with ``title``, ``company``, ``location``, ``preview``.
        excluded_keywords: Terms the user wants excluded.

    Returns:
        ``True`` if the row should be filtered out.
    """
    if not excluded_keywords:
        return False
    haystack = f"{row['title']} {row['company']} {row['location']} {row['preview']}".lower()
    for term in _exclusion_terms(excluded_keywords):
        if re.search(rf"\b{re.escape(term)}\b", haystack):
            return True
    return False


def apply_hard_exclusions(
    candidates: List[Dict[str, Any]], signals: SearchSignals
) -> List[Dict[str, Any]]:
    """Filter out candidates that violate any negated / excluded terms.

    Args:
        candidates: Raw job dicts from ``fetch_rows``.
        signals: Parsed signals (only ``excluded_keywords`` is inspected).

    Returns:
        Filtered list with violating candidates removed.
    """
    if not signals.excluded_keywords:
        return candidates
    return [row for row in candidates if not violates_hard_exclusions(row, signals.excluded_keywords)]
