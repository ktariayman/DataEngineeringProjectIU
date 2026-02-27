# Serving Store

PostgreSQL configuration and database schema for the serving layer.

```
serving_store/
└── postgres/
    ├── migrations/
    │   └── 01_recommendations.sql    # Creates recommendations + student_features tables
    └── seeds/                        # Seed data (reserved)
```

## Purpose

PostgreSQL acts as the serving database — the bridge between the batch pipeline and the REST API. The recommendation loader writes processed results here; the recommendation API reads them for fast lookups.

## Schema

Defined in [postgres/migrations/01_recommendations.sql](postgres/migrations/01_recommendations.sql), auto-applied on first container boot:

| Table | Key Columns | Purpose |
|---|---|---|
| `recommendations` | `user_id`, `recommended_user_id`, `similarity_score`, `rank`, `generation_date` | Precomputed Top-K similar students |
| `student_features` | `user_id`, `accuracy_rate`, `avg_response_time_ms`, `total_interactions`, ... | Aggregated per-student learning features |

## Docker Image

Uses the official `postgres:14` image. Migration scripts are mounted into `/docker-entrypoint-initdb.d/` and run automatically on first boot.

See [postgres/](postgres/) for details.
