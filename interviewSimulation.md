# Interview Simulation (Hammed) — Study Edition

Use this like a study guide. Each question is followed by a plain‑language, detailed answer. Read the question, answer it out loud, then compare with the answer section.

---

## Section 1: Executive Overview

1. **Give me your 90-second overview. What did you build, who is it for, and what is the core value it delivers?**

**Answer:** I built a job search app that helps people find relevant jobs using plain English, then refine results through follow‑up messages. It is for job seekers who want a smarter search than simple filters. The core value is better relevance: it brings back jobs that match intent, not just keywords.

1. **What is the single most important design principle that guided your implementation, and why?**

**Answer:** Keep it simple and explainable. Every part of the ranking can be explained in human terms: “this matched your keywords,” “this is remote,” “this included a word you said to avoid,” etc. That made the system more trustworthy and easier to tune.

1. **Walk me through the user journey end-to-end: query, retrieval, ranking, refine. Where does each major component live?**

**Answer:**

- The user types a query in the UI.
- The backend parses the query into signals (keywords, remote, seniority, location, and exclusions).
- It pulls candidate jobs using both vector search (semantic meaning) and keyword search (literal matches).
- It re‑ranks the candidates with a hybrid score and a small second‑pass reranker.
- The user can refine the results with another message, and the system merges that new intent into context.

1. **What is your definition of "relevance" in this system, and how do you ensure you are measuring it?**

**Answer:** Relevance means “how well this job matches the user’s intent for this specific query.” It is not a global or absolute score. We measure it by a mix of semantic similarity, keyword coverage, and explicit intent signals like remote or seniority, plus exclusion penalties.

1. **If I had to explain the system in one sentence to a non-technical stakeholder, what would you say?**

**Answer:** “It is a smart job search tool that understands what you mean, not just the words you type, and it gets better when you refine your request.”

---

## Section 2: Architecture Deep Dive

1. **Describe the architecture layers. What are the responsibilities and data boundaries of each layer?**

**Answer:**

- **UI layer** (React): collects the query and shows results.
- **API layer** (FastAPI): validates requests and returns results.
- **Retrieval layer** (FAISS + DuckDB): finds candidate jobs quickly.
- **Ranking layer** (Python logic): scores and sorts candidates.
- **Storage layer** (DuckDB + FAISS index files): keeps job metadata and vectors.

1. **Why did you pick FAISS + DuckDB? What would be the cost and complexity trade-offs of Postgres + pgvector or Elasticsearch + BM25?**

**Answer:** FAISS is strong for fast vector similarity search. DuckDB is light, fast, and easy for local analytical queries. Together they are simple and cost‑effective for this size. Postgres + pgvector or Elasticsearch would add more operational overhead, cost, and setup complexity for this take‑home scope.

1. **You use vector retrieval plus keyword retrieval plus signals. Why not just vector search? Why not just BM25?**

**Answer:** Only vectors can miss exact keyword intent like “remote” or “nonprofit.” Only BM25 can miss semantic matches where the wording is different. The hybrid approach gives both recall (vector) and precision (keywords + signals).

1. **Explain the index build process and persistence strategy. What artifacts are created and how are they reused?**

**Answer:** The ingest step reads the JSONL data, stores metadata in DuckDB, and builds a FAISS index for vector search. These artifacts are written to disk so startup can reuse them instead of re‑ingesting each time.

1. **Talk me through the exact data flow at startup and at query time. Where do the caches matter?**

**Answer:** Startup loads the saved index and DB if they exist. At query time, the API parses the query, does vector and keyword retrieval, merges the candidates, and ranks them. The embedding cache saves repeated embedding calls for the same query.

1. **What parts are synchronous vs async? Why did you choose that execution model?**

**Answer:** Queries are handled synchronously for clarity and reliability. The workload is small enough that async would add complexity without a clear benefit in this environment.

1. **Describe your deployment boundary. Is it a monolith, or are there clear microservice seams? Where would you draw those seams later?**

**Answer:** Right now it is a single service. Clear future seams are: (1) indexing service, (2) retrieval/ranking service, and (3) feedback analytics service.

---

## Section 3: Query Understanding and Signals

1. **How does your parser extract intent, and why a deterministic parser instead of an LLM-based parser?**

**Answer:** A deterministic parser is fast, cheap, and predictable. It gives consistent behavior and avoids extra LLM cost. It can be tuned with clear rules.

1. **What are the failure modes of deterministic parsing, and how do you mitigate them?**

**Answer:** It can miss unusual phrasing or complex sentences. We mitigate by expanding abbreviations, normalizing text, and using multiple negation patterns. We also allow refinement so the user can clarify intent.

1. **Explain negation handling. How do you avoid false exclusions or missing negations?**

**Answer:** We look for cues like “not,” “don’t,” “neither nor,” and “less.” We then add those terms to exclusion rules. There is also a hard exclusion filter to remove results that violate clear negatives.

1. **How do you treat location parsing, and what are the known edge cases?**

**Answer:** We look for patterns like “in Toronto.” We avoid obvious non‑location phrases like “data science.” Edge cases are ambiguous phrases or multi‑word locations, which are handled by basic heuristics.

1. **How do you handle abbreviations like ML, DS, SWE? Why did you choose that method?**

**Answer:** Short forms like “ML” and “SWE” are expanded to full forms before parsing. That improves both keyword and vector quality.

1. **How do you handle multi-intent queries like “remote senior ML roles at startups, not management”?**

**Answer:** The parser collects multiple signals in one pass (keywords, remote, seniority, org type, exclusions). The ranking then applies all those signals together.

1. **How do you track or evolve intent across refinement turns?**

**Answer:** We merge signals across turns: keywords and org types are unioned, remote is sticky, and seniority is updated by the newest turn.

1. **How would you improve intent extraction if you had a stronger budget or more time?**

**Answer:** I would add a learned intent parser (small LLM or classifier) to reduce missed signals and improve edge‑case understanding, while keeping deterministic rules as a safety fallback.

---

## Section 4: Retrieval and Ranking

1. **Break down your retrieval pipeline. What candidate sets are formed and how are they merged?**

**Answer:** We retrieve candidates from FAISS (semantic) and DuckDB (keyword). We now also run compact query rewrites and merge those results. Candidates are deduped and merged before ranking.

1. **Explain your hybrid scoring formula and how each component contributes to final ordering.**

**Answer:** Final score is a mix of vector similarity, keyword coverage, and signal boosts (remote, seniority, org type, location) plus penalties for excluded terms.

1. **How does your reranker work? Why is it lightweight and how does it help quality?**

**Answer:** We apply a lightweight reranker to the top set. It rewards exact phrase overlap, title matches, and signal consistency. It is cheap but improves precision in the top results.

1. **How do you avoid overfitting to exact keyword matches?**

**Answer:** Semantic vectors and the reranker keep results from being too literal. We do not require full keyword overlap for a job to rank well.

1. **What happens when embeddings are missing or API keys are not set?**

**Answer:** If the API key is missing, the system falls back to keyword retrieval and ranking using the deterministic signals.

1. **What is the role of confidence gating and focused retry? Why is it needed?**

**Answer:** If top scores look flat or weak, we build a focused query and retry retrieval. This improves results for vague or difficult queries.

1. **How do you ensure repeatability and explainability in ranking?**

**Answer:** The scoring is deterministic and transparent. We provide matched signals and score breakdowns so results are explainable.

1. **If two jobs are semantically close but one is on-site and the user asked for remote, how does the model behave?**

**Answer:** If the user asks for remote, “remote” gets a boost and onsite is penalized through exclusions if the user explicitly says to avoid onsite.

1. **Describe how you evaluate the trade-off between recall and precision in candidate retrieval.**

**Answer:** We widen candidate retrieval (high recall), then re‑rank tightly (precision). Multi‑query retrieval helps recall; signal‑aware scoring improves precision.

1. **What metrics do you track for quality, and why those metrics?**

**Answer:** We track top score, avg@5 score, keyword hit rate, exclusion violations, latency, and token usage. These reflect relevance, safety, performance, and cost.

---

## Section 5: Cost, Performance, and Budget

1. **What are the main cost drivers in this system? How did you keep them down?**

**Answer:** Embedding calls are the main cost. We reduce this with caching, compact query rewrites, and by limiting candidate sizes.

1. **You added multi-query retrieval. What is the cost impact and how do you bound it?**

**Answer:** It adds a few extra embedding calls per query, but still very cheap with the current model and budget. We cap it at a small number of rewrites.

1. **How do you estimate cost per query? What is your target and current measured spend?**

**Answer:** We estimate using tokens used times the cost per 1k tokens. Current spend is far below $10 because embeddings are small and caching helps.

1. **What is the time complexity of retrieval and ranking? What scales with N, and what scales with K?**

**Answer:** FAISS retrieval is fast and sub‑linear. Keyword retrieval scales with the database filter. Ranking scales with the candidate count, not the full dataset.

1. **What are the memory constraints for embeddings, indexes, and DuckDB?**

**Answer:** The FAISS index is the main memory load. DuckDB is on disk and read‑only. The app keeps caches small.

1. **If we scale from 100k to 10M jobs, what breaks first and why?**

**Answer:** The index size and retrieval time are the first pressure points. Storage and RAM become the big issues.

1. **How would you shard or partition the index for scale?**

**Answer:** We can partition by geography or category, or use multiple FAISS shards and combine results at query time.

1. **What caching strategies exist in your system today, and what would you add next?**

**Answer:** We cache embeddings and reuse the index/DB in memory. Next steps would be result caching and query normalization caching for frequent queries.

---

## Section 6: Robustness, Reliability, and Quality

1. **What are your system's biggest sources of ranking error today?**

**Answer:** Ambiguous queries and inconsistent job metadata. Some postings lack clear signals.

1. **How do you handle noisy or missing job metadata?**

**Answer:** We rely on both title and preview text. If fields are missing, we still build candidates from available text.

1. **How do you handle duplicate postings or repeated entries across different sources?**

**Answer:** Currently we do not dedupe globally. That is a future improvement with fuzzy matching or canonical job IDs.

1. **What is your approach to monitoring drift in ranking quality over time?**

**Answer:** We track feedback trends and quality metrics over time. If scores drop or exclusions rise, we flag drift.

1. **How do you validate that exclusions are always respected?**

**Answer:** We enforce exclusions in ranking and also apply a hard filter that removes violating candidates.

1. **What are your test boundaries? What do unit tests cover vs what do they not cover?**

**Answer:** Unit tests cover parsing, exclusions, ranking, and API contracts. They do not cover full end‑to‑end UI flows.

1. **If you had to add a regression suite, what would it look like?**

**Answer:** A set of fixed queries with expected top results and exclusion checks, run on each change.

1. **How do you handle adversarial queries or spammy content?**

**Answer:** We rely on deterministic parsing and exclusions to keep intent safe. More robust input filtering is a future improvement.

---

## Section 7: Feedback and Learning

1. **You now capture click feedback. How will you use it to tune relevance without overfitting?**

**Answer:** We log feedback and summarize trends. We only make small weight changes based on consistent patterns, not single events.

1. **How do you define a "good" click signal? What about position bias?**

**Answer:** A good signal is repeat clicks on top results with consistent intent. We account for position bias by comparing clicks across ranks, not just absolute counts.

1. **Would you apply learning-to-rank? If so, how would you design a safe offline evaluation?**

**Answer:** Yes, but only with offline evaluation first. We would train on logged interactions and test against a fixed validation set.

1. **What minimal data volume would you need before you trust feedback-driven tuning?**

**Answer:** We need enough events to avoid noise, usually a few hundred to a few thousand interactions, depending on diversity.

1. **How do you protect privacy and security with feedback data?**

**Answer:** We store hashed query IDs and avoid personal data. Feedback data is limited to job IDs, rank, and score details.

1. **How would you incorporate implicit negative feedback (no clicks)?**

**Answer:** If a result is shown but never clicked across many sessions, it can be treated as a weak negative for tuning.

---

## Section 8: Alternatives and Trade-offs

1. **If you had to rebuild this for enterprise scale, what would you replace and why?**

**Answer:** I would move to managed vector search or sharded FAISS, plus a more robust data pipeline and monitoring stack.

1. **If you had to keep only one of vector or keyword retrieval, which would you keep and why?**

**Answer:** I would keep vectors for semantic coverage, but I would keep a very small keyword fallback for edge cases.

1. **Why not use a large LLM to rank the top-50 results? What would be the trade-offs?**

**Answer:** It is expensive, slower, and harder to explain. For this budget, lightweight reranking is more practical.

1. **What are the failure cases of pure LLM reranking in this domain?**

**Answer:** LLMs can be inconsistent, hallucinate, or miss exact constraints unless carefully prompted.

1. **How would you compare BM25 + LTR vs dense retrieval + rerank for this use case?**

**Answer:** BM25 + LTR is strong when exact text matches dominate. Dense + rerank is better when intent is fuzzy. Hybrid gives the best balance.

1. **Under what conditions would you stop using embeddings and revert to keyword-only?**

**Answer:** If embeddings are too expensive, too slow, or unavailable, keyword‑only is the safe fallback.

---

## Section 9: Long-Term Roadmap

1. **What are the top three product improvements you would ship in the next 90 days?**

**Answer:**

- Personal saved searches and alerts
- More powerful intent filters (skills, level, salary)
- Clearer explainability in the UI

1. **What are the top three infrastructure improvements for the next 6-12 months?**

**Answer:**

- Scalable ingestion pipeline
- Sharded vector index
- Strong monitoring and quality dashboards

1. **How would you add multi-language support?**

**Answer:** Add language detection and translate queries or run multilingual embeddings.

1. **How would you add user personalization without increasing bias?**

**Answer:** Use opt‑in preferences and behavioral signals with fairness checks, and keep a “reset personalization” option.

1. **How would you build explainability into the UI without overwhelming users?**

**Answer:** Show matched keywords and signals with short tooltips, not full raw scores.

1. **How would you handle fresh data ingestion at scale (hourly or continuous)?**

**Answer:** Move to incremental ingestion with change tracking, and update the index in batches or streaming.

---

## Section 10: Closing

1. **What is the biggest risk you see in this system, and how would you mitigate it?**

**Answer:** Risk: wrong matches from ambiguous queries. Mitigation: stronger intent parsing and feedback‑based tuning.

1. **If we onboarded you tomorrow, what is the first technical decision you would push to revisit?**

**Answer:** I would revisit the ranking weights and rerank blend once enough feedback is collected.

1. **What trade-off do you think we should explicitly accept, and why?**

**Answer:** Accept a small amount of recall loss to keep results very precise and trustworthy.

1. **Is there any part of the system you are most proud of, and why?**

**Answer:** The hybrid approach with clear, explainable scoring and strong negation handling.

1. **If I gave you $10 more in budget, where would you spend it first?**

**Answer:** Use it on smarter reranking for the top results or a better intent parser.

1. **Any final notes you want to leave us with about your engineering process?**

**Answer:** I aimed for clarity, measurable improvements, and predictable behavior. I built simple first, then layered improvements with tests and metrics.
