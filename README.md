# HiringCafe Assessment — AI Job Search + Refine

This project implements two capabilities over a large `jobs.jsonl` dataset:

1. `Search`: natural-language query → ranked job results.
2. `Refine`: conversational narrowing using context from previous turns.

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

1. Parse query signals (keywords, remote intent, org type, seniority, location hints).
1. Embed query (if `OPENAI_API_KEY` is set) and retrieve top candidates from FAISS.
1. Re-rank candidates with a hybrid score:

- vector similarity
- keyword overlap
- signal boosts (remote, seniority, org-type, location)

1. Return results and refinement suggestions.

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
- `BATCH_SIZE` (default `500`)
- `PREVIEW_CHARS` (default `280`)
- `REBUILD_INDEX=1` to force re-ingestion/reindexing

## Run the API

```bash
python main.py
```

Endpoints:

- `GET /health`
- `POST /search`
- `POST /refine`

## Runnable Demo (5+ queries including refine)

```bash
python demo.py
```

What it does:

- starts API server
- runs multiple search queries
- runs a 3-turn refine conversation
- prints top ranked jobs + suggestions

## Frontend UI

```bash
cd ui
npm install
npm run dev
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

## If More Time

- richer query intent parser for mission/company values
- learned ranker (LTR) with offline eval set
- advanced explainability per result feature contribution
- stronger quality filters for stale/low-information postings
