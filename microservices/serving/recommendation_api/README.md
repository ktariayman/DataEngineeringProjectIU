# Recommendation API

**Role in the pipeline:** Final delivery layer — a JWT-protected REST API that serves precomputed recommendations and student features from PostgreSQL. No heavy computation at query time.

```mermaid
flowchart LR
    A["PostgreSQL"] --> B["Recommendation API"]
    B --> C["Client"]
```

---

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/token` | API key in body | Issues a JWT (HS256, 24 h TTL) |
| `GET` | `/recommendations/{user_id}` | Bearer JWT | Top-K similar students (default 10, max 50) with similarity scores |
| `GET` | `/students/{user_id}/features` | Bearer JWT | Aggregated learning features for a student |
| `GET` | `/health` | None | Liveness probe (Docker healthcheck) |

---

## Authentication Flow

1. Client sends `POST /auth/token` with `{"user_id": "u1", "api_key": "<key>"}`
2. Server validates the API key (from `API_KEY` env var) and returns an HS256-signed JWT
3. Client includes `Authorization: Bearer <token>` on subsequent requests
4. JWT `sub` claim must match the requested `{user_id}` — mismatches return **HTTP 403**

JWTs are stateless, making the API horizontally scalable (any instance can verify any token).

---

## Implementation

| Component | Path | Purpose |
|---|---|---|
| App entry point | `src/app.py` | Creates FastAPI app, registers route modules |
| Auth routes | `src/routes/auth.py` | Token issuance with API-key validation |
| Recommendation routes | `src/routes/recommendations.py` | `/recommendations/{user_id}` and `/students/{user_id}/features` |
| Response schemas | `src/schemas/models.py` | Pydantic v2 models for request/response validation |
| Database pool | `src/services/database.py` | PostgreSQL connection pool (1–10 connections, psycopg2) |

---

## Database Tables (read-only)

| Table | Contents |
|---|---|
| `recommendations` | `user_id`, `recommended_user_id`, `similarity_score`, `rank`, `generation_date` |
| `student_features` | `user_id` + 17 aggregated learning features |

The API has **read-only** access — only the recommendation loader writes data.

---

## Configuration

- `config/api_config.yaml` — host, port, default/max `top_k`
- Environment variables: `API_KEY`, `JWT_SECRET`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_DB`

---

## Non-Functional Requirements

| Category | Implementation |
|---|---|
| **Reliability** | `/health` liveness probe (Docker, 30 s interval); connection pooling (1–10); graceful HTTP error responses (4xx / 5xx with JSON detail) |
| **Scalability** | Serves precomputed results (no real-time compute); indexed queries on `user_id`; stateless (horizontally scalable behind a load balancer) |
| **Maintainability** | Pydantic v2 schemas auto-generate OpenAPI docs; YAML config; separated route modules; structured logging |
| **Security** | JWT auth (HS256, 24 h TTL); API-key gating; token-scoped access (`sub` must match `{user_id}`); all secrets via env vars |
| **Privacy** | Only anonymised `user_id` and numerical scores served; no PII stored or returned |
| **Governance** | `generation_date` on every recommendation record; read-only database access |
