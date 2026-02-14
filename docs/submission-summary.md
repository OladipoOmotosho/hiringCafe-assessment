# HiringCafe Take-Home — Executive Summary

## Objective

Build an AI-powered job discovery prototype with two capabilities:

1. **Search**: natural-language query to relevant jobs.
2. **Refine**: conversational narrowing across turns.

This submission is intentionally scoped to **intent-based relevance ranking**.

## What Was Built

- Hybrid retrieval and ranking engine over `jobs.jsonl` (100k-scale) using:
  - FAISS vector retrieval (semantic relevance)
  - DuckDB keyword retrieval (lexical precision)
  - Signal-aware re-ranking (remote/seniority/org/location/mission + negation handling)
- Conversational refinement context merge:
  - sticky remote preference
  - merged keywords/org/location terms
  - latest explicit seniority preference
- Robust ambiguity handling:
  - abbreviation expansion (e.g., `ml` -> `machine learning`)
  - broad negation cues (`don't`, `never`, `neither...nor`, `less/fewer`)
  - hard exclusion filtering for explicit disallowed role families
- Score transparency:
  - per-result score breakdown in API
  - UI relevance display as percentage with raw decimal tooltip

## Scale and Performance Approach

- Streaming ingest into persistent artifacts:
  - `data/jobs.duckdb`
  - `data/faiss.index`
- Startup artifact reuse (no unnecessary full re-ingest on each app run)
- Candidate-based ranking over merged retrieval sets instead of full scan ranking

## Quality and Validation

- Focused automated tests cover API contracts and search behavior:
  - `tests/test_api.py`
  - `tests/test_search.py`
- Lightweight evaluation harness (`python -m app.eval`) provides:
  - top-score and avg@5 signals
  - keyword hit rate
  - exclusion-violation checks
  - latency and token usage snapshot

## Token Usage (Measured)

From latest eval run (`data/eval-report.json`):

- Queries: 10
- Total tokens used: 57
- Mean tokens/query: 5.7
- Estimated runtime cost at configured pricing: **$0.00000114**

This is far below the stated $10 budget ceiling.

## Deliverables Mapping

- **Working code**: Search + Refine implemented and runnable.
- **Demo**: `python demo.py` executes multi-query + multi-turn flow.
- **README**: approach, relevance strategy, trade-offs, strengths, limits, and improvements.
- **Tokens report**: measured runtime token and cost accounting in `tokens-report.md`.

## Quick Run Commands

```bash
python main.py
python demo.py
python -m pytest -q tests/test_api.py tests/test_search.py
python -m app.eval
```
