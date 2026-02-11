from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schema import RefineRequest, SearchRequest, SearchResponse
from app.search import refine_search, search_jobs
from app.ingest import build_index

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
    try:
        build_index()
    except FileNotFoundError:
        pass


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse)
def search(payload: SearchRequest) -> SearchResponse:
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
    return search_jobs(payload.query, payload.top_k)


@app.post("/refine", response_model=SearchResponse)
def refine(payload: RefineRequest) -> SearchResponse:
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
    return refine_search(payload.query, payload.context, payload.top_k)