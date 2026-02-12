# Tokens Report

## Development Token Usage

This implementation was developed as deterministic code changes in the repository.
No runtime LLM generation is required by the application logic itself.

- Estimated development prompt/completion token usage: not instrumented in-repo
- Practical engineering assumption for this submission: no product-runtime dependency on development tokens

## Runtime Token Usage Per Query

The backend reports `tokens_used` in each `SearchResponse`.

### Current behavior

- If `OPENAI_API_KEY` is configured:
  - One embeddings request is made per user query/refinement (`text-embedding-3-small`).
  - `tokens_used` reflects provider-reported usage for that embedding call.
- If `OPENAI_API_KEY` is not configured:
  - No external token-based model call is made.
  - `tokens_used = 0`.

## Typical Consumption Pattern

Given query text length `L`:

- Approximate token usage is proportional to `L` for embedding input.
- Total query token cost is roughly one embedding call per turn.

Refinement conversations consume tokens per turn in the same way:

- Turn 1 search: 1 embedding call
- Turn 2 refine: 1 embedding call
- Turn 3 refine: 1 embedding call

Total for a 3-turn refine flow: 3 embedding calls.

## Recommendation for Production Tracking

- Persist `tokens_used` per request in analytics logs.
- Aggregate by endpoint (`/search` vs `/refine`) and by day.
- Track p50/p95 tokens per query and cost-per-successful-session.
