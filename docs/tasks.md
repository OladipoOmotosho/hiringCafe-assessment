# AI Job Search Tasks

## Backend Core
- [x] Add configuration module (`app/config.py`).
- [x] Define data models (`app/schema.py`).
- [x] Implement search logic (`app/search.py`).
- [x] Implement ingestion + FAISS indexing (`app/ingest.py`).
- [x] Add FastAPI endpoints (`app/api.py`).
- [ ] Add API entrypoint (e.g., `main.py`).
- [ ] Align search logic to ingestion schema and improve ranking.

## Demo & Tooling
- [x] Add Python dependencies (`requirements.txt`).
- [ ] Add CLI demo script (`demo.py`) to start API and run 5+ queries.
- [ ] Add tokens usage report (`tokens-report.md`).

## Frontend UI (AI Discovery)
- [ ] Add minimal Vite/React UI under `ui/`.
- [ ] Port AI discovery UI components (search input, suggestions, results grid).
- [ ] Add API client wrapper for `/search` and `/refine`.

## Documentation
- [x] Add implementation plan (`docs/implementation-plan.md`).
- [ ] Update README with setup, usage, and approach.
- [ ] Add notes on trade-offs, limitations, and next steps.