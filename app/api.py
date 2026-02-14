from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.ingest import build_index
from app.feedback import get_feedback_summary, record_feedback
from app.metrics import get_token_metrics, record_token_usage
from app.schema import FeedbackRequest, RefineRequest, SearchRequest, SearchResponse
from app.search import refine_search, search_jobs

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Job Search", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    """Build search artifacts at startup when required."""
    try:
        if settings.rebuild_index:
            logger.warning(
                "REBUILD_INDEX is set, but API startup reuses existing artifacts; use 'python -m app.ingest' to force rebuild"
            )
        build_index(force_rebuild=False)
        logger.info("Startup initialization completed")
    except FileNotFoundError:
        logger.warning("Skipping index build because JOBS_JSONL_PATH is not configured")


@app.get("/health")
def health() -> dict:
    """Return service health status."""
    return {"status": "ok"}


@app.get("/metrics/tokens")
def token_metrics(recent_limit: int = 20) -> dict:
    """Return aggregate token/cost metrics and recent request records."""
    return get_token_metrics(recent_limit)


@app.get("/feedback")
def feedback_summary(recent_limit: int = 20) -> dict:
    """Return a summary of recent feedback events."""
    return get_feedback_summary(recent_limit)


@app.post("/feedback")
def feedback(payload: FeedbackRequest) -> dict:
    """Record user feedback (click/apply) for offline tuning."""
    entry = record_feedback(payload.model_dump())
    return {"status": "ok", "event": entry}


@app.post("/search", response_model=SearchResponse)
def search(payload: SearchRequest) -> SearchResponse:
    """Execute a natural-language job search request."""
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
    try:
        response = search_jobs(payload.query, payload.top_k)
        metrics_entry = record_token_usage(
            endpoint="/search",
            query=payload.query,
            tokens_used=response.tokens_used,
            elapsed_ms=response.elapsed_ms,
        )
        logger.info(
            "Search completed query=%r top_k=%d elapsed_ms=%d tokens_used=%d usd=%s results=%d",
            payload.query,
            payload.top_k,
            response.elapsed_ms,
            response.tokens_used,
            metrics_entry["estimated_usd_cost"],
            len(response.results),
        )
        return response
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/refine", response_model=SearchResponse)
def refine(payload: RefineRequest) -> SearchResponse:
    """Execute conversational refinement using prior search context."""
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
    try:
        response = refine_search(payload.query, payload.context, payload.top_k)
        metrics_entry = record_token_usage(
            endpoint="/refine",
            query=payload.query,
            tokens_used=response.tokens_used,
            elapsed_ms=response.elapsed_ms,
        )
        logger.info(
            "Refine completed query=%r top_k=%d elapsed_ms=%d tokens_used=%d usd=%s results=%d",
            payload.query,
            payload.top_k,
            response.elapsed_ms,
            response.tokens_used,
            metrics_entry["estimated_usd_cost"],
            len(response.results),
        )
        return response
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc