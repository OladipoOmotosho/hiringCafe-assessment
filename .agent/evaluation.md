# Codebase Evaluation — Current State vs. Assessment Requirements

> Generated: 2026-02-13
> Evaluates the `development` branch against `description.md` deliverables.

---

## Deliverable Status Matrix

| #   | Requirement                    | Status       | Verdict                                                       |
| --- | ------------------------------ | ------------ | ------------------------------------------------------------- |
| 1a  | Working code — Search + Refine | **DONE**     | `POST /search` and `POST /refine` are implemented             |
| 1b  | Runnable demo with 5+ queries  | **DONE**     | `demo.py` runs 2 independent + 3-turn refine = 5 queries      |
| 1c  | Refinement flow in demo        | **DONE**     | 3-turn refine: "data science" → "social good" → "remote"      |
| 2   | README — approach explanation  | **DONE**     | Covers data representation, search, ranking, trade-offs       |
| 3   | Tokens report                  | **PARTIAL**  | File exists but contains estimates, not real measured numbers |
| 4   | Demo video (optional)          | **NOT DONE** | No video present                                              |

---

## Detailed Evaluation by Area

### A. Search Quality — Does it "feel right"?

**Current state**: Hybrid ranking (0.65 vector + 0.25 keyword + signal boosts).

**Strengths**:

- Weighted embedding merge (0.5 explicit, 0.3 inferred, 0.2 company) is sound.
- Over-retrieval (top_k × 10 from FAISS, then re-rank) improves precision.
- Signal boosts for remote/seniority/org-type add structured relevance.

**Gaps and Risks**:

1. **Ranking weights are magic numbers** — `0.65`, `0.25`, `0.15`, `0.1`, `0.05` appear inline in `search.py` without named constants. Hard to tune, easy to break.
2. **Query understanding is shallow** — only detects `remote`, basic seniority tokens, and a few org types. Missing: salary intent, industry terms, abbreviation expansion (`ml`, `ds`, `swe`), negation ("not management").
3. **"Social good" / mission-driven filtering is weak** — relies on keyword match against company/preview text. The description specifically tests this flow.
4. **No query embedding cache** — identical queries re-call OpenAI every time, wasting tokens.
5. **Stopword list is small** — missing common fillers (`find`, `show`, `me`, `some`, `please`, `need`).
6. **Location parsing is naive** — `re.findall(r"in ([a-zA-Z\s,]+)", query)` over-matches (e.g., "interested in data science" → captures "data science" as location).

**Impact**: Results will feel decent for straightforward queries but weak for the nuanced "social good at non-profits" and negation-style queries the evaluators will test.

---

### B. Handling Ambiguity

**Current state**: Heuristic regex/token signal extraction.

**Strengths**:

- Falls back gracefully if OpenAI key is missing (keyword-only DuckDB retrieval).
- Ingestion handles missing fields with resilient fallbacks.
- Refinement correctly merges rather than replaces context.

**Gaps**:

1. **No abbreviation expansion** — "ML engineer" won't match jobs titled "Machine Learning Engineer" via keyword score (vector similarity may help, but keyword score drags it down).
2. **No synonym expansion** — "data science" won't boost "analytics", "statistical modeling", etc. via keyword path.
3. **No negation handling** — "not management" is ignored entirely.
4. **No confidence scoring** — all signals are treated as equally certain regardless of match quality.

---

### C. Handling Scale

**Current state**: Streaming JSONL ingestion → DuckDB + FAISS.

**Strengths**:

- Streaming line-by-line — never loads 8.4GB file into memory. Good.
- FAISS `IndexFlatIP` with normalized vectors = exact cosine search. Correct and simple.
- DuckDB for metadata avoids pulling 100K records into Python dicts.
- Incremental: skips rebuild if artifacts exist.

**Gaps**:

1. **No DuckDB index on `row_index`** — `WHERE row_index IN (...)` does a full scan. Adding an index would speed up metadata fetches.
2. **SQL injection risk in `fetch_rows()`** — builds SQL string via string concatenation of `row_ids`. Since these come from FAISS (integers), it's safe in practice, but parameterized queries are the standard.
3. **`keyword_candidates()` uses LIKE with wildcards** — `LIKE %keyword%` cannot use indexes, so it's a full table scan for each keyword. Acceptable at 100K but won't scale.

---

### D. Code Quality

| Aspect                 | State                                | Issue                                                            |
| ---------------------- | ------------------------------------ | ---------------------------------------------------------------- |
| Type hints             | **Good** — present on most functions | A few `dict` return types could be more specific                 |
| Docstrings             | **MISSING**                          | No docstrings on any function in any module                      |
| Named constants        | **Partial**                          | `DIM = 1536` exists but ranking weights are inline magic numbers |
| Error handling         | **Adequate**                         | API catches `FileNotFoundError`, startup is resilient            |
| Logging                | **MISSING**                          | No `logging` module used anywhere. Only `print` in `demo.py`     |
| Dead code              | **Clean**                            | No dead code found                                               |
| File sizes             | **Good**                             | All files under 350 LOC                                          |
| Separation of concerns | **Good**                             | config / schema / ingest / search / api are cleanly separated    |

---

### E. Tests

**Current state**: **NO TESTS EXIST.** There is no `tests/` directory.

This is a significant gap. While the assessment says "we don't care about test coverage," having zero tests means:

- No way to verify ranking logic works correctly.
- No regression safety net when tuning weights.
- No proof that signal parsing handles edge cases.

**Minimum required**: Unit tests for `parse_signals()`, `merge_signals()`, `keyword_score()`, `signal_boost()`, and one integration test for the search→refine flow.

---

### F. Tokens Report

**Current state**: The file exists but contains only theoretical descriptions and recommendations, not actual measured numbers.

**What evaluators want**: "How many tokens did you use to develop this? How many tokens does the system consume per query?"

**Gaps**:

1. No actual development token count (from Cursor/Copilot/ChatGPT usage).
2. No actual per-query token measurement from test runs.
3. The report reads as a template, not a completed deliverable.

---

### G. README

**Current state**: Covers all required sections.

**Strengths**:

- Setup instructions are clear (PowerShell + bash).
- Architecture explanation is accurate.
- Trade-offs section is honest.

**Gaps**:

1. **"What queries work well?"** section is too brief — needs specific example queries with explanations.
2. **Missing**: How long was spent on the assessment (required in submission).
3. **Missing**: Explicit mention of what 3rd-party AI tools were used during development.

---

### H. Frontend

**Current state**: Functional Vite + React UI with search, refine, suggestions, and results display.

**Assessment note**: "We don't care about fancy UI/UX." The UI is a bonus, not a deliverable. It's well-built but should not consume further engineering time.

---

## Priority Action Items (Ranked by Impact on Evaluation)

| Priority | Action                                                                                   | Why                                              | Effort |
| -------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------ | ------ |
| **P0**   | Add docstrings to all public functions                                                   | Direct eval criteria: "thoughtful approach"      | 30 min |
| **P0**   | Extract magic numbers into named constants                                               | Demonstrates principled engineering              | 15 min |
| **P0**   | Add query embedding cache                                                                | Saves OpenAI tokens (cost constraint)            | 15 min |
| **P0**   | Fill tokens report with real measured numbers                                            | Incomplete deliverable                           | 20 min |
| **P1**   | Add unit tests for search/ranking logic                                                  | Demonstrates rigor, catches bugs                 | 45 min |
| **P1**   | Improve query understanding (abbreviations, expanded stopwords, better location parsing) | Directly improves "results feel right"           | 30 min |
| **P1**   | Add logging module                                                                       | Replace silent failures with observable behavior | 15 min |
| **P1**   | Add more demo queries (edge cases, ambiguous intent)                                     | Shows system breadth                             | 15 min |
| **P2**   | Add DuckDB index on `row_index`                                                          | Scale handling improvement                       | 5 min  |
| **P2**   | Parameterize `fetch_rows()` SQL                                                          | Code quality / safety                            | 10 min |
| **P2**   | Enrich README with specific query examples and time-spent                                | Completeness                                     | 15 min |
| **P3**   | Add `__init__.py` to `app/`                                                              | Package hygiene                                  | 1 min  |

---

## Summary Verdict

The codebase is a **solid prototype** that satisfies the core functional requirements (search + refine + demo). The architecture is clean, the tech choices (FAISS + DuckDB + FastAPI) are appropriate, and the streaming ingestion handles scale correctly.

**Critical gaps** are:

1. **No tests** — zero confidence in correctness under edge cases.
2. **No docstrings** — makes the code look auto-generated without thought.
3. **Magic numbers** in ranking — undermines the "thoughtful approach" signal.
4. **Incomplete tokens report** — a required deliverable with placeholder content.
5. **Shallow query understanding** — will fail on the exact nuanced queries evaluators will test.

Addressing the P0 and P1 items above would meaningfully improve the evaluation outcome.
