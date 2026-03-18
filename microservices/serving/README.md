# Serving Layer

This directory contains the two microservices responsible for delivering processed data to end users.

```
serving/
├── recommendation_loader/    # Reads from HDFS curated zone, writes to PostgreSQL
└── recommendation_api/       # REST API serving recommendations from PostgreSQL
```

## Data Flow

```mermaid
flowchart LR
    A["HDFS curated zone"] --> B["Recommendation Loader"]
    B --> C["PostgreSQL"]
    C --> D["Recommendation API"]
    D --> E["Client"]
```

| Service | Role | Technology |
|---|---|---|
| [recommendation_loader](recommendation_loader/) | Loads precomputed results into the serving database | Python 3.11, psycopg2 / PySpark |
| [recommendation_api](recommendation_api/) | JWT-protected REST API for querying recommendations and student features | FastAPI, Uvicorn, psycopg2 |

See each subdirectory's `README.md` for implementation details.
