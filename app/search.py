from __future__ import annotations

import logging
import re
import time
from functools import lru_cache
from statistics import mean
from typing import Any, Dict, Iterable, List, Tuple

import duckdb
import faiss
import numpy as np
from openai import OpenAI

from app.config import settings
from app.ingest import build_index
from app.schema import JobResult, RefinementSuggestion, ScoreBreakdown, SearchContext, SearchResponse, SearchSignals

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
MAX_MULTI_QUERIES = 4
MULTI_QUERY_HIT_BONUS = 0.02
RERANK_TOP_N = 40
RERANK_BLEND = 0.20

EMBEDDING_CACHE_SIZE = 256
NEGATION_PENALTY = 0.20
MISSION_BOOST = 0.05

CONFIDENCE_MIN_TOP_SCORE = 0.30
CONFIDENCE_MIN_SPREAD = 0.03
CONFIDENCE_TOP_WINDOW = 5

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
    "managerial",
    "people management",
    "manager",
    "managers",
    "leadership",
    "director",
    "directors",
    "executive",
    "executives",
    "vp",
    "onsite",
    "on-site",
}

NEGATION_CUES = [
    "not",
    "no",
    "without",
    "exclude",
    "excluding",
    "except",
    "avoid",
    "never",
    "dont",
    "do not",
    "doesnt",
    "does not",
    "didnt",
    "did not",
    "shouldnt",
    "should not",
    "cannot",
    "cant",
    "will not",
    "wont",
    "less",
    "fewer",
]

NEGATION_NOISE_TOKENS = {
    "include",
    "including",
    "exclude",
    "excluding",
    "show",
    "list",
    "give",
    "want",
    "need",
    "prefer",
    "more",
    "less",
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

EXCLUSION_VARIANTS = {
    "management": ["management", "manager", "managers", "managerial", "people management"],
    "manager": ["manager", "managers", "management", "managerial"],
    "director": ["director", "directors", "director-level"],
    "executive": ["executive", "executives", "exec", "c-suite", "c suite", "vp", "vice president"],
    "vp": ["vp", "vice president", "vice-president"],
    "onsite": ["onsite", "on-site", "in office", "in-office"],
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
    """Extract negated terms from user intent (not/don't/never/neither...nor/less...)."""
    normalized = query.lower().replace("’", "'")
    normalized = re.sub(r"\b(don't|doesn't|didn't|can't|won't|shouldn't|isn't|aren't)\b", lambda m: m.group(1).replace("'", ""), normalized)
    negations: List[str] = []

    terms_by_length = sorted(NEGATION_TERMS, key=len, reverse=True)
    cue_pattern = "|".join(re.escape(cue) for cue in NEGATION_CUES)

    for term in terms_by_length:
        term_pattern = re.escape(term)
        if re.search(rf"\b(?:{cue_pattern})\b(?:\s+\w+){{0,2}}\s+{term_pattern}\b", normalized):
            negations.append(term)

    for match in re.finditer(r"\bneither\s+([a-z][a-z\s\-]{1,40}?)\s+nor\s+([a-z][a-z\s\-]{1,40})\b", normalized):
        left, right = match.group(1), match.group(2)
        for side in (left, right):
            for term in terms_by_length:
                if re.search(rf"\b{re.escape(term)}\b", side):
                    negations.append(term)

    for match in re.finditer(rf"\b(?:{cue_pattern})\b\s+([a-z\-]{{3,}})", normalized):
        candidate = match.group(1)
        if candidate in STOPWORDS:
            continue
        if candidate in NEGATION_NOISE_TOKENS:
            continue
        if candidate in {"role", "roles", "job", "jobs", "work", "position", "positions"}:
            continue
        negations.append(candidate)

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


def rank_candidates(candidates: List[Dict[str, Any]], score_map: Dict[int, float], signals: SearchSignals) -> List[JobResult]:
    """Rank fetched candidates using hybrid score components."""
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


def build_retrieval_queries(query: str, signals: SearchSignals) -> List[str]:
    """Build compact query rewrites used for candidate-recall improvements."""
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


def _query_ngrams(query: str) -> List[str]:
    """Return simple bigrams used by the lightweight reranker."""
    terms = tokenize(normalize_query(query))
    return [f"{terms[i]} {terms[i + 1]}" for i in range(len(terms) - 1)]


def rerank_results(results: List[JobResult], query: str, top_n: int = RERANK_TOP_N) -> List[JobResult]:
    """Apply a lightweight phrase/title-aware reranker to top candidates."""
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


def assess_ranking_confidence(results: List[JobResult]) -> Tuple[bool, Dict[str, float]]:
    """Return low-confidence flag and summary metrics for ranked results."""
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


def build_focus_query(query: str, signals: SearchSignals) -> str:
    """Build a compact query rewrite for low-confidence retries."""
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


def merge_ranked_results(primary: List[JobResult], secondary: List[JobResult]) -> List[JobResult]:
    """Merge two ranked lists by job id, preserving the highest-scoring version."""
    merged: Dict[str, JobResult] = {}
    for item in [*primary, *secondary]:
        existing = merged.get(item.id)
        if existing is None or item.score > existing.score:
            merged[item.id] = item
    ranked = list(merged.values())
    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked


def merge_row_ids(primary: List[int], secondary: List[int], limit: int) -> List[int]:
    """Merge candidate row ids with de-duplication and stable source priority."""
    merged = list(dict.fromkeys([*primary, *secondary]))
    return merged[:limit]


def _exclusion_terms(excluded_keywords: List[str]) -> List[str]:
    """Expand excluded terms into normalized variant list used for hard filtering."""
    expanded: List[str] = []
    for term in excluded_keywords:
        expanded.extend(EXCLUSION_VARIANTS.get(term, [term]))
    return list(dict.fromkeys(expanded))


def violates_hard_exclusions(row: Dict[str, Any], excluded_keywords: List[str]) -> bool:
    """Return True when row content matches any excluded term or variant."""
    if not excluded_keywords:
        return False
    haystack = f"{row['title']} {row['company']} {row['location']} {row['preview']}".lower()
    for term in _exclusion_terms(excluded_keywords):
        if re.search(rf"\b{re.escape(term)}\b", haystack):
            return True
    return False


def apply_hard_exclusions(candidates: List[Dict[str, Any]], signals: SearchSignals) -> List[Dict[str, Any]]:
    """Filter out candidates that violate explicit excluded intent terms."""
    if not signals.excluded_keywords:
        return candidates
    return [row for row in candidates if not violates_hard_exclusions(row, signals.excluded_keywords)]


def search_jobs(query: str, top_k: int, context: SearchContext | None = None) -> SearchResponse:
    """Execute search using hybrid retrieval and return ranked job results."""
    started = time.time()
    signals = parse_signals(query)
    if context:
        signals = merge_signals(context.signals, signals)

    vector, tokens_used = embed_query(query)
    results: List[JobResult] = []
    retrieval_queries = build_retrieval_queries(query, signals)
    retrieval_mode = "vector+keyword" if vector is not None else "keyword"
    confidence_retry_used = False
    focus_query = ""
    search_k = min(top_k * VECTOR_SEARCH_MULTIPLIER, MAX_VECTOR_CANDIDATES)
    keyword_limit = min(top_k * KEYWORD_SEARCH_MULTIPLIER, MAX_KEYWORD_CANDIDATES)

    if vector is not None:
        index = load_index()
        distances, indices = index.search(vector.reshape(1, -1), search_k)
        vector_row_ids = [int(i) for i in indices[0] if i >= 0]
        row_hits: Dict[int, int] = {row_id: 1 for row_id in vector_row_ids}
        keyword_row_ids = keyword_candidates(signals, limit=keyword_limit)
        score_map = {int(idx): float(dist) for idx, dist in zip(indices[0], distances[0]) if idx >= 0}

        for rewrite_query in retrieval_queries[1:]:
            rewrite_vector, rewrite_tokens = embed_query(rewrite_query)
            tokens_used += rewrite_tokens
            if rewrite_vector is None:
                continue
            rewrite_distances, rewrite_indices = index.search(rewrite_vector.reshape(1, -1), search_k)
            rewrite_row_ids = [int(i) for i in rewrite_indices[0] if i >= 0]
            for idx, dist in zip(rewrite_indices[0], rewrite_distances[0]):
                if idx < 0:
                    continue
                row_index = int(idx)
                row_hits[row_index] = row_hits.get(row_index, 0) + 1
                score_map[row_index] = max(score_map.get(row_index, -1.0), float(dist))
            vector_row_ids = merge_row_ids(vector_row_ids, rewrite_row_ids, limit=keyword_limit)

        for row_index, hits in row_hits.items():
            if hits > 1 and row_index in score_map:
                score_map[row_index] = round(score_map[row_index] + MULTI_QUERY_HIT_BONUS * (hits - 1), 6)

        row_ids = merge_row_ids(vector_row_ids, keyword_row_ids, limit=keyword_limit)
        candidates = fetch_rows(row_ids)
        retrieval_mode = f"vector+keyword+multiq({len(retrieval_queries)})"
    else:
        row_ids = keyword_candidates(signals, limit=keyword_limit)
        candidates = fetch_rows(row_ids)
        score_map = {}

    candidates = apply_hard_exclusions(candidates, signals)
    results = rank_candidates(candidates, score_map, signals)
    results = rerank_results(results, query)
    low_confidence, confidence_metrics = assess_ranking_confidence(results)

    if low_confidence and vector is not None:
        focus_query = build_focus_query(query, signals)
        if focus_query != query:
            retry_vector, retry_tokens = embed_query(focus_query)
            tokens_used += retry_tokens
            if retry_vector is not None:
                index = load_index()
                retry_distances, retry_indices = index.search(retry_vector.reshape(1, -1), search_k)
                retry_vector_row_ids = [int(i) for i in retry_indices[0] if i >= 0]
                retry_keyword_row_ids = keyword_candidates(signals, limit=keyword_limit)
                retry_row_ids = merge_row_ids(retry_vector_row_ids, retry_keyword_row_ids, limit=keyword_limit)
                retry_candidates = fetch_rows(retry_row_ids)
                retry_candidates = apply_hard_exclusions(retry_candidates, signals)
                retry_score_map = {int(idx): float(dist) for idx, dist in zip(retry_indices[0], retry_distances[0]) if idx >= 0}
                retry_results = rank_candidates(retry_candidates, retry_score_map, signals)
                retry_results = rerank_results(retry_results, focus_query)
                results = merge_ranked_results(results, retry_results)
                confidence_retry_used = True
                retrieval_mode = f"{retrieval_mode}+focus-retry"

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
        "Search internals query=%r mode=%s retrieval_queries=%s candidates=%d top_k=%d tokens_used=%d elapsed_ms=%d low_confidence=%s confidence=%s focus_retry=%s focus_query=%r signals=%s",
        query,
        retrieval_mode,
        retrieval_queries,
        len(candidates),
        top_k,
        tokens_used,
        elapsed_ms,
        low_confidence,
        confidence_metrics,
        confidence_retry_used,
        focus_query,
        signals.model_dump(),
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