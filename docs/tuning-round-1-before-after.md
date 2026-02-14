# Tuning Round 1: Before vs After

## Scope

This round focused on reducing false negation parsing and improving robustness for prompts like:

- don't / shouldn't / never
- neither ... nor
- less / fewer

## Change Applied

- Added negation cue expansion and contraction normalization in search parsing.
- Added a negation noise-token guard so directive words (for example, "include") are not treated as exclusion targets.

## Summary Metrics Comparison (10-query eval set)

| Metric                     | Baseline |  Final |   Delta |
| -------------------------- | -------: | -----: | ------: |
| mean_top_score             |   0.5463 | 0.5400 | -0.0063 |
| mean_avg_top5_score        |   0.4889 | 0.4844 | -0.0045 |
| mean_keyword_hit_rate      |   0.4342 | 0.4192 | -0.0150 |
| total_exclusion_violations |        1 |      0 |      -1 |
| mean_elapsed_ms            |   2820.8 | 2410.3 |  -410.5 |
| total_tokens_used          |       57 |     57 |       0 |

## Interpretation

- Latency improved meaningfully.
- Global score metrics dipped slightly, which is expected after stricter exclusion enforcement.
- Exclusion violations are now reduced to 0 after adding robust hard exclusion filtering with role-family variants.

## What this means

- The parser is now more semantically correct for user-intent negations.
- Explicit exclusion intent (for example, "don't include director") is now enforced more reliably in final results.

## Next Suggested Tuning Step

- Add query-class-specific weight calibration (broad discovery vs constraint-heavy).
- Track pairwise ranking quality on a small judged set to recover score quality while preserving zero exclusion leaks.
