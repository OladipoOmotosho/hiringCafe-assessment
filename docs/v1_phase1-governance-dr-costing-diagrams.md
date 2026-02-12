# Phase 1 Data Governance, Disaster Recovery, and Costing Diagrams

## 9) Data Governance & Access Controls
```mermaid
flowchart TD
  DATA[User Data] --> CLASSIFY[Data Classification]
  CLASSIFY --> PII[PII Data]
  CLASSIFY --> NONPII[Non-PII Data]

  PII --> ENCRYPT[Encryption at Rest]
  PII --> VAULT[Key Management]
  PII --> RBAC[Role-Based Access Control]

  NONPII --> ANALYTICS[Analytics & Reporting]

  RBAC --> AUDIT[Audit Logging]
  ANALYTICS --> DASH[Governance Dashboard]

  subgraph Policies
    PIPEDA[PIPEDA]
    GDPR[GDPR-Ready]
    RETENTION[Retention Policies]
  end

  AUDIT --> Policies
  DASH --> Policies
```

---

## 10) Disaster Recovery & Business Continuity
```mermaid
flowchart LR
  PRIMARY[Primary Region] --> BACKUP[Automated Backups]
  PRIMARY --> REPLICA[Cross-Region Replication]

  BACKUP --> COLD[Cold Storage]
  REPLICA --> FAILOVER[Failover Region]

  FAILOVER --> RESTORE[Restore Services]
  RESTORE --> RTO[RTO < 4 Hours]
  RESTORE --> RPO[RPO < 30 Minutes]
```

---

## 11) Costing Model (High-Level)
```mermaid
flowchart TD
  COSTS[Monthly Cloud Costs] --> COMPUTE[Compute]
  COSTS --> STORAGE[Storage]
  COSTS --> SEARCH[Search Cluster]
  COSTS --> DATA[Data Pipelines]
  COSTS --> OBS[Observability]
  COSTS --> SECURITY[Security & Compliance]

  COMPUTE --> FE_COST[Frontend]
  COMPUTE --> API_COST[API Services]
  COMPUTE --> ML_COST[ML Workers]

  STORAGE --> DB_COST[Postgres]
  STORAGE --> OBJ_COST[Object Storage]
  STORAGE --> BACKUP_COST[Backups]

  DATA --> INGEST_COST[Ingestion]
  DATA --> ETL_COST[ETL/Orchestration]
```