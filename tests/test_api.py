from __future__ import annotations

import logging
from types import SimpleNamespace

from app.api import startup
from app.schema import SearchContext, SearchSignals
from tests.conftest import create_test_client


def test_search_endpoint_contract(monkeypatch) -> None:
    client = create_test_client(monkeypatch)

    response = client.post("/search", json={"query": "data science jobs", "top_k": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "data science jobs"
    assert "context" in payload
    assert "results" in payload
    assert "elapsed_ms" in payload
    assert "tokens_used" in payload


def test_refine_endpoint_contract(monkeypatch) -> None:
    client = create_test_client(monkeypatch)
    context = SearchContext(
        query="data science jobs",
        signals=SearchSignals(keywords=["data", "science"]),
        history=["data science jobs"],
        refinements=[],
    )

    response = client.post(
        "/refine",
        json={"query": "make it remote", "context": context.model_dump(), "top_k": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "make it remote"
    assert payload["context"]["history"][-1] == "make it remote"


def test_search_whitespace_query_returns_400(monkeypatch) -> None:
    client = create_test_client(monkeypatch)

    response = client.post("/search", json={"query": "   ", "top_k": 10})

    assert response.status_code == 400
    assert response.json()["detail"] == "Query is required"


def test_search_empty_query_returns_422(monkeypatch) -> None:
    client = create_test_client(monkeypatch)

    response = client.post("/search", json={"query": "", "top_k": 10})

    assert response.status_code == 422


def test_refine_malformed_context_returns_422(monkeypatch) -> None:
    client = create_test_client(monkeypatch)

    response = client.post(
        "/refine",
        json={"query": "make it remote", "context": {"history": ["x"]}, "top_k": 10},
    )

    assert response.status_code == 422


def test_token_metrics_endpoint_returns_shape(monkeypatch) -> None:
    client = create_test_client(monkeypatch)

    response = client.get("/metrics/tokens?recent_limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert "totals" in payload
    assert "pricing" in payload
    assert "recent_requests" in payload


def test_feedback_endpoint_accepts_payload(monkeypatch) -> None:
    recorded = []

    def fake_record_feedback(payload):
        recorded.append(payload)
        return {"status": "ok"}

    monkeypatch.setattr("app.api.record_feedback", fake_record_feedback)
    client = create_test_client(monkeypatch)

    response = client.post(
        "/feedback",
        json={
            "event_type": "apply_click",
            "query": "senior remote data jobs",
            "job_id": "job-1",
            "rank": 1,
            "score": 0.5,
            "source": "search",
            "context": {
                "query": "senior remote data jobs",
                "signals": {
                    "keywords": ["senior", "data"],
                    "excluded_keywords": [],
                    "remote": True,
                    "seniority": "senior",
                    "org_types": [],
                    "location_terms": [],
                },
                "refinements": [],
                "history": ["senior remote data jobs"],
            },
        },
    )

    assert response.status_code == 200
    assert recorded


def test_startup_logs_warning_when_rebuild_flag_set(monkeypatch, caplog) -> None:
    calls: list[bool] = []

    def fake_build_index(force_rebuild: bool = False) -> None:
        calls.append(force_rebuild)

    monkeypatch.setattr("app.api.settings", SimpleNamespace(rebuild_index=True))
    monkeypatch.setattr("app.api.build_index", fake_build_index)

    with caplog.at_level(logging.WARNING):
        startup()

    assert "REBUILD_INDEX is set" in caplog.text
    assert calls == [False]
