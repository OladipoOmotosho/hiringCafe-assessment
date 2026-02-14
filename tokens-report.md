# Tokens Report

## Scope Note

This project uses embeddings only for search relevance and ranking quality.

## Development Token Usage

- Development prompt/completion tokens were not instrumented in-repo.
- The product runtime token usage below is fully measured by the app.

## Runtime Token Usage (Measured)

Source: `python -m app.eval` output (`data/eval-report.json`).

- Evaluated queries: 10
- Total runtime tokens used: 57
- Mean runtime tokens/query: 5.7

Per-query examples from the latest run:

- "data science jobs" → 3 tokens
- "senior remote machine learning engineer" → 6 tokens
- "neither executive nor vp data roles" → 11 tokens

## How Runtime Tokens Are Counted

- If `OPENAI_API_KEY` is configured:
  - The engine uses embedding calls (`text-embedding-3-small`) for semantic retrieval.
  - `tokens_used` in API responses is provider-reported usage for those embedding calls.
- If `OPENAI_API_KEY` is not configured:
  - No external token-based model call is made.
  - `tokens_used = 0`.

## Budget Check (<= $10 requirement)

- Pricing configured in app: `$0.00002` per 1K tokens.
- Latest eval run estimated cost: `57 / 1000 * 0.00002 = $0.00000114`.
- This is far below the `$10` cap.

## Ongoing Tracking

- Token and estimated USD cost are persisted and exposed via `GET /metrics/tokens`.
- This supports per-endpoint monitoring for `/search` and `/refine`.
