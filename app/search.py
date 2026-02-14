from __future__ import annotations

import logging
import re
import time
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Tuple

import duckdb
import faiss
import numpy as np
from openai import OpenAI

from app.config import settings
from app.ingest import build_index
from app.schema import JobResult, RefinementSuggestion, SearchContext, SearchResponse, SearchSignals

logger = logging.getLogger(__name__)

VECTOR_WEIGHT = 0.65
KEYWORD_WEIGHT = 0.25
MAX_SIGNAL_BOOST = 0.30
REMOTE_BOOST = 0.15
SENIORITY_BOOST = 0.10
ORG_TYPE_BOOST = 0.05
LOCATION_BOOST = 0.05

VECTOR_SEARCH_MULTIPLIER = 10
MAX_VECTOR_CANDIDATES = 500
KEYWORD_SEARCH_MULTIPLIER = 25
MAX_KEYWORD_CANDIDATES = 1000

EMBEDDING_CACHE_SIZE = 256
NEGATION_PENALTY = 0.20
MISSION_BOOST = 0.05

STOPWORDS = {
    "a",
    "an",
    "the",
    "for",
    "with",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "at",
    "jobs",
    "job",
    "role",
    "roles",
    "position",
    "positions",
    "looking",
    "want",
    "find",
    "show",
    "me",
    "some",
    "please",
    "need",
    "something",
    "i",
    "am",
    "interested",
    "not",
}

SENIORITY = ["intern", "junior", "mid", "senior", "staff", "principal", "lead"]
ORG_TYPES = ["nonprofit", "non-profit", "ngo", "startup", "government", "public"]

ABBREVIATION_EXPANSIONS = {
    "ml": "machine learning",
    "ds": "data science",
    "swe": "software engineer",
    "ai": "artificial intelligence",
    "pm": "product manager",
}

MISSION_QUERY_TERMS = [
    "social good",
    "mission driven",
    "mission-driven",
    "social impact",
    "public benefit",
    "purpose driven",
]

MISSION_MATCH_TERMS = [
    "social good",
    "mission",
    "impact",
    "equity",
    "community",
    "climate",
    "sustainability",
    "public benefit",
    "nonprofit",
    "non-profit",
    "ngo",
]

NEGATION_TERMS = {
    "management",
    "manager",
    "managers",
    "leadership",
    "director",
    "executive",
    "vp",
}

NON_LOCATION_PHRASES = {
    "data science",
    "machine learning",
    "software engineering",
    "product management",
    "social good",
    "mission driven",
}

NON_LOCATION_TOKENS = {
    "job",
    "jobs",
    "role",
    "roles",
    "engineering",
    "management",
    "manager",
    "science",
}


@lru_cache(maxsize=1)
def load_index() -> faiss.Index:
    """Load FAISS index from disk, building it if artifacts are missing."""
    if not settings.index_path.exists() or not settings.db_path.exists():
        build_index()
    return faiss.read_index(str(settings.index_path))


@lru_cache(maxsize=1)
def load_db() -> duckdb.DuckDBPyConnection:
    """Return a cached read-only DuckDB connection."""
    return duckdb.connect(str(settings.db_path), read_only=True)


@lru_cache(maxsize=1)
def openai_client() -> OpenAI | None:
    """Return an OpenAI client when API credentials are configured."""
    if not settings.openai_api_key:
        return None
    return OpenAI(api_key=settings.openai_api_key)


def tokenize(text: str) -> List[str]:
    """Tokenize query text while removing stopwords."""
    return [t for t in re.findall(r"[a-zA-Z0-9]+", text.lower()) if t not in STOPWORDS]


def normalize_query(query: str) -> str:
    """Normalize query text and expand common role-domain abbreviations."""
    normalized = " ".join(query.lower().split())
    for short, expanded in ABBREVIATION_EXPANSIONS.items():
        normalized = re.sub(rf"\b{re.escape(short)}\b", expanded, normalized)
    return normalized


def extract_negations(query: str) -> List[str]:
    """Extract minimal negation terms from phrases like 'not management'."""
    negations: List[str] = []
    for term in NEGATION_TERMS:
        if re.search(rf"\bnot\s+{re.escape(term)}\b", query):
            negations.append(term)
    return list(dict.fromkeys(negations))


def extract_location_terms(query: str) -> List[str]:
    """Extract likely location phrases while filtering obvious non-location clauses."""
    matches = re.findall(r"\b(?:in|near|around|within)\s+([a-zA-Z\s,]{2,40})", query)
    locations: List[str] = []
    for raw_match in matches:
        candidate = re.split(r"\b(?:with|for|that|who|where|and|or|not)\b", raw_match)[0]
        candidate = " ".join(candidate.strip(" ,.").split())
        if not candidate:
            continue
        if any(phrase in candidate for phrase in NON_LOCATION_PHRASES):
            continue
        words = re.findall(r"[a-zA-Z]+", candidate)
        if not words or len(words) > 4:
            continue
        if len(words) == 1 and words[0] in STOPWORDS:
            continue
        if any(word in NON_LOCATION_TOKENS for word in words):
            continue
        locations.append(" ".join(words))
    return list(dict.fromkeys(locations))


def parse_signals(query: str) -> SearchSignals:
    """Parse deterministic query signals used by retrieval and re-ranking."""
    normalized_query = normalize_query(query)
    tokens = tokenize(normalized_query)
    negated_terms = extract_negations(normalized_query)
    tokens = [token for token in tokens if token not in negated_terms]

    seniority = next((s for s in SENIORITY if s in tokens), None)
    org_types = [o for o in ORG_TYPES if o in normalized_query]
    if any(term in normalized_query for term in MISSION_QUERY_TERMS) and "mission-driven" not in org_types:
        org_types.append("mission-driven")

    remote = (
        "remote" in normalized_query
        or "work from home" in normalized_query
        or "wfh" in normalized_query
        or "anywhere" in normalized_query
    )
    location_terms = extract_location_terms(normalized_query)

    return SearchSignals(
        keywords=tokens,
        excluded_keywords=negated_terms,
        remote=remote,
        seniority=seniority,
        org_types=org_types,
        location_terms=location_terms,
    )


@lru_cache(maxsize=EMBEDDING_CACHE_SIZE)
def _embed_query_cached(query: str) -> Tuple[Tuple[float, ...], int]:
    """Generate and cache query embeddings to reduce repeated token spend."""
    client = openai_client()
    if not client:
        return tuple(), 0
    response = client.embeddings.create(model=settings.embedding_model, input=query)
    return tuple(response.data[0].embedding), response.usage.total_tokens


def embed_query(query: str) -> Tuple[np.ndarray | None, int]:
    """Embed a query and return normalized vector and tokens used for this request."""
    if not openai_client():
        return None, 0

    cache_before = _embed_query_cached.cache_info()
    embedding_values, cached_tokens = _embed_query_cached(query)
    cache_after = _embed_query_cached.cache_info()
    is_cache_hit = cache_after.hits > cache_before.hits

    vector = np.array(embedding_values, dtype=np.float32)
    faiss.normalize_L2(vector.reshape(1, -1))
    tokens_used = 0 if is_cache_hit else cached_tokens
    if is_cache_hit:
        logger.debug("Embedding cache hit for query=%r", query)
    return vector, tokens_used


def keyword_score(text: str, keywords: Iterable[str]) -> float:
    """Compute simple keyword coverage ratio for a candidate text."""
    keywords_list = list(keywords)
    if not keywords_list:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for k in keywords_list if k in text_lower)
    return hits / max(len(keywords_list), 1)


def merge_signals(base: SearchSignals, incoming: SearchSignals) -> SearchSignals:
    """Merge refinement signals into existing context signals."""
    return SearchSignals(
        keywords=list(dict.fromkeys([*base.keywords, *incoming.keywords])),
        excluded_keywords=list(dict.fromkeys([*base.excluded_keywords, *incoming.excluded_keywords])),
        remote=base.remote or incoming.remote,
        seniority=incoming.seniority or base.seniority,
        org_types=list(dict.fromkeys([*base.org_types, *incoming.org_types])),
        location_terms=list(dict.fromkeys([*base.location_terms, *incoming.location_terms])),
    )


def keyword_candidates(signals: SearchSignals, limit: int) -> List[int]:
    """Retrieve candidate row indices from DuckDB using keyword fallback filters."""
    con = load_db()
    where: List[str] = []
    params: List[object] = []

    if signals.keywords:
        where.append("(" + " OR ".join(["lower(title || ' ' || preview) LIKE ?" for _ in signals.keywords]) + ")")
        params.extend([f"%{k.lower()}%" for k in signals.keywords])
    for excluded in signals.excluded_keywords:
        where.append("lower(title || ' ' || preview || ' ' || company) NOT LIKE ?")
        params.append(f"%{excluded.lower()}%")
    if signals.remote:
        where.append("lower(title || ' ' || preview || ' ' || location) LIKE ?")
        params.append("%remote%")
    for org in signals.org_types:
        if org == "mission-driven":
            where.append(
                "(" + " OR ".join(["lower(title || ' ' || preview || ' ' || company) LIKE ?" for _ in MISSION_MATCH_TERMS]) + ")"
            )
            params.extend([f"%{term}%" for term in MISSION_MATCH_TERMS])
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


def signal_boost(row: Dict[str, Any], signals: SearchSignals) -> Tuple[float, List[str]]:
    """Compute additive boosts and matched signal labels for a candidate row."""
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
            if any(term in haystack for term in MISSION_MATCH_TERMS):
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


def fetch_rows(row_ids: List[int]) -> List[Dict[str, Any]]:
    """Fetch candidate metadata rows from DuckDB for given row indices."""
    if not row_ids:
        return []
    con = load_db()
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


def search_jobs(query: str, top_k: int, context: SearchContext | None = None) -> SearchResponse:
    """Execute search using hybrid retrieval and return ranked job results."""
    started = time.time()
    signals = parse_signals(query)
    if context:
        signals = merge_signals(context.signals, signals)

    vector, tokens_used = embed_query(query)
    results: List[JobResult] = []

    if vector is not None:
        index = load_index()
        search_k = min(top_k * VECTOR_SEARCH_MULTIPLIER, MAX_VECTOR_CANDIDATES)
        distances, indices = index.search(vector.reshape(1, -1), search_k)
        row_ids = [int(i) for i in indices[0] if i >= 0]
        candidates = fetch_rows(row_ids)
        score_map = {idx: float(dist) for idx, dist in zip(indices[0], distances[0])}
    else:
        row_ids = keyword_candidates(signals, limit=min(top_k * KEYWORD_SEARCH_MULTIPLIER, MAX_KEYWORD_CANDIDATES))
        candidates = fetch_rows(row_ids)
        score_map = {}

    for row in candidates:
        text = f"{row['title']} {row['preview']}"
        kw_score = keyword_score(text, signals.keywords)
        vec_score = score_map.get(row["row_index"], 0.0)
        boost, matched = signal_boost(row, signals)
        score = VECTOR_WEIGHT * vec_score + KEYWORD_WEIGHT * kw_score + boost
        results.append(
            JobResult(
                id=row["id"],
                title=row["title"],
                company=row["company"],
                location=row["location"],
                apply_url=row["apply_url"],
                score=round(score, 4),
                preview=row["preview"],
                matched_signals=matched,
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    results = results[:top_k]

    suggestions = suggest_refinements(signals)
    elapsed_ms = int((time.time() - started) * 1000)
    context_out = SearchContext(
        query=query,
        signals=signals,
        refinements=context.refinements if context else [],
        history=(context.history if context else []) + [query],
    )
    logger.debug(
        "Search internals query=%r candidates=%d vector_used=%s tokens_used=%d elapsed_ms=%d",
        query,
        len(candidates),
        vector is not None,
        tokens_used,
        elapsed_ms,
    )
    return SearchResponse(
        query=query,
        context=context_out,
        results=results,
        suggestions=suggestions,
        elapsed_ms=elapsed_ms,
        tokens_used=tokens_used,
    )


def suggest_refinements(signals: SearchSignals) -> List[RefinementSuggestion]:
    """Produce next-step refinement suggestions from current signal state."""
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


def refine_search(query: str, context: SearchContext, top_k: int) -> SearchResponse:
    """Apply a refinement query on top of previous conversational context."""
    context.refinements.append(query)
    return search_jobs(query, top_k, context)