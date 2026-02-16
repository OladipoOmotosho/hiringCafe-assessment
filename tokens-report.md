# Tokens Report

## Scope Note

This project uses embeddings only for search relevance and ranking quality.

## Development Token Usage

- AI tools used during development: GitHub Copilot, ChatGPT.
- Estimated development token usage: ~150K–200K tokens (prompt + completion) across all sessions.
- Estimated development cost: ~$0.30–$0.60 (well under budget).

## Runtime Token Usage (Measured)

Source: `data/token-metrics.jsonl` — every `/search` and `/refine` call is logged automatically.

### Aggregate totals (all sessions through 2026-02-16)

| Metric | Value |
|---|---|
| Total API calls logged | 118 |
| `/search` calls | 65 (722 tokens) |
| `/refine` calls | 53 (901 tokens) |
| **Total runtime tokens** | **1,623** |
| **Total estimated cost** | **$0.000032** |
| Mean tokens/call (non-zero) | 20.8 |
| Mean tokens/call (all) | 13.8 |
| Min / Max tokens per call | 2 / 41 |

### Per-query examples

- "data science jobs" → 3–5 tokens
- "senior remote machine learning engineer" → 6 tokens
- "remote senior ml roles at mission-driven companies" → 35 tokens
- "neither executive nor vp data roles" → 11 tokens
- "make it remote" (refine) → 25 tokens

### Notes

- Calls showing `tokens_used = 0` used the cached embedding or keyword-only fallback (no API call made).
- 78 of 118 calls consumed tokens; 40 were served from cache or keyword-only retrieval.

## How Runtime Tokens Are Counted

- If `OPENAI_API_KEY` is configured:
  - The engine uses embedding calls (`text-embedding-3-small`) for semantic retrieval.
  - `tokens_used` in API responses is provider-reported usage for those embedding calls.
- If `OPENAI_API_KEY` is not configured:
  - No external token-based model call is made.
  - `tokens_used = 0`.

## Budget Check (<= $10 requirement)

- Pricing configured in app: `$0.00002` per 1K tokens.
- Total runtime cost: `1,623 / 1,000 × $0.00002 = $0.000032`.
- This is far below the `$10` cap.

## Ongoing Tracking

- Token and estimated USD cost are persisted per call in `data/token-metrics.jsonl`.
- Aggregated metrics are exposed via `GET /metrics/tokens`.
- This supports per-endpoint monitoring for `/search` and `/refine`.
