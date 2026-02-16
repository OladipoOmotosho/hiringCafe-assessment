# HiringCafe Assessment — AI Job Search + Refine

## Submission Deliverables (In Brief Order)

1. **Working code**

- Search + Refine implemented (API in `main.py` / `app/`)
- Runnable demo with multi-turn refinement: `python demo.py`

1. **README explanation**

- Approach, ranking, trade-offs, strengths/limits, and improvement ideas (this file)

1. **Tokens report**

- Measured runtime token/cost accounting: `tokens-report.md`

1. **Demo video (optional)**

- Not required for code execution; can be recorded from the demo flow above

This project implements two capabilities over a large `jobs.jsonl` dataset:

1. `Search`: natural-language query → ranked job results.
2. `Refine`: conversational narrowing using context from previous turns.

## Scope Clarification

- This project is an intent-aware job search engine.
- Returned scores represent relative relevance for ranking results.
- Scores are ranking values used to order results for each query.

## Tech Stack

- Backend: FastAPI + DuckDB + FAISS
- Vector model: OpenAI `text-embedding-3-small` for query embeddings
- Frontend: Vite + React

## Data Representation

- Jobs are streamed from `jobs.jsonl` (no full-file load into RAM).
- Metadata is stored in DuckDB (`data/jobs.duckdb`) with one row per indexed job.
- Weighted embeddings are built from the three provided vectors in `v7_processed_job_data`:
  - `0.5 * embedding_explicit_vector`
  - `0.3 * embedding_inferred_vector`
  - `0.2 * embedding_company_vector`
- Weighted vectors are normalized and stored in FAISS (`data/faiss.index`).

## Search + Ranking Approach

1. Parse query signals (keywords, remote intent, org type, seniority, location hints, and negations).
1. Build blended candidates:

- vector retrieval from FAISS (when embeddings are enabled)
- multi-query rewrites for better recall (original + compact intent-focused rewrites)
- keyword retrieval from DuckDB
- deduplicate and merge candidate sets

1. Re-rank candidates with a hybrid score:

- vector similarity
- keyword overlap
- signal boosts (remote, seniority, org-type, mission, location)
- hard exclusions for explicit negation intent (for example, manager/director/executive/onsite families)

1. Apply a lightweight second-pass reranker on top candidates:

- phrase-level query matching
- title keyword coverage
- small matched-signal bonus

1. If top results are low-signal, run one compact focused-query retry and merge the best candidates.
1. Return ranked results, matched signals, score breakdown, and refinement suggestions.

If OpenAI is not configured, the system uses keyword candidate retrieval in DuckDB as fallback.

## Refine Logic

Refine merges conversational context instead of replacing it:

- keywords: union of prior + current
- remote: sticky once requested
- seniority: most recent non-empty value wins
- org_types/location_terms: union of prior + current

This allows flows like:

- `"data science jobs"`
- `"at companies/non-profits that care about social good"`
- `"make it remote"`

## Setup

### 1) Python dependencies

```bash
pip install -r requirements.txt
```

### 2) Environment variables

PowerShell example:

```powershell
$env:JOBS_JSONL_PATH="C:\path\to\jobs.jsonl"
$env:OPENAI_API_KEY="your_key_here"   # optional but recommended
```

Optional variables:

- `DATA_DIR` (default `data`)
- `DB_PATH` (default `data/jobs.duckdb`)
- `INDEX_PATH` (default `data/faiss.index`)
- `FEEDBACK_EVENTS_PATH` (default `data/feedback-events.jsonl`)
- `BATCH_SIZE` (default `500`)
- `PREVIEW_CHARS` (default `280`)
- `REBUILD_INDEX=1` to force re-ingestion/reindexing when running `python -m app.ingest`

Note: API startup (`python main.py`) reuses existing artifacts when present and does not force a rebuild.

## Run the API

```bash
python main.py
```

Endpoints:

- `GET /health`
- `POST /search`
- `POST /refine`
- `POST /feedback`
- `GET /feedback`

## Runnable Demo (5+ queries including refine)

```bash
python demo.py
```

What it does:

- starts API server
- runs multiple search queries
- runs a 3-turn refine conversation
- prints top ranked jobs + suggestions

## Lightweight Evaluation Harness

```bash
python -m app.eval
```

What it does:

- runs a small seed set of 10 representative queries
- computes lightweight ranking/constraint metrics (top score, avg@5, keyword hit rate, exclusion violations, latency, tokens)
- writes JSON report to `data/eval-report.json`

## Feedback Tuning Report

```bash
python -m app.feedback_tuning
```

What it does:

- summarizes click feedback from `data/feedback-events.jsonl`
- reports average rank/score and component averages when available
- suggests small weight adjustments to improve relevance

## Frontend UI

```bash
cd ui
yarn
yarn dev
```

The UI calls:

- `POST /api/search`
- `POST /api/refine`

via Vite proxy to `http://127.0.0.1:8000`.

## Trade-offs and Limitations

- Query embeddings require OpenAI API for best semantic quality.
- Current signal extraction is heuristic (regex/token based), not full LLM intent parsing.
- Company mission/social-good filtering is keyword based in this version.
- Dataset schema can be inconsistent; ingestion uses resilient fallbacks for title/company/location.

## What Works Well / What’s Tricky

Works well:

- broad role search
- iterative narrowing (remote/org/seniority/location)
- large dataset retrieval with FAISS + DuckDB

Tricky:

- ambiguous mission-driven intent without explicit structured tags
- sparse or inconsistent location/metadata across listings

## Why This Meets Evaluation Criteria

- **Results feel right**: hybrid retrieval (vector + keyword), intent-aware boosts, and hard exclusions improve precision for natural-language intent.
- **Thoughtful approach**: architecture is intentionally simple and explainable (streamed ingest, FAISS + DuckDB, deterministic parsing, score breakdown).
- **Handling ambiguity**: robust signal parser supports abbreviations, mission intent, multi-style negation cues (`don't`, `never`, `neither...nor`, `less/fewer`), and conversational refinement state.
- **Handling scale**: ingestion streams `jobs.jsonl`, artifacts are persisted (`data/jobs.duckdb` + `data/faiss.index`), and retrieval is candidate-based re-ranking rather than full-scan ranking.

Validation artifacts:

- Search/refine behavior and parsing logic are covered in `tests/test_api.py` and `tests/test_search.py`.
- Lightweight quality/cost checks are runnable with `python -m app.eval` (writes `data/eval-report.json`).

## If More Time

- richer query intent parser for mission/company values
- learned ranker (LTR) with offline eval set
- advanced explainability per result feature contribution
- stronger quality filters for stale/low-information postings
