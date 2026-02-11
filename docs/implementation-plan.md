# AI Job Search – Implementation Plan

## Goals
- Implement AI-powered job discovery with **search** and **refine** capabilities over a large JSONL dataset.
- Provide a CLI demo (`python demo.py`) and a lightweight UI inspired by the Fake-Job-Posting-Tracker AI Discovery flow.
- Keep the repository under 10 changed files, with each file under 350 LOC.

## Constraints
- Data file is 8.4GB (external): must be streamed, indexed, and cached.
- Use Python + FAISS for vector search.
- Avoid prop drilling in UI; use lightweight state container.
- Apply DRY, separation of concerns, and reusable components.

## Architecture Overview

### Backend (FastAPI)
- `app/api.py` – FastAPI router with `/search` and `/refine` endpoints.
- `app/ingest.py` – streaming JSONL ingestion into DuckDB + FAISS index build.
- `app/search.py` – hybrid retrieval (keyword + vector) + ranking logic.
- `app/schemas.py` – typed request/response models.
- `app/config.py` – env config (dataset path, cache dir, model).

### Vector + Data Storage
- **DuckDB** stores metadata (id, title, company, location, preview, embedding offset).
- **FAISS** stores 3 embeddings (explicit, inferred, company) merged as a weighted vector.
- Cache artifacts stored under `data/` (not committed):
  - `jobs.duckdb`
  - `faiss.index`
  - `embeddings.npy`

### Search Flow
1. Parse query into signals (keywords, seniority, remote, org type, location).
2. Create embedding for query (OpenAI `text-embedding-3-small`).
3. FAISS search for top-k candidates.
4. Re-rank using:
   - Vector similarity (weighted)
   - Keyword overlap
   - Signal boosts (remote, org type, location, seniority)
5. Return results + refinement suggestions.

### Refine Flow
- Accept context from previous search (history + signals + refinements).
- Merge new query signals into context.
- Re-run hybrid search with updated signals.
- Append suggestions based on missing filters and low-signal coverage.

## Tasks

### 1) Backend Core
- [ ] Add `app/config.py` for env configuration.
- [ ] Add `app/ingest.py` streaming ingest + index build.
- [ ] Add `app/search.py` with hybrid search + ranking.
- [ ] Add `app/api.py` with `/search` and `/refine` routes.
- [ ] Add `demo.py` CLI that starts server + runs example queries.

### 2) Frontend UI (AI Discovery)
- [ ] Add minimal Vite app under `ui/`.
- [ ] Add AI search input component and results grid.
- [ ] Add refinement suggestions + applied filters.
- [ ] Add API client wrapper for `/search` and `/refine`.

### 3) Documentation
- [ ] Update `README.md` with setup + usage.
- [ ] Add `tokens-report.md` with estimates and notes.
- [ ] Provide example queries and refinement flow.

## Deliverables Checklist
- [ ] `python demo.py` starts API + prints 5 query results.
- [ ] Refinement flow demonstrated in CLI output.
- [ ] UI shows AI discovery search flow.
- [ ] README describes approach, trade-offs, and limitations.
- [ ] Tokens report included.

## Risks & Mitigations
- **Large dataset** → Stream ingestion + incremental indexing.
- **Embedding cost** → Cache query embeddings and reuse signals.
- **Speed** → FAISS + DuckDB + in-memory LRU caching.
- **Ambiguity** → Heuristic signal extraction + optional LLM parsing.

## Timeline (≤24h)
1. Ingest/index + search backend (6–8h)
2. Refinement logic + CLI demo (4–6h)
3. UI & styling (4–6h)
4. Docs & polish (2–4h)