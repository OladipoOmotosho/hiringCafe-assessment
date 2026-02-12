# AI Job Search Tasks

## Backend Core

- [x] Add configuration module (`app/config.py`).
- [x] Define data models (`app/schema.py`).
- [x] Implement search logic (`app/search.py`).
- [x] Implement ingestion + FAISS indexing (`app/ingest.py`).
- [x] Add FastAPI endpoints (`app/api.py`).
- [x] Add API entrypoint (e.g., `main.py`).
- [x] Align search logic to ingestion schema and improve ranking.

## Demo & Tooling

- [x] Add Python dependencies (`requirements.txt`).
- [x] Add CLI demo script (`demo.py`) to start API and run 5+ queries.
- [x] Add tokens usage report (`tokens-report.md`).

## Frontend UI (AI Discovery)

- [x] Add minimal Vite/React UI under `ui/`.
- [x] Port AI discovery UI components (search input, suggestions, results grid).
- [x] Add API client wrapper for `/search` and `/refine`.

## Documentation

- [x] Add implementation plan (`docs/implementation-plan.md`).
- [x] Update README with setup, usage, and approach.
- [x] Add notes on trade-offs, limitations, and next steps.
