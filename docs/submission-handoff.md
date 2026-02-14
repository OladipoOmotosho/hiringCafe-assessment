# Submission Handoff (Ready-to-Send)

## 1) Final Pre-Submission Checklist

- [x] Search + Refine capabilities implemented
- [x] Demo script exists and is runnable: `python demo.py`
- [x] README explains approach, ranking, trade-offs, ambiguity handling, and scale handling
- [x] Tokens report is present with measured runtime usage: `tokens-report.md`
- [x] Focused tests pass (`tests/test_api.py`, `tests/test_search.py`)
- [x] Frontend command flow uses Yarn (`yarn`, `yarn dev`, `yarn build`)
- [x] Scope clarified: relevance ranking only
- [x] Non-assignment materials moved under `docs/out-of-scope/`

## 2) Commands to Verify Before Sending

```bash
python -m pytest -q tests/test_api.py tests/test_search.py
python -m app.eval
python demo.py
```

Frontend (optional visual check):

```bash
cd ui
yarn
yarn dev
```

## 3) Suggested Email Body

Subject: HiringCafe Take-Home Submission — AI Job Search + Refine

Hi Hamed and Ali,

Please find my take-home submission attached (or in the private repo link below).

Highlights:

- Implemented both required capabilities: Search and Refine.
- Added a runnable demo script with 5+ queries including multi-turn refinement.
- Built a scalable retrieval architecture using streamed ingest + FAISS + DuckDB.
- Included measured token usage and cost tracking in `tokens-report.md`.

Run instructions:

- `python demo.py` (demo)
- `python main.py` (API)
- `python -m app.eval` (lightweight quality/cost evaluation)

Repository / archive:

- <YOUR_LINK_OR_ATTACHMENT>

Estimated time spent:

- <YOUR_HOURS>

Thank you,
<YOUR_NAME>

## 4) What to Mention Verbally (If Asked)

- You intentionally optimized for relevance under ambiguity using hybrid retrieval + deterministic intent parsing.
- You handled scale by streaming ingestion and persistent retrieval artifacts (`DuckDB` + `FAISS`).
- You improved query robustness with broad negation handling and hard exclusion filtering.
- You explicitly kept scope aligned to assignment goals (smart intent-based search and refine only).
