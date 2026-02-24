# Recommendation API — Testing Guide

> Run these steps in order to verify the full API flow works end-to-end.
> Steps 1–4 can be verified without real recommendation data.
> Step 5 requires the **Recommendation Loader** to have completed (HDFS → PostgreSQL).

---

## Prerequisites

```bash
# 1. Network must exist
docker network create uni_net   # skip if already exists

# 2. Build the image (only needed after code changes)
docker compose build recommendation_api

# 3. Start postgres + API
docker compose up -d postgres recommendation_api

# 4. Apply the DB migration (only needed once, on first run)
docker exec -i postgres psql -U postgres -d recommendations \
  < serving_store/postgres/migrations/01_recommendations.sql

# 5. Wait ~10 seconds, then verify both are healthy
docker compose ps
# Expected: postgres (healthy) | recommendation_api (healthy)
```

---

## Step 1 — Health Check

```bash
curl -s http://localhost:8000/health | python -m json.tool
```

**Expected:**
```json
{
    "status": "ok",
    "db": "ok"
}
```

If `db` shows `unavailable` → check `docker compose logs recommendation_api` for the actual error.

---

## Step 2 — Protected Endpoint Requires Auth (expect 401)

```bash
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/v1/recommendations/me
```

**Expected:** `401`

---

## Step 3 — Get a Token

```bash
curl -s -X POST http://localhost:8000/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_42", "api_key": "dev-api-key"}' \
  | python -m json.tool
```

**Expected:**
```json
{
    "access_token": "eyJ0eXAiO...",
    "token_type": "bearer",
    "expires_in_seconds": 86400,
    "user_id": "user_42"
}
```

> **Default API key:** `dev-api-key` (set as `API_KEY` in `serving.yml`).
> In production, change this via the `API_KEY` environment variable.

---

## Step 4 — Call Protected Endpoint (empty list is correct before data is loaded)

```bash
# Save the token in one step
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_42", "api_key": "dev-api-key"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Call the protected endpoint
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/recommendations/me | python -m json.tool
```

**Expected (before loader runs):**
```json
{
    "user_id": "user_42",
    "count": 0,
    "results": []
}
```

> `count: 0` and empty `results` is **correct** at this stage.
> The loader has not yet moved data from HDFS to PostgreSQL.

---

## Step 5 — After Recommendation Loader Completes ✅

Once the loader has run (`docker compose run --rm recommendation_loader`),
repeat Step 4 with a `user_id` that exists in the loaded data.

**Expected (after loader runs):**
```json
{
    "user_id": "user_42",
    "count": 3,
    "results": [
        {
            "recommended_user_id": "user_99",
            "similarity_score": 0.94,
            "generation_date": "2026-02-23"
        },
        {
            "recommended_user_id": "user_77",
            "similarity_score": 0.87,
            "generation_date": "2026-02-23"
        }
    ]
}
```

You can also filter by a specific date:
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v1/recommendations/me?generation_date=2026-02-23" \
  | python -m json.tool
```

Or limit results:
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v1/recommendations/me?limit=5" \
  | python -m json.tool
```

---

## Step 6 — Verify Rows Directly in PostgreSQL

Cross-check what the API returns against what's actually in the DB:

```bash
docker exec postgres psql -U postgres -d recommendations \
  -c "SELECT user_id, recommended_user_id, similarity_score, generation_date
      FROM recommendations
      WHERE user_id = 'user_42'
      ORDER BY similarity_score DESC
      LIMIT 10;"
```

---

## Step 7 — Swagger UI (Alternative to curl)

Open in browser — no curl needed:
```
http://localhost:8000/docs
```

1. Click **`POST /v1/auth/token`** → **Try it out** → **Execute**
2. Copy the `access_token` from the response
3. Click **Authorize** (top right, 🔒 icon)
4. Paste the token → **Authorize**
5. Now all protected routes are unlocked — click **`GET /v1/recommendations/me`** → **Execute**

---

## Quick Reference — Env Vars

| Variable | Default | What it controls |
|---|---|---|
| `API_KEY` | `dev-api-key` | Key required to call `POST /v1/auth/token` |
| `JWT_SECRET` | `changeme` | Secret used to sign and verify JWTs |
| `POSTGRES_HOST` | `postgres` | PostgreSQL hostname (Docker service name) |
| `POSTGRES_DB` | `recommendations` | Database name |

> ⚠️ **Before deploying to production:** change `API_KEY` and `JWT_SECRET` to strong random values.
> Generate with: `openssl rand -hex 32`
