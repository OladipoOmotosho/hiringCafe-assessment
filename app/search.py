"""Hybrid job-search orchestration layer.

This is the main entry-point for the search pipeline.  It wires together:

- **FAISS vector retrieval** (cosine similarity via OpenAI embeddings).
- **DuckDB keyword retrieval** (SQL LIKE filters built from query signals).
- **Multi-query recall** - multiple embedding rewrites merged for coverage.
- **Ranking + reranking** - hybrid score blend then lightweight phrase reranker.
- **Low-confidence retry** - automatic focus-query retry when scores are flat.
- **Multi-turn refinement** - ``refine_search`` merges prior context.

Other modules
-------------
- ``constants.py``     - all tuning weights and vocabulary lists.
- ``query_parser.py``  - tokenisation, negation, location, signal parsing.
- ``ranking.py``       - scoring, reranking, confidence, suggestions.
- ``retrieval.py``     - DuckDB retrieval, row fetching, merging, exclusions.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Dict, List, Tuple

import duckdb
import faiss
import numpy as np
from openai import OpenAI

from app.config import settings
from app.constants import (
    EMBEDDING_CACHE_SIZE,
    KEYWORD_SEARCH_MULTIPLIER,
    MAX_KEYWORD_CANDIDATES,
    MAX_VECTOR_CANDIDATES,
    MULTI_QUERY_HIT_BONUS,
    VECTOR_SEARCH_MULTIPLIER,
)
from app.ingest import build_index
from app.query_parser import merge_signals, normalize_query, parse_signals
from app.ranking import (
    assess_ranking_confidence,
    rank_candidates,
    rerank_results,
    suggest_refinements,
)
from app.retrieval import (
    apply_hard_exclusions,
    build_focus_query,
    build_retrieval_queries,
    fetch_rows,
    keyword_candidates,
    merge_ranked_results,
    merge_row_ids,
)
from app.schema import (
    JobResult,
    RefinementSuggestion,
    ScoreBreakdown,
    SearchContext,
    SearchResponse,
    SearchSignals,
)

# Re-export everything so existing ``from app.search import X`` still works.
# This keeps api.py, eval.py, and test_search.py imports stable.
from app.query_parser import (  # noqa: F401 - re-exports
    extract_location_terms,
    extract_negations,
    tokenize,
)
from app.ranking import (  # noqa: F401 - re-exports
    keyword_score,
    signal_boost,
)
from app.retrieval import (  # noqa: F401 - re-exports
    violates_hard_exclusions,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Infrastructure - cached singletons
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_index() -> faiss.Index:
    """Load FAISS index from disk, building artifacts first if missing.

    Returns:
        A ready-to-query ``faiss.Index`` (inner-product / cosine).
    """
    if not settings.index_path.exists() or not settings.db_path.exists():
        build_index()
    return faiss.read_index(str(settings.index_path))


@lru_cache(maxsize=1)
def load_db() -> duckdb.DuckDBPyConnection:
    """Return a cached read-only DuckDB connection to the jobs database.

    Returns:
        A ``DuckDBPyConnection`` opened in read-only mode.
    """
    return duckdb.connect(str(settings.db_path), read_only=True)


@lru_cache(maxsize=1)
def openai_client() -> OpenAI | None:
    """Return an OpenAI client if API credentials are configured.

    Returns:
        ``OpenAI`` instance or ``None`` when the key is empty.
    """
    if not settings.openai_api_key:
        return None
    return OpenAI(api_key=settings.openai_api_key)


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------


@lru_cache(maxsize=EMBEDDING_CACHE_SIZE)
def _embed_query_cached(query: str) -> Tuple[Tuple[float, ...], int]:
    """Call the OpenAI embeddings API and cache the result.

    The tuple return type is required for ``lru_cache`` hashability.

    Args:
        query: Text to embed.

    Returns:
        ``(embedding_tuple, tokens_consumed)``.
    """
    client = openai_client()
    if not client:
        return tuple(), 0
    response = client.embeddings.create(model=settings.embedding_model, input=query)
    return tuple(response.data[0].embedding), response.usage.total_tokens


def embed_query(query: str) -> Tuple[np.ndarray | None, int]:
    """Embed a query, returning a normalised vector and token cost.

    Uses ``_embed_query_cached`` under the hood so repeated identical
    queries cost zero additional API tokens.

    Args:
        query: Text to embed.

    Returns:
        ``(vector, tokens_used)`` - vector is ``None`` when no API key.
    """
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


# ---------------------------------------------------------------------------
# Main search orchestration
# ---------------------------------------------------------------------------


def search_jobs(
    query: str, top_k: int, context: SearchContext | None = None
) -> SearchResponse:
    """Execute a hybrid vector + keyword search and return ranked results.

    Pipeline stages:
    1. Parse query into ``SearchSignals`` (merge with prior context if any).
    2. Embed the query (+ multi-query rewrites) via OpenAI.
    3. Retrieve candidates from FAISS (vector) and DuckDB (keyword).
    4. Apply hard exclusions, rank, rerank.
    5. If confidence is low, retry with a focus query and merge results.
    6. Trim to ``top_k``, build suggestions, and return.

    Args:
        query: Natural-language search query.
        top_k: Maximum results to return.
        context: Optional prior ``SearchContext`` for multi-turn refinement.

    Returns:
        ``SearchResponse`` containing results, suggestions, and metrics.
    """
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

    # -- Vector + keyword retrieval --
    if vector is not None:
        index = load_index()
        distances, indices = index.search(vector.reshape(1, -1), search_k)
        vector_row_ids = [int(i) for i in indices[0] if i >= 0]
        row_hits: Dict[int, int] = {row_id: 1 for row_id in vector_row_ids}
        keyword_row_ids = keyword_candidates(signals, limit=keyword_limit, db_loader=load_db)
        score_map = {int(idx): float(dist) for idx, dist in zip(indices[0], distances[0]) if idx >= 0}

        # Multi-query recall expansion
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

        # Bonus for rows retrieved by multiple queries
        for row_index, hits in row_hits.items():
            if hits > 1 and row_index in score_map:
                score_map[row_index] = round(score_map[row_index] + MULTI_QUERY_HIT_BONUS * (hits - 1), 6)

        row_ids = merge_row_ids(vector_row_ids, keyword_row_ids, limit=keyword_limit)
        candidates = fetch_rows(row_ids, db_loader=load_db)
        retrieval_mode = f"vector+keyword+multiq({len(retrieval_queries)})"
    else:
        # Keyword-only fallback (no OpenAI key)
        row_ids = keyword_candidates(signals, limit=keyword_limit, db_loader=load_db)
        candidates = fetch_rows(row_ids, db_loader=load_db)
        score_map = {}

    # -- Post-retrieval pipeline --
    candidates = apply_hard_exclusions(candidates, signals)
    results = rank_candidates(candidates, score_map, signals)
    results = rerank_results(results, query)
    low_confidence, confidence_metrics = assess_ranking_confidence(results)

    # -- Low-confidence focus-query retry --
    if low_confidence and vector is not None:
        focus_query = build_focus_query(query, signals)
        if focus_query != query:
            retry_vector, retry_tokens = embed_query(focus_query)
            tokens_used += retry_tokens
            if retry_vector is not None:
                index = load_index()
                retry_distances, retry_indices = index.search(retry_vector.reshape(1, -1), search_k)
                retry_vector_row_ids = [int(i) for i in retry_indices[0] if i >= 0]
                retry_keyword_row_ids = keyword_candidates(signals, limit=keyword_limit, db_loader=load_db)
                retry_row_ids = merge_row_ids(retry_vector_row_ids, retry_keyword_row_ids, limit=keyword_limit)
                retry_candidates = fetch_rows(retry_row_ids, db_loader=load_db)
                retry_candidates = apply_hard_exclusions(retry_candidates, signals)
                retry_score_map = {
                    int(idx): float(dist)
                    for idx, dist in zip(retry_indices[0], retry_distances[0])
                    if idx >= 0
                }
                retry_results = rank_candidates(retry_candidates, retry_score_map, signals)
                retry_results = rerank_results(retry_results, focus_query)
                results = merge_ranked_results(results, retry_results)
                confidence_retry_used = True
                retrieval_mode = f"{retrieval_mode}+focus-retry"

    results = results[:top_k]

    # -- Build response --
    suggestions = suggest_refinements(signals)
    elapsed_ms = int((time.time() - started) * 1000)
    context_out = SearchContext(
        query=query,
        signals=signals,
        refinements=context.refinements if context else [],
        history=(context.history if context else []) + [query],
    )
    logger.debug(
        "Search internals query=%r mode=%s retrieval_queries=%s candidates=%d "
        "top_k=%d tokens_used=%d elapsed_ms=%d low_confidence=%s confidence=%s "
        "focus_retry=%s focus_query=%r signals=%s",
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


# ---------------------------------------------------------------------------
# Multi-turn refinement
# ---------------------------------------------------------------------------


def refine_search(query: str, context: SearchContext, top_k: int) -> SearchResponse:
    """Execute a refinement query layered on top of prior conversational context.

    Appends the new query to the refinement history and delegates to
    ``search_jobs`` with the accumulated context.

    Args:
        query: The user's follow-up refinement query.
        context: ``SearchContext`` returned from the previous turn.
        top_k: Maximum results to return.

    Returns:
        ``SearchResponse`` incorporating both old and new intent.
    """
    context.refinements.append(query)
    return search_jobs(query, top_k, context)
