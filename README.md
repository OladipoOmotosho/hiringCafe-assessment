# HiringCafe Assessment — AI Job Search + Refine

## Submission Deliverables (In Brief Order)

1. **Working code**

- Search + Refine implemented (API in `main.py` / `app/`)
- Single-command demo: `python demo.py` (starts backend + runs queries + launches frontend UI)

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

## Runnable Demo (single command)

```bash
python demo.py
```

What it does:

1. Starts the backend API server (or reuses a running one)
2. Runs 4 independent search queries + a 3-turn refine conversation
3. Prints ranked results, matched signals, and refinement suggestions
4. Launches the frontend UI (if `ui/node_modules` is present)
5. Keeps both backend and frontend alive for interactive use

After the automated queries finish, open **<http://localhost:5173>** in your browser to use the UI.
Press `Ctrl+C` to stop all services.

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

The frontend is launched automatically by `python demo.py`. To run it manually:

```bash
cd ui
yarn          # install deps (first time only)
yarn dev      # start Vite dev server on http://localhost:5173
```

The UI calls:

- `POST /api/search`
- `POST /api/refine`

via Vite proxy to `http://127.0.0.1:8000`.

## Trade-offs and Limitations

- Query embeddings require OpenAI API for best semantic quality.
- Current signal extraction is heuristic (regex/token based), not full LLM intent parsing.
- Company mission/social-good filtering uses expanded keyword + known-org pattern matching (40+ terms, 20+ org patterns mined from dataset) since the data lacks structured mission/industry tags.
- Dataset schema can be inconsistent; ingestion uses resilient fallbacks for title/company/location.

## What Works Well / What’s Tricky

**Works well:**

- **Broad role retrieval** — queries like `"remote software engineer"` return relevant results fast (e.g., _Staff Software Engineer, Ads – Quora (Remote)_ at 0.86, with signals correctly detecting `remote`).
- **Iterative multi-turn refinement** — starting with `"software engineer"`, then refining to `"remote only"`, then `"senior level, not management"` progressively narrows the result set; exclusion signals like `not management` are respected via negation parsing.
- **Seniority + role queries** — `"senior product manager"` returns highly relevant results (0.95+ scores) with `seniority=senior` correctly extracted.
- **Keyword negation** — `"machine learning engineer but not management"` excludes management-titled results and deprioritizes managerial content (negation penalty applied).
- **Abbreviation expansion** — queries with `"ml engineer"` or `"ai engineer"` expand to `"machine learning"` / `"artificial intelligence"` via the `ABBREVIATION_EXPANSIONS` map.
- **Community/health verticals** — `"community health worker"` returns precise title matches (0.87+ scores) from orgs like Advance Community Health, St. Joseph's Health.
- **Score breakdown transparency** — every result includes `vector_score`, `keyword_score`, `signal_adjustment`, and `rerank_adjustment` so ranking is fully explainable.

**Tricky:**

- **Mission-driven intent is inherently ambiguous** — `"social impact jobs at nonprofits"` relies on keyword matching against titles/previews/companies since the dataset has no structured `mission` tag. We expanded to 40+ match terms and 20+ known org patterns (Volunteers of America, Catholic Charities, YMCA, Goodwill, etc.) but edge cases remain.
- **Location metadata is sparse** — many jobs have empty `location` fields in the dataset. `"data scientist in New York"` correctly parses the location signal but can't filter on it when the field is missing; results fall back to vector relevance.
- **Confidence is conservative** — the confidence heuristic (`top_score ≥ 0.30` and `spread ≥ 0.03`) can read as `null` for well-distributed result sets, which is intentional (avoids false certainty) but may confuse users.
- **Multi-turn state is stateless on the server** — context is passed round-trip via JSON, so the client must persist and forward `context` between calls; any dropped context resets refinement state.

## Why This Meets Evaluation Criteria

- **Results feel right**: hybrid retrieval (vector + keyword), intent-aware boosts, and hard exclusions improve precision for natural-language intent.
- **Thoughtful approach**: architecture is intentionally simple and explainable (streamed ingest, FAISS + DuckDB, deterministic parsing, score breakdown).
- **Handling ambiguity**: robust signal parser supports abbreviations, mission intent, multi-style negation cues (`don't`, `never`, `neither...nor`, `less/fewer`), and conversational refinement state.
- **Handling scale**: ingestion streams `jobs.jsonl`, artifacts are persisted (`data/jobs.duckdb` + `data/faiss.index`), and retrieval is candidate-based re-ranking rather than full-scan ranking.

Validation artifacts:

- Search/refine behavior and parsing logic are covered in `tests/test_api.py` and `tests/test_search.py`.
- Lightweight quality/cost checks are runnable with `python -m app.eval` (writes `data/eval-report.json`).

## Time Spent

Approximately 12–15 hours over multiple sessions. AI tools used during development: GitHub Copilot, ChatGPT.

## If More Time

- **Structured mission/industry tags at ingest** — extract `organization_type` and `industry` from `v5_processed_company_data` into DuckDB columns for real faceted filtering (currently we match against free-text only).
- **Learned ranker (LTR)** — train a lightweight re-ranker on offline relevance judgments instead of hand-tuned signal weights.
- **LLM-powered intent parsing** — replace regex/heuristic signal extraction with a small LLM call to classify intent slots (role, seniority, exclusions, mission preference) for edge cases.
- **Location normalization** — geocode raw location strings during ingest to enable proximity-based filtering, addressing the sparse location field problem.
- **Stronger quality filters** — detect and deprioritize stale, duplicate, or low-information postings at ingest time.
