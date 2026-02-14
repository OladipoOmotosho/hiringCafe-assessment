# Search Engine Learning Note

This note explains how your job search engine works using:

1. Feynman Technique (simple explanation)
2. Cornell Note-Taking (study format)
3. Zettelkasten (linked idea notes)

---

## 1) Feynman Technique (Explain Like I’m New)

## Big picture

Imagine a recruiter assistant with 3 skills:

- It understands meaning (semantic/vector similarity).
- It checks exact words (keyword matching).
- It listens to preferences (remote, seniority, mission-driven, location, and exclusions).

When you ask for jobs, the engine gives each job a final relevance score and sorts highest to lowest.

## Step-by-step in plain language

1. Read your query and normalize it

- Expands abbreviations like "ml" -> "machine learning".
- Extracts signals such as:
  - remote intent
  - seniority (junior/senior/etc.)
  - org type (startup/nonprofit/mission-driven)
  - location hints
  - negations like "not management"

1. Build candidates (possible jobs)

- If OpenAI embedding is available:
  - Query is embedded.
  - FAISS returns top semantic neighbors.
- If embedding is not available:
  - DuckDB keyword filtering returns candidates.

1. Score each candidate

- Final score formula:

  score = 0.65 \_vector_score + 0.25 \_keyword_score + signal_boost

- vector_score: semantic closeness from FAISS
- keyword_score: how many query keywords appear in title/preview
- signal_boost: bonuses/penalties from intent signals

1. Sort and return top K

- Jobs are sorted descending by score.
- Top results are returned with matched signals and suggestions for next refinement.

## Important constants currently used

- VECTOR_WEIGHT = 0.65
- KEYWORD_WEIGHT = 0.25
- MAX_SIGNAL_BOOST = 0.30
- REMOTE_BOOST = 0.15
- SENIORITY_BOOST = 0.10
- ORG_TYPE_BOOST = 0.05
- LOCATION_BOOST = 0.05
- MISSION_BOOST = 0.05
- NEGATION_PENALTY = 0.20 per excluded-term match

The score is a ranking value used to order results.

## One concrete example

Query: "senior remote data science jobs not management"

- Semantic channel finds jobs similar in meaning to data science + senior + remote intent.
- Keyword channel rewards explicit term matches.
- Signal channel adds bonuses for "remote" and "senior" matches.
- Signal channel subtracts penalty if job text contains excluded terms like "management".

A job with strong semantic match and remote/senior signals can rank high even if wording differs.

---

## 2) Cornell Note-Taking Version

## Topic

Hybrid Job Search Ranking (Vector + Keyword + Intent Signals)

## Cue column (questions) | Notes column (answers)

### Q1: What is the engine trying to optimize?

A: Relevance of returned job listings to user intent, not just exact text matching.

### Q2: What are the three ranking ingredients?

A:

- Vector similarity (semantic meaning)
- Keyword coverage (literal overlap)
- Signal boosts/penalties (intent alignment)

### Q3: How is intent extracted?

A: Deterministic parser identifies keywords, excluded keywords, remote, seniority, org types, location terms, and mission-driven intent.

### Q4: What happens when OpenAI key is missing?

A: No embedding vector is used; engine falls back to keyword-based candidate retrieval and scoring relies on keyword + signal terms.

### Q5: How does refinement work across turns?

A: New signals are merged into prior context:

- keywords/org types/location terms are unioned
- remote is sticky once true
- latest explicit seniority overrides previous
- excluded keywords are accumulated

### Q6: Why can a result with different wording still rank high?

A: Because vector similarity captures semantic closeness beyond literal wording.

### Q7: Why can a result with many keywords rank lower?

A: It may have weak semantic alignment, miss key signals, or trigger exclusion penalties.

### Q8: What does the displayed score mean?

A: A relative ranking score (rounded to 4 decimals) used for result ordering.

## Cornell Summary (bottom summary)

The search engine is a hybrid ranker: semantic retrieval finds meaning-level matches, keyword scoring keeps lexical precision, and signal boosts encode user intent preferences. Conversation refinements persist and update intent over turns, producing more personalized and stable ranking behavior.

---

## 3) Zettelkasten (Atomic Notes + Links)

Use these as small linked notes. Each note should stand alone and reference related notes.

## ZK-001: Hybrid relevance is stronger than single-mode retrieval

A ranking system combining semantic, lexical, and intent signals is more robust to noisy job text than any single channel.
Links: ZK-002, ZK-003, ZK-004

## ZK-002: Vector similarity handles vocabulary mismatch

Semantic vectors let "ML engineer" and "applied scientist" relate even when words differ.
Links: ZK-001, ZK-006

## ZK-003: Keyword coverage preserves precision

Literal overlap protects against semantically broad but textually irrelevant results.
Links: ZK-001, ZK-007

## ZK-004: Intent boosts personalize ranking

Remote/seniority/org/location/mission signals align ranking with user constraints and preferences.
Links: ZK-001, ZK-005

## ZK-005: Negation penalties prevent opposite matches

Explicit exclusions (for example, "not management") should actively demote contradictory results.
Links: ZK-004, ZK-008

## ZK-006: Candidate generation and scoring are separate concerns

First retrieve candidates efficiently, then re-rank with richer logic; this scales better and stays explainable.
Links: ZK-002, ZK-003

## ZK-007: Robust fallback paths increase reliability

When embeddings are unavailable, keyword retrieval keeps system functional, though with less semantic depth.
Links: ZK-003, ZK-009

## ZK-008: Conversational refinement is signal state management

Refinement quality depends on how state is merged across turns (sticky, override, and union rules).
Links: ZK-004, ZK-010

## ZK-009: Score interpretation must be relative

The score is for sorting within a query session, not a global calibration across all queries.
Links: ZK-001, ZK-007

## ZK-010: Explainability improves trust

Showing matched signals and component contributions helps users understand why a result ranked where it did.
Links: ZK-008, ZK-009

---

## Connecting All Three Techniques Together

- Feynman gives the intuitive mental model: "three judges" (semantic, keyword, intent).
- Cornell turns that model into exam-ready Q/A and recall prompts.
- Zettelkasten turns knowledge into reusable building blocks you can extend, remix, and connect over time.

Practical workflow:

1. Read the Feynman section first.
2. Quiz yourself with Cornell cues.
3. Add or edit ZK notes as you learn from new experiments.

---

## Optional self-check questions

1. Why does the engine still work when embeddings are unavailable?
2. What trade-off is created by increasing VECTOR_WEIGHT?
3. Why is NEGATION_PENALTY important for user trust?
4. Why is the displayed score relative to a query session?
5. How does refinement preserve context while accepting new intent?

If you can answer those from memory, you understand the system deeply.
