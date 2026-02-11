from __future__ import annotations

import re
import time
from functools import lru_cache
from typing import Dict, Iterable, List, Tuple

import duckdb
import faiss
import numpy as np
from openai import OpenAI

from app.config import settings
from app.schema import JobResult, RefinementSuggestion, SearchContext, SearchResponse, SearchSignals
from app.ingest import build_index

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
}

SENIORITY = ["intern", "junior", "mid", "senior", "staff", "principal", "lead"]
ORG_TYPES = ["nonprofit", "non-profit", "ngo", "startup", "government", "public"]


@lru_cache(maxsize=1)
def load_index() -> faiss.Index:
    if not settings.index_path.exists() or not settings.db_path.exists():
        build_index()
    return faiss.read_index(str(settings.index_path))


@lru_cache(maxsize=1)
def load_db() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(settings.db_path), read_only=True)


@lru_cache(maxsize=1)
def openai_client() -> OpenAI | None:
    if not settings.openai_api_key:
        return None
    return OpenAI(api_key=settings.openai_api_key)


def tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9]+", text.lower()) if t not in STOPWORDS]


def parse_signals(query: str) -> SearchSignals:
    tokens = tokenize(query)
    seniority = next((s for s in SENIORITY if s in tokens), None)
    org_types = [o for o in ORG_TYPES if o in query.lower()]
    remote = "remote" in query.lower() or "work from home" in query.lower()
    location_terms = re.findall(r"in ([a-zA-Z\s,]+)", query.lower())
    return SearchSignals(
        keywords=tokens,
        remote=remote,
        seniority=seniority,
        org_types=org_types,
        location_terms=[t.strip() for t in location_terms if t.strip()],
    )


def embed_query(query: str) -> Tuple[np.ndarray | None, int]:
    client = openai_client()
    if not client:
        return None, 0
    response = client.embeddings.create(model=settings.embedding_model, input=query)
    vector = np.array(response.data[0].embedding, dtype=np.float32)
    faiss.normalize_L2(vector.reshape(1, -1))
    return vector, response.usage.total_tokens


def keyword_score(text: str, keywords: Iterable[str]) -> float:
    if not keywords:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for k in keywords if k in text_lower)
    return hits / max(len(list(keywords)), 1)


def signal_boost(row: Dict, signals: SearchSignals) -> Tuple[float, List[str]]:
    boost = 0.0
    matched: List[str] = []
    haystack = f"{row['title']} {row['company']} {row['location']} {row['preview']}".lower()
    if signals.remote and "remote" in haystack:
        boost += 0.15
        matched.append("remote")
    if signals.seniority and signals.seniority in haystack:
        boost += 0.1
        matched.append(signals.seniority)
    for org in signals.org_types:
        if org in haystack:
            boost += 0.05
            matched.append(org)
    for loc in signals.location_terms:
        if loc in haystack:
            boost += 0.05
            matched.append(loc)
    return boost, matched


def fetch_rows(row_ids: List[int]) -> List[Dict]:
    if not row_ids:
        return []
    con = load_db()
    query = "select row_index, id, title, company, location, apply_url, preview from jobs where row_index in (" + ",".join(
        [str(i) for i in row_ids]
    ) + ")"
    rows = con.execute(query).fetchall()
    return [
        {
            "row_index": r[0],
            "id": r[1],
            "title": r[2],
            "company": r[3],
            "location": r[4],
            "apply_url": r[5],
            "preview": r[6],
        }
        for r in rows
    ]


def search_jobs(query: str, top_k: int, context: SearchContext | None = None) -> SearchResponse:
    started = time.time()
    signals = parse_signals(query)
    if context:
        merged = context.signals.model_dump()
        merged.update(signals.model_dump())
        signals = SearchSignals(**merged)

    vector, tokens_used = embed_query(query)
    results: List[JobResult] = []

    if vector is not None:
        index = load_index()
        search_k = min(top_k * 10, 500)
        distances, indices = index.search(vector.reshape(1, -1), search_k)
        row_ids = [int(i) for i in indices[0] if i >= 0]
        candidates = fetch_rows(row_ids)
        score_map = {idx: float(dist) for idx, dist in zip(indices[0], distances[0])}
    else:
        candidates = fetch_rows(list(range(0, top_k * 10)))
        score_map = {}

    for row in candidates:
        text = f"{row['title']} {row['preview']}"
        kw_score = keyword_score(text, signals.keywords)
        vec_score = score_map.get(row["row_index"], 0.0)
        boost, matched = signal_boost(row, signals)
        score = 0.65 * vec_score + 0.25 * kw_score + boost
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
    return SearchResponse(
        query=query,
        context=context_out,
        results=results,
        suggestions=suggestions,
        elapsed_ms=elapsed_ms,
        tokens_used=tokens_used,
    )


def suggest_refinements(signals: SearchSignals) -> List[RefinementSuggestion]:
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
    context.refinements.append(query)
    return search_jobs(query, top_k, context)