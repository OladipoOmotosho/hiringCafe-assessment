# Employment Operating System — Phase 1 Architecture Diagrams

## 1) High-Level System Architecture (OS Model)
```mermaid
flowchart LR
  subgraph Users
    U1[Newcomer (B2C)]
    U2[Agency Advisor (B2B)]
    U3[Employer (B2B)]
  end

  subgraph Frontend
    FE[Web App (Next.js)]
    B2C[B2C Experience]
    B2B[B2B Dashboards]
  end

  subgraph Core Services
    AUTH[Auth Service]
    CORE[Core API]
    PATH[Credential Pathway Service]
    ELIG[Eligibility Graph Service]
    TRUST[Employer Verification Service]
    OUTCOME[Outcome Analytics Service]
  end

  subgraph ML & Intelligence
    NLP[Resume Parsing + Skill Extraction]
    MATCH[Hybrid Matching Engine]
    SCAM[Scam/Fraud Detection]
  end

  subgraph Data Layer
    DB[(PostgreSQL)]
    CACHE[(Redis)]
    SEARCH[(OpenSearch)]
    OBJECT[(Object Storage)]
  end

  U1 --> FE
  U2 --> FE
  U3 --> FE
  FE --> B2C
  FE --> B2B

  B2C --> CORE
  B2B --> CORE
  CORE --> AUTH
  CORE --> PATH
  CORE --> ELIG
  CORE --> TRUST
  CORE --> OUTCOME

  PATH --> DB
  ELIG --> DB
  TRUST --> DB
  OUTCOME --> DB

  NLP --> DB
  MATCH --> SEARCH
  SCAM --> SEARCH

  CORE --> CACHE
  CORE --> SEARCH
  CORE --> OBJECT
```

---

## 2) Credential Pathway Engine (Core Differentiator)
```mermaid
flowchart TD
  USER[User Credentials + Profile] --> MAP[NOC + Profession Mapping]
  MAP --> REQ[Licensing Requirements by Province]
  REQ --> STEP[Step-by-Step Pathway Builder]
  STEP --> TIME[Time + Cost Estimation]
  STEP --> OUTPUT[Personalized Credential Roadmap]
```

---

## 3) Job Eligibility Graph (Now vs Later)
```mermaid
flowchart LR
  PROFILE[User Skills + Credentials] --> ELIG[Eligibility Graph Builder]
  ELIG --> NOW[Eligible Now Roles]
  ELIG --> SOON[Eligible in 3-6 Months]
  ELIG --> LATER[Eligible After Licensing]

  NOW --> JOBS[Verified Jobs Index]
  SOON --> UPSKILL[Bridging Programs]
  LATER --> LIC[Licensing Steps]
```

---

## 4) Verified Hiring Marketplace
```mermaid
flowchart TD
  EMP[Employer] --> VERIFY[Verification Service]
  VERIFY --> REG[Business Registry Validation]
  VERIFY --> DOMAIN[Domain + Trust Signals]
  VERIFY --> SCORE[Hiring Intent Score]
  SCORE --> VERIFIED[Trusted Employer Index]

  VERIFIED --> JOBS[Verified Job Listings]
  JOBS --> USERS[Matched Candidates]
```

---

## 5) Outcome Accountability Engine
```mermaid
flowchart TD
  USER[User Journey] --> EVENTS[Credential + Job Events]
  EVENTS --> OUTCOME[Outcome Analytics Service]
  OUTCOME --> METRICS[Time-to-Interview, Placement Rate]
  METRICS --> DASH[Agency & Admin Dashboards]
```

---

## 6) B2B Distribution Flywheel
```mermaid
flowchart LR
  AGENCIES[Settlement Agencies] --> DASH[Agency Dashboard]
  DASH --> COHORT[Cohort Tracking + Readiness Scores]
  COHORT --> EMPLOYERS[Employer Pipeline]

  EMPLOYERS --> HIRES[Verified Placements]
  HIRES --> TRUST[Platform Trust & Adoption]
  TRUST --> AGENCIES
```