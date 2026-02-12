# Phase 1 Deployment & Scaling Diagrams

## 6) Deployment Architecture (Cloud-Neutral)
```mermaid
flowchart TD
  USERS[Users] --> CDN[CDN / Edge Cache]
  CDN --> LB[Load Balancer]

  LB --> FE[Frontend Service (Next.js)]
  LB --> API[API Gateway]

  API --> AUTH[Auth Service]
  API --> CORE[Core API Service]
  API --> MLAPI[ML Service API]

  CORE --> DB[(PostgreSQL)]
  CORE --> CACHE[(Redis)]
  CORE --> SEARCH[(OpenSearch)]
  CORE --> OBJECT[(Object Storage)]

  MLAPI --> QUEUE[Message Queue]
  QUEUE --> WORKERS[Async Workers]
  WORKERS --> DB
  WORKERS --> SEARCH

  subgraph Observability
    LOGS[Centralized Logs]
    METRICS[Metrics/Tracing]
    ALERTS[Alerting]
  end

  FE --> LOGS
  API --> LOGS
  MLAPI --> LOGS
  CORE --> METRICS
  WORKERS --> METRICS
  ALERTS --> CORE
```

---

## 7) Scalability & Failover (Service-Level)
```mermaid
flowchart LR
  subgraph Region_A
    LB_A[Load Balancer]
    FE_A[Frontend Pods]
    API_A[API Pods]
    DB_A[(Primary DB)]
    CACHE_A[(Redis)]
    SEARCH_A[(Search Cluster)]
  end

  subgraph Region_B
    LB_B[Load Balancer]
    FE_B[Frontend Pods]
    API_B[API Pods]
    DB_B[(Read Replica)]
    CACHE_B[(Redis Replica)]
    SEARCH_B[(Search Replica)]
  end

  LB_A <--> LB_B
  DB_A --> DB_B
  SEARCH_A --> SEARCH_B
  CACHE_A --> CACHE_B
```

---

## 8) CI/CD & Infrastructure Automation
```mermaid
flowchart TD
  DEV[Developer] --> GIT[GitHub Repo]
  GIT --> CI[CI Pipeline]
  CI --> TEST[Test + Security Scans]
  TEST --> BUILD[Build & Package]
  BUILD --> DEPLOY[Deploy to Staging]
  DEPLOY --> PROD[Deploy to Production]

  subgraph Infra
    IAC[Terraform / Pulumi]
    K8S[Kubernetes / ECS]
  end

  DEPLOY --> Infra
  IAC --> K8S
```