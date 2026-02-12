# Phase 1 Privacy-by-Design & Costing (Expanded)

## 12) Privacy-by-Design Data Flow
```mermaid
flowchart TD
  USER[User] --> CONSENT[Consent + Purpose Disclosure]
  CONSENT --> MINIMIZE[Data Minimization]
  MINIMIZE --> SEPARATE[Separate Identity vs Profile Stores]

  SEPARATE --> IDSTORE[Identity Store (Encrypted)]
  SEPARATE --> PROFSTORE[Profile Store (Pseudonymized)]

  PROFSTORE --> ANALYTICS[Analytics (Aggregated)]
  IDSTORE --> ACCESS[Restricted Access]

  ACCESS --> AUDIT[Audit Logs]
  ANALYTICS --> REPORTS[Non-PII Reports]

  subgraph Controls
    RETENTION[Retention Policy]
    DSAR[Data Subject Access Request]
    DELETE[Right to Delete]
  end

  AUDIT --> Controls
  REPORTS --> Controls
```

---

## 13) Costing Model (MVP vs Growth - Rough Estimates)
```mermaid
flowchart TD
  COST[Monthly Cost Range] --> MVP[MVP Tier]
  COST --> GROWTH[Growth Tier]

  MVP --> MVP_RANGE[$2k–$7k / month]
  MVP --> MVP_SCOPE[Low traffic, single region, basic ML]

  GROWTH --> GROWTH_RANGE[$15k–$60k / month]
  GROWTH --> GROWTH_SCOPE[High traffic, multi-region, advanced ML + search]

  MVP_SCOPE --> MVP_BREAKDOWN[Compute + DB + Search + Storage + Observability]
  GROWTH_SCOPE --> GROWTH_BREAKDOWN[Compute + DB + Search + Storage + Pipelines + Security]

  MVP_BREAKDOWN --> MVP_COMPUTE[Compute: $800–$2k]
  MVP_BREAKDOWN --> MVP_DB[DB: $300–$800]
  MVP_BREAKDOWN --> MVP_SEARCH[Search: $300–$900]
  MVP_BREAKDOWN --> MVP_STORAGE[Storage: $100–$300]
  MVP_BREAKDOWN --> MVP_OBS[Observability: $200–$800]

  GROWTH_BREAKDOWN --> GROWTH_COMPUTE[Compute: $5k–$20k]
  GROWTH_BREAKDOWN --> GROWTH_DB[DB: $2k–$8k]
  GROWTH_BREAKDOWN --> GROWTH_SEARCH[Search: $3k–$10k]
  GROWTH_BREAKDOWN --> GROWTH_STORAGE[Storage: $1k–$3k]
  GROWTH_BREAKDOWN --> GROWTH_PIPELINES[Pipelines: $1k–$5k]
  GROWTH_BREAKDOWN --> GROWTH_SECURITY[Security: $1k–$5k]
```