from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import app
from app.schema import SearchContext, SearchResponse, SearchSignals


def _fake_response(query: str) -> SearchResponse:
    return SearchResponse(
        query=query,
        context=SearchContext(
            query=query,
            signals=SearchSignals(keywords=["data", "science"]),
            history=[query],
            refinements=[],
        ),
        results=[],
        suggestions=[],
        elapsed_ms=12,
        tokens_used=0,
    )


def create_test_client(monkeypatch) -> TestClient:
    def fake_search_jobs(query: str, top_k: int) -> SearchResponse:
        return _fake_response(query)

    def fake_refine_search(query: str, context: SearchContext, top_k: int) -> SearchResponse:
        response = _fake_response(query)
        response.context = SearchContext(
            query=query,
            signals=context.signals,
            history=[*context.history, query],
            refinements=[*context.refinements, query],
        )
        return response

    monkeypatch.setattr("app.api.search_jobs", fake_search_jobs)
    monkeypatch.setattr("app.api.refine_search", fake_refine_search)
    return TestClient(app)
