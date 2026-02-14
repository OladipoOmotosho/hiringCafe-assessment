---
inclusion: always
---

> These guidelines are MANDATORY for every task performed in this repository.
> Every code change, architectural decision, and implementation choice MUST comply.
> Violation of any rule requires immediate correction before proceeding.

---

## 0. Prime Directive

Every decision — code, architecture, model choice, infrastructure — MUST optimize for:

1. **Correctness** — results must be verifiably accurate and relevant.
2. **Performance** — sub-second search latency at 100K-job scale.
3. **Cost efficiency** — minimize OpenAI API spend (hard cap: $10 total); prefer local/cached computation over API calls.
4. **Simplicity** — the fewest moving parts that satisfy the requirements. No over-engineering.

When trade-offs arise, rank: Correctness > Cost > Performance > Simplicity.

---

## 1. Project Context & Scope

This is a take-home assessment for HiringCafe. The deliverables are:

| #   | Deliverable                                                        | Status Gate                                     |
| --- | ------------------------------------------------------------------ | ----------------------------------------------- |
| 1   | **Search** — NL query → ranked jobs                                | `POST /search` returns relevant, scored results |
| 2   | **Refine** — multi-turn conversational narrowing                   | `POST /refine` merges context across turns      |
| 3   | **Demo** — `python demo.py` runs 5+ queries incl. refinement flow  | Exit code 0, printed output                     |
| 4   | **README** — approach, trade-offs, what works/tricky, improvements | Complete, honest, specific                      |
| 5   | **Tokens report** — dev tokens + per-query runtime tokens          | Measured, not estimated                         |
| 6   | **Demo video** (optional)                                          | Screen recording showing search + refine        |

DO NOT add deliverables that are not listed. DO NOT build infrastructure (Docker, CI/CD, Terraform) unless explicitly asked.

---

## 2. Coding Standards

### 2.1 Python (Backend)

- **Version**: Python 3.10+ (use `from __future__ import annotations` for forward refs).
- **Type hints**: Every function signature MUST have full type annotations (args + return).
- **Docstrings**: Every public function / class MUST have a one-liner Google-style docstring. Complex functions get a full docstring with Args/Returns/Raises.
- **Immutability by default**: Use `frozen=True` dataclasses. Avoid mutable default arguments.
- **No global mutable state** except singletons behind `@lru_cache(maxsize=1)` for expensive resources (DB connections, FAISS index).
- **Error handling**: Catch specific exceptions. Never bare `except:`. Surface user-facing errors as `HTTPException` with a descriptive message.
- **No print statements in library code** — use `logging` with appropriate levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
- **Constants**: ALL_CAPS at module level. No magic numbers/strings inline.
- **Imports**: stdlib → third-party → local, separated by blank lines. Absolute imports only.
- **Line length**: ≤ 120 characters.
- **File size**: ≤ 350 LOC per file. If a module exceeds this, refactor into sub-modules.
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `ALL_CAPS` for constants.

### 2.2 JavaScript/JSX (Frontend)

- **Functional components only**. No class components.
- **Hooks**: Use React hooks correctly (dependencies arrays must be exhaustive).
- **No `any` types** if using TypeScript. In JSX, prefer prop destructuring.
- **Error boundaries**: Wrap async calls in try/catch. Display user-friendly error messages.
- **No console.log in production code**. Use conditional logging.
- **CSS**: Use Tailwind utility classes. No inline `style={}` objects unless dynamic.
- **Component size**: ≤ 150 LOC per component. Extract sub-components otherwise.

### 2.3 General

- **DRY**: Do not repeat logic. Extract shared utilities.
- **YAGNI**: Do not build features that are not required by the assessment.
- **Single Responsibility**: Each function does one thing. Each module owns one concern.
- **No dead code**: Remove unused imports, variables, functions before committing.
- **No commented-out code** in committed files.

---

## 3. ML Engineering & Modeling

### 3.1 Embeddings

- **Model**: `text-embedding-3-small` (1536 dimensions). Do NOT switch models without explicit instruction and cost analysis.
- **Weighted merge** of the three provided vectors:
  - `0.50 × embedding_explicit_vector` (what the job says)
  - `0.30 × embedding_inferred_vector` (what the job implies)
  - `0.20 × embedding_company_vector` (who the company is)
- **Normalization**: L2-normalize merged vectors before indexing AND before querying. FAISS `IndexFlatIP` on normalized vectors = cosine similarity.
- **Zero-vector handling**: If any source embedding is missing/empty, fall back gracefully (do NOT skip the job — use the available embeddings or a zero vector, but flag it).
- **Caching**: Never re-embed identical query strings. Use an in-memory LRU cache for query embeddings.

### 3.2 Indexing

- **FAISS index type**: `IndexFlatIP` for prototype (exact search). If latency is unacceptable at 100K scale, upgrade to `IndexIVFFlat` with `nprobe` tuning — never `IndexFlatL2` (we use cosine via normalized IP).
- **Batch insertion**: Insert vectors in batches (default: 500). Stream from JSONL — never load entire file into RAM.
- **Persistence**: Write `faiss.index` to disk. Skip rebuild if artifacts exist and `REBUILD_INDEX` is not set.

### 3.3 Ranking

The hybrid ranking formula MUST be:

```
final_score = w_vec × vector_similarity + w_kw × keyword_score + signal_boost
```

Where:

- `w_vec ≥ 0.50` (vector similarity is the primary signal)
- `w_kw ≤ 0.30` (keyword overlap is secondary)
- `signal_boost` is additive, capped at `0.30` total
- All weights MUST be named constants, not magic numbers

**Signal boosts** (each is a small additive bump):

- Remote match: `+0.10–0.15`
- Seniority match: `+0.05–0.10`
- Org-type match: `+0.03–0.05`
- Location match: `+0.03–0.05`

If the vector similarity is unavailable (no OpenAI key), fall back to keyword-only retrieval from DuckDB with the same signal-boost logic.

### 3.4 Cost Control

- **One embedding call per user turn** (search or refine). Never batch-embed multiple query variations per turn.
- **No LLM calls** (GPT-4, GPT-3.5) for query parsing — use deterministic heuristics (regex, token matching). LLM intent parsing is a "more time" improvement, not a prototype requirement.
- **Track and report** `tokens_used` in every `SearchResponse`.
- **Hard budget**: Total OpenAI spend for development + demo ≤ $10. Monitor via dashboard.

---

## 4. Search Engine Engineering

### 4.1 Query Understanding

Parse the user query into structured signals using deterministic heuristics:

| Signal    | Detection Method                                                                                            |
| --------- | ----------------------------------------------------------------------------------------------------------- |
| Keywords  | Tokenize, remove stopwords                                                                                  |
| Remote    | Regex: `remote`, `work from home`, `wfh`, `anywhere`                                                        |
| Seniority | Token match: `intern`, `junior`, `mid`, `senior`, `staff`, `principal`, `lead`, `director`, `vp`, `c-level` |
| Org type  | Token/phrase match: `nonprofit`, `non-profit`, `ngo`, `startup`, `enterprise`, `government`, `public`       |
| Location  | Regex: `in <place>`, known US state/city names                                                              |
| Salary    | Regex: `$XXk`, `$XXX,XXX`, salary range patterns                                                            |
| Industry  | Keyword match against known industry terms                                                                  |

- **Extend stopwords** to include common filler: `looking`, `want`, `find`, `show`, `me`, `some`, `please`, `need`.
- **Normalize** query text: lowercase, strip extra whitespace, expand common abbreviations (`ml` → `machine learning`, `ds` → `data science`, `swe` → `software engineer`).

### 4.2 Retrieval Strategy

1. **Vector retrieval**: Query FAISS for `top_k × 10` candidates (over-retrieve, then re-rank).
2. **Keyword fallback**: If no OpenAI key, query DuckDB with SQL LIKE filters.
3. **Re-ranking**: Apply hybrid scoring formula (Section 3.3) to all candidates.
4. **Deduplication**: Deduplicate by job ID before returning.
5. **Result limit**: Return exactly `top_k` results, sorted descending by `final_score`.

### 4.3 Refinement (Conversational Context)

Refinement merges context — it NEVER replaces it:

| Signal    | Merge Strategy                      |
| --------- | ----------------------------------- |
| Keywords  | Union (preserve order, deduplicate) |
| Remote    | Sticky — once true, stays true      |
| Seniority | Latest non-null wins                |
| Org types | Union                               |
| Location  | Union                               |
| History   | Append current query                |

- The full `SearchContext` is returned to the client and passed back on the next turn.
- Context MUST be serializable (Pydantic model → JSON).
- Suggest refinements based on which signals are absent (e.g., if no seniority → suggest "senior roles only").

### 4.4 Latency Targets

| Operation                   | Target  | Hard Limit |
| --------------------------- | ------- | ---------- |
| FAISS search (100K vectors) | < 50ms  | < 200ms    |
| DuckDB metadata fetch       | < 30ms  | < 100ms    |
| OpenAI embedding call       | < 500ms | < 2000ms   |
| Total `/search` response    | < 800ms | < 3000ms   |
| Total `/refine` response    | < 800ms | < 3000ms   |

Measure and report `elapsed_ms` in every response.

---

## 5. Data Handling

### 5.1 Ingestion

- **Stream** JSONL line-by-line. Never `json.load()` the entire file.
- **Resilient parsing**: If a field is missing or malformed, use fallback values ("" for strings, zero vector for embeddings). Log a warning, do NOT skip the job.
- **Title extraction priority**: `job.title` → `v7.title` → `job_information.title` → `""`.
- **Company extraction priority**: `job.company` → `v5_company.name` → `v7.company_name` → `""`.
- **Location extraction priority**: `job.location` → `v7.location` → `job_information.location` → `""`.
- **Preview**: Strip HTML, unescape entities, truncate to `PREVIEW_CHARS` (default 280).

### 5.2 Storage

- **DuckDB**: One table `jobs` with columns: `row_index`, `id`, `title`, `company`, `location`, `apply_url`, `preview`. Indexed on `row_index`.
- **FAISS**: One `IndexFlatIP` with one vector per job, aligned by `row_index`.
- **Data directory**: `data/` (gitignored). Contains `jobs.duckdb` and `faiss.index`.

### 5.3 Schema Validation

- Use **Pydantic v2** models for all API request/response schemas.
- Use `Field(...)` with constraints (`min_length`, `max_length`, `ge`, `le`).
- Never trust client input — validate and sanitize.

---

## 6. Testing Standards

### 6.1 Test Philosophy

Tests MUST exist for critical paths. The assessment says "we don't care about test coverage" — but untested ranking logic is unacceptable.

### 6.2 Required Tests

| Category        | What to Test                                                                     | Type        |
| --------------- | -------------------------------------------------------------------------------- | ----------- |
| Signal parsing  | `parse_signals()` returns correct signals for known queries                      | Unit        |
| Signal merging  | `merge_signals()` correctly unions/overrides                                     | Unit        |
| Keyword scoring | `keyword_score()` returns expected scores                                        | Unit        |
| Signal boost    | `signal_boost()` returns correct boosts per signal                               | Unit        |
| Ranking order   | Given known candidates + scores, verify sort order                               | Unit        |
| API contracts   | `/search` returns 200 with valid schema; `/refine` returns 200 with valid schema | Integration |
| API errors      | Empty query → 400, malformed context → 422                                       | Integration |
| Ingestion       | Stream 10 sample jobs, verify DuckDB row count + FAISS index size                | Integration |
| End-to-end      | Search + refine flow produces non-empty, plausible results                       | E2E         |

### 6.3 Test Framework

- **pytest** with `pytest-asyncio` for async tests if needed.
- **Test files**: `tests/` directory, named `test_<module>.py`.
- **Fixtures**: Use `@pytest.fixture` for DB connections, sample data, test client.
- **No network calls in unit tests** — mock OpenAI client. Integration tests may use real FAISS/DuckDB with small fixture data.
- **Assertions**: Use specific assertions (`assert result.score > 0.5`), not just `assert result`.

### 6.4 Running Tests

```bash
pytest tests/ -v --tb=short
```

Tests MUST pass before any PR or submission.

---

## 7. API Design

### 7.1 Endpoints

| Method | Path      | Request Body    | Response           |
| ------ | --------- | --------------- | ------------------ |
| GET    | `/health` | —               | `{"status": "ok"}` |
| POST   | `/search` | `SearchRequest` | `SearchResponse`   |
| POST   | `/refine` | `RefineRequest` | `SearchResponse`   |

### 7.2 Response Contract

Every `SearchResponse` MUST include:

- `query`: The original query string
- `context`: Full `SearchContext` for the next turn
- `results`: List of `JobResult` objects (scored, sorted)
- `suggestions`: List of `RefinementSuggestion` objects
- `elapsed_ms`: Wall-clock time in milliseconds
- `tokens_used`: OpenAI tokens consumed (0 if no API call)

### 7.3 Error Responses

- **400**: Invalid input (empty query, missing required fields)
- **422**: Pydantic validation failure (automatic from FastAPI)
- **500**: Unexpected server error (logged, not exposed to client)

### 7.4 CORS

- Allow all origins in prototype (`allow_origins=["*"]`).
- In production, restrict to known frontend domains.

---

## 8. Performance & Optimization

### 8.1 Memory

- FAISS index for 100K × 1536 float32 vectors ≈ 600MB. This fits in RAM.
- DuckDB file is lightweight for metadata-only storage.
- Do NOT load `jobs.jsonl` into memory. Stream always.

### 8.2 Startup

- Build index on first startup if artifacts don't exist.
- Skip rebuild on subsequent startups (check `settings.db_path.exists()` and `settings.index_path.exists()`).
- Use `@app.on_event("startup")` (or lifespan) for initialization.

### 8.3 Caching

- `@lru_cache(maxsize=1)` for FAISS index, DuckDB connection, OpenAI client.
- Consider caching query embeddings by query string hash (LRU, maxsize=256).

### 8.4 Concurrency

- FastAPI runs in async event loop. FAISS search and DuckDB queries are CPU-bound — they block the event loop.
- For prototype: acceptable. For production: use `run_in_executor` for FAISS/DuckDB calls.

---

## 9. Repository Hygiene

### 9.1 File Structure

```
├── main.py                 # Uvicorn entrypoint
├── demo.py                 # CLI demo script (5+ queries + refine)
├── requirements.txt        # Pinned Python dependencies
├── README.md               # Approach, trade-offs, setup
├── tokens-report.md        # Token usage report
├── .gitignore              # data/, __pycache__/, .env, node_modules/
├── .agent/                 # Agent guidelines (this file)
│   └── guidelines.md
├── app/
│   ├── __init__.py
│   ├── api.py              # FastAPI routes
│   ├── config.py           # Settings dataclass
│   ├── ingest.py           # JSONL → DuckDB + FAISS
│   ├── schema.py           # Pydantic models
│   └── search.py           # Search + refine logic
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # Shared fixtures
│   ├── test_search.py      # Unit tests for search logic
│   ├── test_ingest.py      # Unit tests for ingestion
│   └── test_api.py         # Integration tests for endpoints
├── data/                   # Gitignored — generated artifacts
│   ├── jobs.duckdb
│   └── faiss.index
├── docs/                   # Design docs
│   └── implementation-plan.md
└── ui/                     # Vite + React frontend
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── api.js
        ├── App.jsx
        ├── index.css
        └── main.jsx
```

### 9.2 Git

- **Commit messages**: imperative tense, ≤ 72 chars first line. E.g. `Add hybrid ranking with signal boosts`
- **No large files** committed (no `jobs.jsonl`, no `faiss.index`, no `jobs.duckdb`).
- **.gitignore** must exclude: `data/`, `__pycache__/`, `.env`, `node_modules/`, `dist/`, `*.pyc`.

### 9.3 Dependencies

- **Pin ranges** in `requirements.txt` (e.g., `fastapi>=0.115,<1`).
- **Minimal dependencies**: Do not add libraries unless they save significant effort.
- **No vendored AI search solutions** (Algolia, Elastic, Weaviate, Pinecone). The search logic must be custom-built.

---

## 10. Evaluation Alignment

The assessment evaluators care about (in their words):

| They Care About               | How We Address It                                                                            |
| ----------------------------- | -------------------------------------------------------------------------------------------- |
| **Do the results feel right** | Hybrid ranking with vector similarity as primary signal; manual testing with diverse queries |
| **Thoughtful approach**       | Clear architecture, documented trade-offs, principled weight choices                         |
| **Handling ambiguity**        | Robust signal parsing, graceful fallbacks, messy-data resilience                             |
| **Handling scale**            | Streaming ingestion, FAISS for vector search, DuckDB for metadata — no full-file RAM loads   |

They DO NOT care about: perfect code style, test coverage, fancy infra, fancy UI.

→ Invest effort in **result quality** and **thoughtful engineering**, not polish.

---

## 11. Decision Log

Every non-trivial technical decision MUST be logged here or in the README. Format:

```
**Decision**: <What was decided>
**Context**: <Why this came up>
**Options considered**: <Alternatives>
**Chosen**: <Which and why>
**Trade-off**: <What we gave up>
```

---

## 12. Checklist Before Submission

- [ ] `python demo.py` runs end-to-end with 5+ queries including 3-turn refine
- [ ] Results are relevant and feel right for each demo query
- [ ] README explains approach, ranking, trade-offs, what works, what's tricky, improvements
- [ ] `tokens-report.md` has real measured numbers (not estimates)
- [ ] No hardcoded API keys in committed code
- [ ] `data/` and `.env` are gitignored
- [ ] All Python files have type hints and docstrings on public functions
- [ ] No dead code, no commented-out code, no print statements in library modules
- [ ] Tests exist for search logic and pass: `pytest tests/ -v`
- [ ] Frontend builds and displays results: `cd ui && yarn dev`
- [ ] Total OpenAI spend ≤ $10

---

## 13. Anti-Patterns — NEVER Do These

1. **Never** load `jobs.jsonl` entirely into memory.
2. **Never** call GPT-4/GPT-3.5/any LLM for query parsing in the prototype.
3. **Never** use a third-party AI search service (Algolia, Weaviate, Pinecone, Elastic).
4. **Never** skip error handling — every external call (OpenAI, disk I/O, DB) must have try/except.
5. **Never** return unsorted results. Always sort by `final_score` descending.
6. **Never** ignore the conversation context in `/refine` — always merge, never replace.
7. **Never** use bare `except:` or `except Exception:` without logging.
8. **Never** commit secrets, API keys, or large data files.
9. **Never** add unnecessary dependencies or infrastructure.
10. **Never** over-engineer — this is a prototype, not a production system.

---

_These guidelines are living. Update them as decisions evolve, but never weaken correctness or cost constraints._
