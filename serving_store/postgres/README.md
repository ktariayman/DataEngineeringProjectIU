# Serving Store — PostgreSQL

Database migrations and seed data for the PostgreSQL serving store.

```
postgres/
├── migrations/
│   └── 01_recommendations.sql    # DDL: creates tables + indexes
└── seeds/                        # Reserved for seed/test data
```

## Migration: `01_recommendations.sql`

Creates two tables on first boot:

### `recommendations`

| Column | Type | Constraint |
|---|---|---|
| `user_id` | `VARCHAR(50)` | NOT NULL |
| `recommended_user_id` | `VARCHAR(50)` | NOT NULL |
| `similarity_score` | `DOUBLE PRECISION` | NOT NULL |
| `rank` | `INTEGER` | NOT NULL |
| `generation_date` | `DATE` | NOT NULL, DEFAULT CURRENT_DATE |
| | | PRIMARY KEY (`user_id`, `recommended_user_id`) |

### `student_features`

| Column | Type | Constraint |
|---|---|---|
| `user_id` | `VARCHAR(50)` | PRIMARY KEY |
| `accuracy_rate` | `DOUBLE PRECISION` | |
| `avg_response_time_ms` | `DOUBLE PRECISION` | |
| `total_interactions` | `INTEGER` | |
| `unique_questions_attempted` | `INTEGER` | |
| `unique_lectures_viewed` | `INTEGER` | |
| `active_days` | `INTEGER` | |

## How It Works

The `postgres:14` Docker image automatically executes `.sql` files in `/docker-entrypoint-initdb.d/` on first startup. The migration file is mounted there via Docker Compose (`serving.yml`).

The recommendation loader populates these tables. The recommendation API reads from them.
