# AI Job Search – Remediation Implementation Plan

## Objective

Close all gaps identified in `.agent/evaluation.md` with a **batch-by-batch rollout** that maximizes relevance quality, runtime efficiency, and low token cost.

## Success Criteria

- Search/refine quality improves for nuanced queries (mission-driven, abbreviation, negation, location intent).
- Required submission artifacts are complete and measurable (tests, tokens report, README additions).
- Token usage and USD cost are trackable in a visible medium (API + UI panel).
- No regressions in existing `/search`, `/refine`, and `demo.py` flow.

## Rollout Strategy (Batches)

### Batch 1 — Reliability and Code Quality Foundation (P0)

**Goal**: Make ranking logic explicit, maintainable, and cheaper per repeated query.

**Scope**

- Replace ranking and boost magic numbers with named constants.
- Add public-function docstrings across backend modules.
- Add in-memory query embedding cache (LRU) to avoid duplicate embedding calls.
- Add basic backend logging setup and structured logs around search/refine timing and token usage.

**Primary files**

- `app/search.py`
- `app/api.py`
- `app/config.py`
- `app/ingest.py`

**Acceptance criteria**

- No inline numeric ranking weights remain in search logic.
- Repeated identical query does not trigger repeated embedding request.
- Search/refine still return the same response schema.

---

### Batch 2 — Relevance and Query Understanding Upgrades (P1)

**Goal**: Improve “results feel right” for ambiguous and real-world phrasing.

**Scope**

- Expand stopwords and normalize common abbreviations (`ml`, `ds`, `swe`, etc.).
- Improve location parsing to reduce false positives from generic “in ...” clauses.
- Add lightweight synonym and intent hints for mission-driven and social-good filtering.
- Add optional negative intent handling (e.g., "not management") in scoring filters.

**Primary files**

- `app/search.py`
- `demo.py` (add edge-case demo queries)

**Acceptance criteria**

- Mission-driven refinement shows visibly improved filtering.
- Abbreviation queries produce relevant titles.
- Negation-style query behavior is deterministic and tested.

---

### Batch 3 — Testing and Regression Safety Net (P1)

**Goal**: Add enough tests to prevent ranking/intent regressions while staying lean.

**Scope**

- Add unit tests for `parse_signals`, `merge_signals`, `keyword_score`, `signal_boost`.
- Add integration tests for `/search`, `/refine`, input validation, and error handling.
- Add a compact end-to-end flow test for search → refine.

**Primary files**

- `tests/test_search.py`
- `tests/test_api.py`
- `tests/test_ingest.py` (small fixture-based validation)
- `requirements.txt` (if test deps needed)

**Acceptance criteria**

- `pytest tests/ -v --tb=short` passes.
- Core ranking and signal behavior is covered with deterministic assertions.

---

### Batch 4 — Scale and Safety Hardening (P2)

**Goal**: Reduce query overhead and tighten data-access safety.

**Scope**

- Add DuckDB index on `row_index`.
- Parameterize SQL row fetch paths where feasible.
- Keep keyword fallback behavior, but tighten query generation and guardrails.

**Primary files**

- `app/ingest.py`
- `app/search.py`

**Acceptance criteria**

- Metadata fetch path avoids avoidable full scans for common retrieval paths.
- Query composition is safer and easier to audit.

---

### Batch 5 — Token + USD Cost Tracking Medium (Requested)

**Goal**: Provide a practical way to track cumulative token usage and dollar cost.

**Scope**

- Add backend cost tracker that logs per-request:
  - timestamp, endpoint, query hash, tokens_used, model, estimated_usd_cost.
- Add aggregate endpoint, e.g. `GET /metrics/tokens` with totals and daily breakdown.
- Add UI panel in existing React app showing:
  - total tokens (session + lifetime file-backed),
  - total estimated USD,
  - last N requests.
- Add env-configurable pricing constants to avoid hardcoding assumptions.

**Primary files**

- `app/metrics.py` (new)
- `app/api.py`
- `ui/src/App.jsx`
- `ui/src/api.js`
- `tokens-report.md` (replace template with measured runs)

**Acceptance criteria**

- UI displays live totals after each search/refine request.
- `tokens-report.md` includes measured numbers from demo runs.
- Estimated cost math is transparent and configurable.

---

### Batch 6 — Submission Readiness and Documentation (P1/P2)

**Goal**: Finish all non-code deliverables to maximize evaluator confidence.

**Scope**

- Update README with:
  - concrete “works well / tricky” query examples,
  - total time spent,
  - AI tools used during development.
- Update `demo.py` output formatting for clarity in reviewer run-through.
- Refresh `.agent/evaluation.md` to reflect closure status.

**Primary files**

- `README.md`
- `demo.py`
- `tokens-report.md`
- `.agent/evaluation.md`

**Acceptance criteria**

- All required deliverables are complete and evidenced.
- Repo is submission-ready with a single-command demo.

## Order of Execution

1. Batch 1
2. Batch 2
3. Batch 3
4. Batch 4
5. Batch 5
6. Batch 6

## Rollback / Risk Controls

- Keep each batch in isolated commits.
- Run tests and demo after every batch.
- If relevance drops, revert only the affected batch and re-tune constants.

## Estimated Effort (Focused)

- Batch 1: 1.5–2.5h
- Batch 2: 1.5–2.5h
- Batch 3: 1.5–2.0h
- Batch 4: 0.5–1.0h
- Batch 5: 1.0–2.0h
- Batch 6: 0.75–1.25h

Total: ~6.75–11.25h, adjustable by depth of test suite and UI polish.
