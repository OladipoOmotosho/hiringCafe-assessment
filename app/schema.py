from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class SearchSignals(BaseModel):
    keywords: List[str] = Field(default_factory=list)
    excluded_keywords: List[str] = Field(default_factory=list)
    remote: bool = False
    seniority: Optional[str] = None
    org_types: List[str] = Field(default_factory=list)
    location_terms: List[str] = Field(default_factory=list)


class SearchContext(BaseModel):
    query: str
    signals: SearchSignals = Field(default_factory=SearchSignals)
    refinements: List[str] = Field(default_factory=list)
    history: List[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=20, ge=1, le=100)


class RefineRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    context: SearchContext
    top_k: int = Field(default=20, ge=1, le=100)


class ScoreBreakdown(BaseModel):
    vector_score: float
    keyword_score: float
    signal_adjustment: float
    rerank_adjustment: float = 0.0
    final_score: float


class JobResult(BaseModel):
    id: str
    title: str
    company: str
    location: str
    apply_url: str
    score: float
    preview: str
    matched_signals: List[str] = Field(default_factory=list)
    score_breakdown: Optional[ScoreBreakdown] = None


class RefinementSuggestion(BaseModel):
    text: str
    reason: str


class SearchResponse(BaseModel):
    query: str
    context: SearchContext
    results: List[JobResult]
    suggestions: List[RefinementSuggestion]
    elapsed_ms: int
    tokens_used: int


class FeedbackRequest(BaseModel):
    event_type: str = Field(default="click", min_length=1, max_length=32)
    query: str = Field(..., min_length=1, max_length=500)
    job_id: str = Field(..., min_length=1, max_length=200)
    rank: int = Field(..., ge=1, le=500)
    score: float = Field(..., ge=0.0)
    source: str = Field(default="search", min_length=1, max_length=32)
    context: Optional[SearchContext] = None
    matched_signals: List[str] = Field(default_factory=list)
    score_breakdown: Optional[ScoreBreakdown] = None
