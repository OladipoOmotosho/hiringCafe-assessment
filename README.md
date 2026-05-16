# Semantic Job Search Engine with RAG and Conversational Refinement

> A natural-language job search system built from scratch with FastAPI, FAISS, OpenAI embeddings, and a React frontend. Implements hybrid retrieval, intent-aware ranking, and multi-turn conversational refinement over a large jobs dataset.

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat&logo=openai&logoColor=white)
![FAISS](https://img.shields.io/badge/FAISS-0467DF?style=flat&logo=meta&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-FFF000?style=flat&logo=duckdb&logoColor=black)
![React](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat&logo=vite&logoColor=white)

---

## Overview

This project demonstrates how to build a production-style Retrieval-Augmented Generation (RAG) system for natural-language job search without depending on heavyweight agent frameworks. It indexes a large `jobs.jsonl` dataset into a FAISS vector store backed by DuckDB metadata, then serves two capabilities over it:

1. **Search** — natural-language query to ranked, intent-aware job results
2. **Refine** — multi-turn conversational narrowing that preserves state across turns

The system uses hybrid retrieval (vector + keyword), explainable signal-based reranking, deterministic intent parsing, and a small evaluation harness for repeatable benchmarking.

---

## Key Features

- **Hybrid retrieval pipeline** combining FAISS vector similarity, multi-query rewrites for recall, and DuckDB keyword matching
- **Intent-aware ranking** that parses keywords, remote intent, seniority, org-type preferences, location hints, and negations from raw queries
- **Hard exclusions** for negation intent (e.g., "machine learning engineer but not management" filters out manager/director/executive titles)
- **Conversational Refine** with stateful merging: keyword union, sticky remote intent, recency-based seniority, union-based org-type filtering
- **Abbreviation expansion** ("ml engineer" → "machine learning", "ai engineer" → "artificial intelligence")
- **Explainable scoring** — every result returns `vector_score`, `keyword_score`, `signal_adjustment`, and `rerank_adjustment` so ranking is fully auditable
- **Evaluation harness** measuring top-score, average@5, keyword hit rate, exclusion violations, latency, and token cost
- **Feedback tuning loop** that ingests click events and suggests ranking weight adjustments
- **Streaming ingestion** — processes large datasets without loading the full file into memory

---

## Architecture

```
                ┌─────────────────────────────────────────────┐
                │              React + Vite UI                │
                └─────────────────┬───────────────────────────┘
                                  │ /search, /refine
                                  ▼
                ┌─────────────────────────────────────────────┐
                │          FastAPI Application Layer          │
                │  ┌────────────────────────────────────────┐ │
                │  │  Signal Parser (keywords, seniority,   │ │
                │  │  remote, org-type, location, negation) │ │
                │  └────────────────────────────────────────┘ │
                │  ┌────────────────────────────────────────┐ │
                │  │  Hybrid Retrieval (FAISS + DuckDB)     │ │
                │  └────────────────────────────────────────┘ │
                │  ┌────────────────────────────────────────┐ │
                │  │  Multi-stage Ranker + Reranker         │ │
                │  └────────────────────────────────────────┘ │
                │  ┌────────────────────────────────────────┐ │
                │  │  Refine State Manager                  │ │
                │  └────────────────────────────────────────┘ │
                └─────────────────┬───────────────────────────┘
                                  │
                  ┌───────────────┼─────────────────┐
                  ▼               ▼                 ▼
        ┌─────────────────┐  ┌──────────┐  ┌──────────────┐
        │ FAISS Index     │  │ DuckDB   │  │ OpenAI       │
        │ (weighted       │  │ (metadata│  │ Embeddings   │
        │  embeddings)    │  │  store)  │  │ (queries)    │
        └─────────────────┘  └──────────┘  └──────────────┘
```

### Data Representation

- Jobs are streamed from `jobs.jsonl` (no full-file load into RAM)
- Metadata stored in DuckDB (`data/jobs.duckdb`) with one row per indexed job
- Weighted embeddings built from three vectors in `v7_processed_job_data`:
  - `0.5 * embedding_explicit_vector`
  - `0.3 * embedding_inferred_vector`
  - `0.2 * embedding_company_vector`
- Weighted vectors normalized and stored in FAISS (`data/faiss.index`)

---

## How Search & Ranking Works

1. **Parse query signals** — keywords, remote intent, org type, seniority, location hints, negations
2. **Build blended candidate set:**
   - Vector retrieval from FAISS (when embeddings are enabled)
   - Multi-query rewrites for better recall (original + compact intent-focused rewrites)
   - Keyword retrieval from DuckDB
   - Deduplicate and merge
3. **Re-rank with hybrid score:**
   - Vector similarity
   - Keyword overlap
   - Signal boosts (remote, seniority, org-type, mission, location)
   - Hard exclusions for explicit negation intent
4. **Lightweight second-pass reranker** on top candidates:
   - Phrase-level query matching
   - Title keyword coverage
   - Matched-signal bonus
5. **Fallback retry** with a focused query if top results are low-signal
6. **Return** ranked results, matched signals, score breakdown, and refinement suggestions

If OpenAI is not configured, the system falls back to pure DuckDB keyword retrieval.

---

## How Refine Works

Refine merges conversational context instead of replacing it:

| Field | Merge strategy |
| --- | --- |
| `keywords` | Union of prior + current |
| `remote` | Sticky once requested |
| `seniority` | Most recent non-empty value wins |
| `org_types` | Union of prior + current |
| `location_terms` | Union of prior + current |

Example flow:

```
Turn 1: "data science jobs"
Turn 2: "at non-profits that care about social good"
Turn 3: "make it remote"
```

Each turn narrows results while preserving prior intent.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | FastAPI (async Python) |
| Vector store | FAISS |
| Metadata store | DuckDB |
| Embeddings | OpenAI `text-embedding-3-small` |
| Frontend | React + Vite + TypeScript |

---

## Getting Started

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Set environment variables

```bash
export JOBS_JSONL_PATH="/path/to/jobs.jsonl"
export OPENAI_API_KEY="your_key_here"   # optional but recommended
```

PowerShell:

```powershell
$env:JOBS_JSONL_PATH="C:\path\to\jobs.jsonl"
$env:OPENAI_API_KEY="your_key_here"
```

Optional configuration:

| Variable | Default |
| --- | --- |
| `DATA_DIR` | `data` |
| `DB_PATH` | `data/jobs.duckdb` |
| `INDEX_PATH` | `data/faiss.index` |
| `FEEDBACK_EVENTS_PATH` | `data/feedback-events.jsonl` |
| `BATCH_SIZE` | `500` |
| `PREVIEW_CHARS` | `280` |
| `REBUILD_INDEX` | unset (set `1` to force rebuild) |

API startup (`python main.py`) reuses existing artifacts when present.

---

## Running the System

### Single-command demo

```bash
python demo.py
```

This will:

1. Start the FastAPI backend (or reuse a running instance)
2. Run 4 independent search queries and a 3-turn refine conversation
3. Print ranked results, matched signals, and refinement suggestions
4. Launch the frontend UI if `ui/node_modules` is present
5. Keep both services alive for interactive exploration

Open [http://localhost:5173](http://localhost:5173) to use the UI. Press `Ctrl+C` to stop.

### Backend only

```bash
python main.py
```

Endpoints:

- `GET /health`
- `POST /search`
- `POST /refine`
- `POST /feedback`
- `GET /feedback`

### Frontend only

```bash
cd ui
yarn
yarn dev
```

The UI proxies to the backend at `http://127.0.0.1:8000`.

---

## Evaluation Harness

```bash
python -m app.eval
```

Runs a seed set of 10 representative queries and computes:

- Top score, average@5
- Keyword hit rate
- Exclusion violation count
- Latency
- Token cost

Writes a JSON report to `data/eval-report.json` for repeatable benchmarking.

---

## Feedback Tuning

```bash
python -m app.feedback_tuning
```

Summarizes click feedback from `data/feedback-events.jsonl`, reports average rank/score and component averages, and suggests weight adjustments for relevance tuning.

---

## What Works Well

- **Broad role retrieval** — `"remote software engineer"` returns relevant results fast (e.g., *Staff Software Engineer, Ads – Quora (Remote)* at 0.86, with `remote` signal correctly detected)
- **Iterative refinement** — starting with `"software engineer"`, refining to `"remote only"`, then `"senior level, not management"` progressively narrows the result set with exclusions respected
- **Seniority + role queries** — `"senior product manager"` returns 0.95+ score results with `seniority=senior` correctly extracted
- **Negation handling** — `"machine learning engineer but not management"` excludes management titles and deprioritizes managerial content
- **Vertical precision** — `"community health worker"` returns 0.87+ score matches from orgs like Advance Community Health, St. Joseph's Health
- **Explainable scoring** — every result includes the four score components so ranking can be audited end-to-end

---

## Trade-offs and Limitations

- Query embeddings require an OpenAI API key for best semantic quality
- Signal extraction is heuristic (regex/token based), not full LLM intent parsing
- Mission/social-good filtering uses keyword + known-org pattern matching since the dataset lacks structured industry tags
- Location metadata is sparse in many records, so `"data scientist in New York"` parses the location signal but cannot filter on it when the field is empty
- Multi-turn state is stateless on the server side; the client must persist and forward `context` between calls
- Confidence heuristic is intentionally conservative and can read as `null` for well-distributed result sets

---

## What I'd Build Next

- **Structured mission/industry tags at ingest** — extract `organization_type` and `industry` from `v5_processed_company_data` into DuckDB columns for real faceted filtering
- **Learned ranker (LTR)** — train a lightweight re-ranker on offline relevance judgments instead of hand-tuned signal weights
- **LLM-powered intent parsing** — replace regex/heuristic signal extraction with a small LLM call to classify intent slots (role, seniority, exclusions, mission preference) for edge cases
- **Location normalization** — geocode raw location strings during ingest to enable proximity-based filtering
- **Stronger quality filters** — detect and deprioritize stale, duplicate, or low-information postings at ingest time

---

## About This Project

This was built as a take-home engineering assessment over approximately 12-15 hours across multiple sessions. The goal was to demonstrate an end-to-end intent-aware search system without leaning on heavyweight agent frameworks, prioritizing explainability, evaluation, and a clean separation between retrieval, ranking, and refinement.

AI tools used during development: GitHub Copilot, ChatGPT.

---

## Project Structure

```
.
├── app/
│   ├── ingest.py          # Streaming ingestion and indexing
│   ├── search.py          # Hybrid retrieval and ranking
│   ├── refine.py          # Conversational state management
│   ├── signals.py         # Intent parsing
│   ├── eval.py            # Evaluation harness
│   └── feedback_tuning.py # Feedback loop
├── data/
│   ├── jobs.duckdb        # Metadata store
│   ├── faiss.index        # Vector index
│   └── feedback-events.jsonl
├── tests/
│   ├── test_api.py
│   └── test_search.py
├── ui/                    # React + Vite frontend
├── demo.py                # Single-command demo runner
├── main.py                # API entry point
├── requirements.txt
├── tokens-report.md       # Runtime token/cost accounting
└── README.md
```

---

## Author

**Ishaq Omotosho**
M.Eng. Information Systems Security candidate at Concordia University, Montreal.

- 🔗 [LinkedIn](https://www.linkedin.com/in/ishaq-omotosho)
- 🌐 [Portfolio](https://tosholadipo.netlify.app/)
- 📧 is.haqomotosho@gmail.com
