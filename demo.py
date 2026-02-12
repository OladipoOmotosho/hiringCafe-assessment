from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Tuple

import httpx
from dotenv import load_dotenv

from app.config import settings

load_dotenv()

HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"


def wait_for_health(timeout_s: int = 120) -> None:
    started = time.time()
    while time.time() - started < timeout_s:
        try:
            response = httpx.get(f"{BASE_URL}/health", timeout=2.0)
            if response.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError("API did not become healthy in time")


def run_query(payload: Dict[str, Any], endpoint: str = "/search") -> Dict[str, Any]:
    response = httpx.post(f"{BASE_URL}{endpoint}", json=payload, timeout=90.0)
    response.raise_for_status()
    return response.json()


def print_results(title: str, response: Dict[str, Any], max_rows: int = 5) -> None:
    print(f"\n=== {title} ===")
    print(f"query: {response.get('query')}")
    print(f"elapsed_ms: {response.get('elapsed_ms')} | tokens_used: {response.get('tokens_used')}")
    for idx, job in enumerate(response.get("results", [])[:max_rows], start=1):
        print(
            f"{idx}. {job.get('title', '')} | {job.get('company', '')} | {job.get('location', '')} | score={job.get('score')}"
        )
        if job.get("matched_signals"):
            print(f"   matched: {', '.join(job['matched_signals'])}")
    suggestions = response.get("suggestions", [])
    if suggestions:
        print("suggestions:")
        for s in suggestions[:3]:
            print(f"- {s.get('text')} ({s.get('reason')})")


def run_demo() -> None:
    jobs_path = os.getenv("JOBS_JSONL_PATH", "").strip()
    has_index_artifacts = settings.db_path.exists() and settings.index_path.exists()
    if not jobs_path and not has_index_artifacts:
        raise RuntimeError(
            "Set JOBS_JSONL_PATH before running demo.py, e.g.\n"
            "PowerShell: $env:JOBS_JSONL_PATH='C:\\path\\to\\jobs.jsonl'"
        )

    print("Starting API server...")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", HOST, "--port", str(PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        wait_for_health()
        print("API is healthy. Running demo queries...")

        independent_queries = [
            {"query": "machine learning engineer jobs in california", "top_k": 10},
            {"query": "biostatistics scientist roles at hospitals", "top_k": 10},
        ]

        for payload in independent_queries:
            res = run_query(payload, endpoint="/search")
            print_results("SEARCH", res)

        # Refine conversation (3 turns)
        turn1 = run_query({"query": "data science jobs", "top_k": 10}, endpoint="/search")
        print_results("REFINE TURN 1", turn1)

        context = turn1["context"]
        turn2 = run_query(
            {
                "query": "at companies or non-profits that care about social good",
                "context": context,
                "top_k": 10,
            },
            endpoint="/refine",
        )
        print_results("REFINE TURN 2", turn2)

        context = turn2["context"]
        turn3 = run_query(
            {
                "query": "make it remote",
                "context": context,
                "top_k": 10,
            },
            endpoint="/refine",
        )
        print_results("REFINE TURN 3", turn3)

        print("\nDemo completed successfully.")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    run_demo()
