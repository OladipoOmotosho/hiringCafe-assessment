# Interview Simulation (Hammed) — Answers

Below are plain-language answers to each question. I keep the tone natural and easy to follow, while still being detailed and accurate to what was actually built.

---

## Section 1: Executive Overview

1. **90-second overview**
   I built a job search app that helps people find relevant jobs using plain English, then refine results through follow‑up messages. It is for job seekers who want a smarter search than simple filters. The core value is better relevance: it brings back jobs that match intent, not just keywords.

2. **Most important design principle**
   Keep it simple and explainable. Every part of the ranking can be explained in human terms: “this matched your keywords,” “this is remote,” “this included a word you said to avoid,” etc. That made the system more trustworthy and easier to tune.

3. **User journey end‑to‑end**

- The user types a query in the UI.
- The backend parses the query into signals (keywords, remote, seniority, location, and exclusions).
- It pulls candidate jobs using both vector search (semantic meaning) and keyword search (literal matches).
- It re‑ranks the candidates with a hybrid score and a small second‑pass reranker.
- The user can refine the results with another message, and the system merges that new intent into context.

1. **Definition of relevance**
   Relevance means “how well this job matches the user’s intent for this specific query.” It is not a global or absolute score. We measure it by a mix of semantic similarity, keyword coverage, and explicit intent signals like remote or seniority, plus exclusion penalties.

2. **One‑sentence summary for non‑technical stakeholders**
   “It is a smart job search tool that understands what you mean, not just the words you type, and it gets better when you refine your request.”

---

## Section 2: Architecture Deep Dive

1. **Architecture layers and boundaries**

- **UI layer** (React): collects the query and shows results.
- **API layer** (FastAPI): validates requests and returns results.
- **Retrieval layer** (FAISS + DuckDB): finds candidate jobs quickly.
- **Ranking layer** (Python logic): scores and sorts candidates.
- **Storage layer** (DuckDB + FAISS index files): keeps job metadata and vectors.

1. **Why FAISS + DuckDB**
   FAISS is strong for fast vector similarity search. DuckDB is light, fast, and easy for local analytical queries. Together they are simple and cost‑effective for this size. Postgres + pgvector or Elasticsearch would add more operational overhead, cost, and setup complexity for this take‑home scope.

2. **Why not just vectors or just BM25**
   Only vectors can miss exact keyword intent like “remote” or “nonprofit.” Only BM25 can miss semantic matches where the wording is different. The hybrid approach gives both recall (vector) and precision (keywords + signals).

3. **Index build and persistence**
   The ingest step reads the JSONL data, stores metadata in DuckDB, and builds a FAISS index for vector search. These artifacts are written to disk so startup can reuse them instead of re‑ingesting each time.

4. **Data flow at startup and query time**
   Startup loads the saved index and DB if they exist. At query time, the API parses the query, does vector and keyword retrieval, merges the candidates, and ranks them. The embedding cache saves repeated embedding calls for the same query.

5. **Sync vs async**
   Queries are handled synchronously for clarity and reliability. The workload is small enough that async would add complexity without a clear benefit in this environment.

6. **Deployment boundary**
   Right now it is a single service. Clear future seams are: (1) indexing service, (2) retrieval/ranking service, and (3) feedback analytics service.

---

## Section 3: Query Understanding and Signals

1. **Parser and why deterministic**
   A deterministic parser is fast, cheap, and predictable. It gives consistent behavior and avoids extra LLM cost. It can be tuned with clear rules.

2. **Failure modes and mitigations**
   It can miss unusual phrasing or complex sentences. We mitigate by expanding abbreviations, normalizing text, and using multiple negation patterns. We also allow refinement so the user can clarify intent.

3. **Negation handling**
   We look for cues like “not,” “don’t,” “neither nor,” and “less.” We then add those terms to exclusion rules. There is also a hard exclusion filter to remove results that violate clear negatives.

4. **Location parsing**
   We look for patterns like “in Toronto.” We avoid obvious non‑location phrases like “data science.” Edge cases are ambiguous phrases or multi‑word locations, which are handled by basic heuristics.

5. **Abbreviations**
   Short forms like “ML” and “SWE” are expanded to full forms before parsing. That improves both keyword and vector quality.

6. **Multi‑intent queries**
   The parser collects multiple signals in one pass (keywords, remote, seniority, org type, exclusions). The ranking then applies all those signals together.

7. **Intent across refinements**
   We merge signals across turns: keywords and org types are unioned, remote is sticky, and seniority is updated by the newest turn.

8. **Improvements with more time/budget**
   I would add a learned intent parser (small LLM or classifier) to reduce missed signals and improve edge‑case understanding, while keeping deterministic rules as a safety fallback.

---

## Section 4: Retrieval and Ranking

1. **Retrieval pipeline**
   We retrieve candidates from FAISS (semantic) and DuckDB (keyword). We now also run compact query rewrites and merge those results. Candidates are deduped and merged before ranking.

2. **Hybrid scoring**
   Final score is a mix of vector similarity, keyword coverage, and signal boosts (remote, seniority, org type, location) plus penalties for excluded terms.

3. **Reranker**
   We apply a lightweight reranker to the top set. It rewards exact phrase overlap, title matches, and signal consistency. It is cheap but improves precision in the top results.

4. **Avoiding overfitting to keywords**
   Semantic vectors and the reranker keep results from being too literal. We do not require full keyword overlap for a job to rank well.

5. **No embeddings**
   If the API key is missing, the system falls back to keyword retrieval and ranking using the deterministic signals.

6. **Confidence gating and retry**
   If top scores look flat or weak, we build a focused query and retry retrieval. This improves results for vague or difficult queries.

7. **Repeatability and explainability**
   The scoring is deterministic and transparent. We provide matched signals and score breakdowns so results are explainable.

8. **Remote vs onsite conflict**
   If the user asks for remote, “remote” gets a boost and onsite is penalized through exclusions if the user explicitly says to avoid onsite.

9. **Recall vs precision**
   We widen candidate retrieval (high recall), then re‑rank tightly (precision). Multi‑query retrieval helps recall; signal‑aware scoring improves precision.

10. **Quality metrics**
    We track top score, avg@5 score, keyword hit rate, exclusion violations, latency, and token usage. These reflect relevance, safety, performance, and cost.

---

## Section 5: Cost, Performance, and Budget

1. **Main cost drivers**
   Embedding calls are the main cost. We reduce this with caching, compact query rewrites, and by limiting candidate sizes.

2. **Cost impact of multi‑query**
   It adds a few extra embedding calls per query, but still very cheap with the current model and budget. We cap it at a small number of rewrites.

3. **Cost per query**
   We estimate using tokens used × cost per 1k tokens. Current spend is far below $10 because embeddings are small and caching helps.

4. **Time complexity**
   FAISS retrieval is fast (sub‑linear). Keyword retrieval scales with the database filter. Ranking scales with the candidate count, not the full dataset.

5. **Memory constraints**
   The FAISS index is the main memory load. DuckDB is on disk and read‑only. The app keeps caches small.

6. **Scaling from 100k to 10M**
   The index size and retrieval time are the first pressure points. Storage and RAM become the big issues.

7. **Sharding/partitioning**
   We can partition by geography or category, or use multiple FAISS shards and combine results at query time.

8. **Caching strategies**
   We cache embeddings and reuse the index/DB in memory. Next steps would be result caching and query normalization caching for frequent queries.

---

## Section 6: Robustness, Reliability, and Quality

1. **Biggest sources of ranking error**
   Ambiguous queries and inconsistent job metadata. Some postings lack clear signals.

2. **Noisy or missing metadata**
   We rely on both title and preview text. If fields are missing, we still build candidates from available text.

3. **Duplicate postings**
   Currently we do not dedupe globally. That is a future improvement with fuzzy matching or canonical job IDs.

4. **Monitoring drift**
   We can track feedback trends and quality metrics over time. If scores drop or exclusions rise, we flag drift.

5. **Exclusions**
   We enforce exclusions in ranking and also apply a hard filter that removes violating candidates.

6. **Test boundaries**
   Unit tests cover parsing, exclusions, ranking, and API contracts. They do not cover full end‑to‑end UI flows.

7. **Regression suite**
   A set of fixed queries with expected top results and exclusion checks, run on each change.

8. **Adversarial queries**
   We rely on deterministic parsing and exclusions to keep intent safe. More robust input filtering is a future improvement.

---

## Section 7: Feedback and Learning

1. **Using click feedback safely**
   We log feedback and summarize trends. We only make small weight changes based on consistent patterns, not single events.

2. **Good click signal & position bias**
   A good signal is repeat clicks on top results with consistent intent. We must account for position bias by comparing clicks across ranks, not just absolute counts.

3. **Learning‑to‑rank**
   Yes, but only with offline evaluation first. We would train on logged interactions and test against a fixed validation set.

4. **Minimum data volume**
   We need enough events to avoid noise — usually a few hundred to a few thousand interactions, depending on diversity.

5. **Privacy and security**
   We store hashed query IDs and avoid personal data. Feedback data is limited to job IDs, rank, and score details.

6. **Implicit negative feedback**
   If a result is shown but never clicked across many sessions, it can be treated as a weak negative for tuning.

---

## Section 8: Alternatives and Trade‑offs

1. **Enterprise rebuild**
   I would move to managed vector search or sharded FAISS, plus a more robust data pipeline and monitoring stack.

2. **If one retrieval method must stay**
   I would keep vectors for semantic coverage, but I would keep a very small keyword fallback for edge cases.

3. **Why not large LLM rerank**
   It is expensive, slower, and harder to explain. For this budget, lightweight reranking is more practical.

4. **Failure cases of LLM rerank**
   LLMs can be inconsistent, hallucinate, or miss exact constraints unless carefully prompted.

5. **BM25 + LTR vs dense + rerank**
   BM25 + LTR is strong when exact text matches dominate. Dense + rerank is better when intent is fuzzy. Hybrid gives the best balance.

6. **When to revert to keyword‑only**
   If embeddings are too expensive, too slow, or unavailable, keyword‑only is the safe fallback.

---

## Section 9: Long‑Term Roadmap

1. **Top 3 product improvements (90 days)**

- Personal saved searches and alerts
- More powerful intent filters (skills, level, salary)
- Clearer explainability in the UI

1. **Top 3 infra improvements (6‑12 months)**

- Scalable ingestion pipeline
- Sharded vector index
- Strong monitoring and quality dashboards

1. **Multi‑language support**
   Add language detection and translate queries or run multilingual embeddings.

2. **Personalization without bias**
   Use opt‑in preferences and behavioral signals with fairness checks, and keep a “reset personalization” option.

3. **Explainability in UI**
   Show matched keywords and signals with short tooltips, not full raw scores.

4. **Fresh data ingestion at scale**
   Move to incremental ingestion with change tracking, and update the index in batches or streaming.

---

## Section 10: Closing

1. **Biggest risk and mitigation**
   Risk: wrong matches from ambiguous queries. Mitigation: stronger intent parsing and feedback‑based tuning.

2. **First decision to revisit**
   I would revisit the ranking weights and rerank blend once enough feedback is collected.

3. **Trade‑off to accept**
   Accept a small amount of recall loss to keep results very precise and trustworthy.

4. **Most proud of**
   The hybrid approach with clear, explainable scoring and strong negation handling.

5. **Spend $10 extra**
   Use it on smarter reranking for the top results or a better intent parser.

6. **Final note on process**
   I aimed for clarity, measurable improvements, and predictable behavior. I built simple first, then layered improvements with tests and metrics.
