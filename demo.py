from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

import httpx
from dotenv import load_dotenv

from app.config import settings

load_dotenv()

HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"
UI_DIR = Path(__file__).resolve().parent / "ui"
DEFAULT_HEALTH_TIMEOUT_WITH_INDEX = 120
DEFAULT_HEALTH_TIMEOUT_WITHOUT_INDEX = 0


def is_healthy(timeout_s: float = 2.0) -> bool:
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=timeout_s)
        return response.status_code == 200
    except Exception:
        return False


def wait_for_health(
    timeout_s: int = DEFAULT_HEALTH_TIMEOUT_WITH_INDEX,
    server: subprocess.Popen[str] | None = None,
) -> None:
    if timeout_s <= 0:
        while True:
            if is_healthy(timeout_s=2.0):
                return
            if server is not None and server.poll() is not None:
                raise RuntimeError("API server exited during startup before becoming healthy")
            time.sleep(1)

    started = time.time()
    while time.time() - started < timeout_s:
        if is_healthy(timeout_s=2.0):
            return
        if server is not None and server.poll() is not None:
            raise RuntimeError("API server exited during startup before becoming healthy")
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

    using_existing_server = is_healthy()
    server: subprocess.Popen[str] | None = None

    if using_existing_server:
        print("Using existing healthy API server...")
    else:
        print("Starting API server...")
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", HOST, "--port", str(PORT)],
            stdout=None,
            stderr=None,
        )

    try:
        health_timeout = (
            DEFAULT_HEALTH_TIMEOUT_WITH_INDEX
            if has_index_artifacts
            else int(os.getenv("DEMO_HEALTH_TIMEOUT_S", str(DEFAULT_HEALTH_TIMEOUT_WITHOUT_INDEX)))
        )
        wait_for_health(timeout_s=health_timeout, server=server)
        print("API is healthy. Running demo queries...")

        independent_queries = [
            {"query": "machine learning engineer jobs in california", "top_k": 10},
            {"query": "biostatistics scientist roles at hospitals", "top_k": 10},
            {"query": "remote senior ml roles at mission-driven companies", "top_k": 10},
            {"query": "data science jobs in new york not management", "top_k": 10},
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
    except Exception:
        # On demo failure, still try to keep server/UI alive if launched
        import traceback
        traceback.print_exc()
        if server is not None:
            server.terminate()
        raise

    # --- Launch frontend UI and keep everything running ---
    frontend: subprocess.Popen[str] | None = None
    yarn_bin = shutil.which("yarn")
    npm_bin = shutil.which("npm")

    if UI_DIR.exists() and (UI_DIR / "node_modules").exists() and (yarn_bin or npm_bin):
        print("\n--- Starting frontend UI ---")
        run_cmd = [yarn_bin or npm_bin, "dev"]  # type: ignore[list-item]
        frontend = subprocess.Popen(run_cmd, cwd=str(UI_DIR), stdout=None, stderr=None)
        time.sleep(3)  # give Vite a moment
        print(f"Frontend running at http://localhost:5173")
    elif UI_DIR.exists():
        print("\nNote: Frontend UI dependencies not installed. Run 'cd ui && yarn' to enable the UI.")

    if server is not None or frontend is not None:
        print(f"\nBackend API: {BASE_URL}")
        if frontend is not None:
            print(f"Frontend UI: http://localhost:5173")
        print("Press Ctrl+C to stop all services.\n")
        try:
            while True:
                if server is not None and server.poll() is not None:
                    print("Backend server exited unexpectedly.")
                    break
                if frontend is not None and frontend.poll() is not None:
                    print("Frontend server exited unexpectedly.")
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            if frontend is not None:
                frontend.terminate()
                try:
                    frontend.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    frontend.kill()
            if server is not None:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
    else:
        print(f"\nUsed existing server at {BASE_URL}. Start frontend separately with: cd ui && yarn dev")


if __name__ == "__main__":
    run_demo()
