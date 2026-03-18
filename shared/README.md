# Shared

Cross-service contracts and utilities used by multiple microservices.

```
shared/
├── schema_contracts/
│   └── schema_contracts.json    # Data-format contracts (JSON Schema)
└── utils/                       # Shared utility modules (reserved)
```

## Schema Contracts

`schema_contracts/schema_contracts.json` defines the agreed data formats at every layer boundary:

| Layer | What It Specifies |
|---|---|
| **Raw zone** | Parquet schema for KT4, questions, and lectures (column names, types, partition keys) |
| **Curated zone** | Parquet schema for aggregated features, user vectors, and recommendations; includes data-quality gates (max null ratio, PK uniqueness, min rows) |
| **Serving store** | PostgreSQL table schemas (`recommendations`, `student_features`) with column types and primary keys |
| **API response** | JSON response structure for `/recommendations` and `/students/{user_id}/features` endpoints |

Any schema change must be reflected in this contract **before** modifying microservice code. This prevents silent format drift between services.
