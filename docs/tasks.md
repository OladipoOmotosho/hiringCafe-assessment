# AI Job Search Remediation Tasks (Batch Rollout)

This task list executes the gaps from `.agent/evaluation.md` in controlled batches.

## Batch 1 — Reliability and Code Quality Foundation (P0)

- [x] Add named constants for ranking weights and boost values in `app/search.py`.
- [x] Add public-function docstrings in `app/search.py`, `app/ingest.py`, `app/api.py`, `app/config.py`.
- [x] Add query embedding LRU cache in `app/search.py`.
- [x] Add logging setup and request-level logs (query, elapsed_ms, tokens_used).
- [x] Verify no schema changes to `SearchResponse`.
- [ ] Run `python demo.py` and confirm existing flow still works.

## Batch 2 — Relevance and Query Understanding (P1)

- [x] Expand stopword list with filler terms (find/show/me/some/please/need/etc).
- [x] Add abbreviation expansion (`ml`, `ds`, `swe`, etc.) during normalization.
- [x] Improve location extraction to reduce false positives.
- [x] Add mission-driven/social-good intent hints in parsing/scoring.
- [x] Add minimal negation handling for phrases like “not management”.
- [x] Add at least 2 edge-case queries to `demo.py`.
- [ ] Validate Batch 2 output quality from full `python demo.py` runtime.

## Batch 3 — Tests and Regression Safety Net (P1)

- [x] Create `tests/` directory and baseline test config.
- [x] Add unit tests for `parse_signals()`.
- [x] Add unit tests for `merge_signals()`.
- [x] Add unit tests for `keyword_score()`.
- [x] Add unit tests for `signal_boost()`.
- [x] Add integration tests for `/search` and `/refine` contracts.
- [x] Add validation/error tests (empty query, malformed context).
- [x] Run `pytest tests/ -v --tb=short` and fix failures.

## Batch 4 — Scale and Safety Hardening (P2)

- [x] Add DuckDB index on `jobs.row_index` in ingestion setup.
- [x] Parameterize row fetch SQL paths where feasible.
- [x] Re-check keyword fallback query safety and performance guardrails.
- [ ] Validate end-to-end search latency remains acceptable.

## Batch 5 — Token + USD Tracking Medium (Requested)

- [x] Add backend metrics store for token and estimated USD per request.
- [x] Add `GET /metrics/tokens` endpoint with totals and daily breakdown.
- [x] Add pricing config/env variables for transparent cost math.
- [x] Add UI panel in `ui/src/App.jsx` showing:
  - [x] total tokens,
  - [x] total estimated USD,
  - [x] last N request entries.
- [x] Add frontend API client method for token metrics in `ui/src/api.js`.
- [x] Validate metrics update after every `/search` and `/refine` call.

## Batch 6 — Submission Readiness (P1/P2)

- [ ] Replace `tokens-report.md` estimates with measured numbers from real runs.
- [ ] Update README with:
  - [ ] concrete “works well” queries,
  - [ ] concrete “tricky” queries,
  - [ ] time spent,
  - [ ] AI tools used.
- [ ] Re-run `python demo.py` and ensure it still demonstrates 5+ queries including refine.
- [ ] Re-check `.agent/evaluation.md` and mark addressed items.

## Definition of Done (Global)

- [ ] All Batch 1–6 checklist items completed.
- [ ] Demo and tests both pass in current environment.
- [ ] Token + USD tracking is visible via API and UI.
- [ ] Deliverables in `description.md` are complete or explicitly marked optional.
