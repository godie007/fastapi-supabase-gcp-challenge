# Users API (FastAPI + Supabase/Postgres + GCP)

REST API to manage users with typed roles, Pydantic validation, basic structured logging, and a CI/CD pipeline on Google Cloud Build to Cloud Run.

## Stack

- **FastAPI** + **Uvicorn**
- **SQLAlchemy 2** + **psycopg2** (Postgres; compatible with **Supabase** connection strings)
- **Pydantic v2** (`EmailStr`, `ConfigDict`, OpenAPI examples)
- **pytest** + **httpx** (`TestClient`)
- **Docker** (multi-stage image) and **Cloud Build** → **Artifact Registry** → **Cloud Run**

## Software Engineer Challenge (submission)

This repository fulfills the **FastAPI users REST API** challenge: Postgres persistence (e.g. Supabase), **pytest** tests, **OpenAPI/Swagger** docs at `/docs`, error handling (`404` / `409` / validation), basic **logging**, and **GCP CI/CD** via `cloudbuild.yaml` (tests → Docker build → push → **Cloud Run**).

### Mapping — evaluation criteria

| Criterion | How it is addressed |
|-----------|---------------------|
| **Code quality** | Layered packages: `core` (settings, DB, errors), `models`, `schemas`, `crud`, `api` (`deps`, routers); typing and concise docstrings. |
| **API design** | `/users` resource, HTTP verbs and status codes (`201`, `204`, `404`, `409`), partial updates with `PATCH`. |
| **Data handling** | Pydantic (`EmailStr`, length limits), role `Enum`, SQLAlchemy + DB constraints; explicit uniqueness conflicts. |
| **Testing** | Root `tests/` (pytest) covering CRUD paths and conflicts; SQLite in CI without Postgres credentials. |
| **Documentation** | README + JSON and **curl** examples per endpoint; Swagger UI at `/docs`. |
| **Cloud / CI/CD** | Multi-stage `Dockerfile`, `cloudbuild.yaml` (pytest → image → Artifact Registry → Cloud Run), **`DATABASE_URL` from Secret Manager**. |

### Repository layout

- **`app/core`** — Settings (`pydantic-settings`), SQLAlchemy engine/session, shared HTTP/error helpers  
- **`app/models`** — ORM entities  
- **`app/schemas`** — Pydantic I/O models and error envelopes  
- **`app/crud`** — Persistence logic invoked by routers  
- **`app/api`** — `deps.py` (shared FastAPI dependencies), `router.py`, **`endpoints/`** — thin HTTP handlers  
- **`tests/`** — `pytest` + `TestClient`; SQLite via `dependency_overrides` on `get_db`  

Also: **`Dockerfile`**, **`cloudbuild.yaml`**, **`supabase/migrations/`** (Postgres DDL and triggers).

## Local setup

### Environment variables

Create a `.env` file at the project root:

```bash
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/postgres
```

Use `.env.example` as a template. If the password contains URL-reserved characters (e.g. `#`), percent-encode them (`#` → `%23`) so the URL parses correctly.

Supabase typically uses host `db.<project-ref>.supabase.co`; check Session pooler settings if your environment requires them.

### Run from source

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://...
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive docs: **`http://localhost:8000/docs`**.

### Run the container

Build the same image CI uses (`linux/amd64` on Cloud Run):

```bash
docker build --platform linux/amd64 -t users-api .
docker run --rm -p 8080:8080 -e DATABASE_URL="postgresql+psycopg2://..." users-api
```

### Tests

Tests use in-memory SQLite with `dependency_overrides` on `get_db`, without external Postgres:

```bash
pip install -r requirements.txt
pytest -v
```

The Cloud Build test step sets `DATABASE_URL=sqlite://` for the same behavior.

## SQL schema (Supabase / Postgres)

On any Postgres instance (including Supabase), create a table equivalent to `app/models/user.py`, or apply the scripts under **`supabase/migrations/`**.

```sql
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'user', 'guest')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    active BOOLEAN NOT NULL DEFAULT TRUE
);
```

Inserts use UUIDs from the application. The **`updated_at`** column is updated by the ORM (`onupdate`) and, on Postgres, by the trigger in migrations (`set_users_updated_at`).

## Endpoints

Example base URL: `http://localhost:8000`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/users/` | Create user (`201 Created`) |
| GET | `/users/` | List users (pagination `skip`, `limit`) |
| GET | `/users/{id}` | Get user by UUID (`404` if missing) |
| PATCH | `/users/{id}` | Partial update (`404` / `409` as applicable) |
| DELETE | `/users/{id}` | Delete user (`204 No Content`) |

### JSON examples

**POST `/users/` — request body**

```json
{
  "username": "jdoe",
  "email": "jdoe@example.com",
  "first_name": "Jane",
  "last_name": "Doe",
  "role": "user",
  "active": true
}
```

**Response (`201`)**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "jdoe",
  "email": "jdoe@example.com",
  "first_name": "Jane",
  "last_name": "Doe",
  "role": "user",
  "created_at": "2026-05-13T12:00:00Z",
  "updated_at": "2026-05-13T12:00:00Z",
  "active": true
}
```

**PATCH `/users/{id}` — partial example**

```json
{
  "first_name": "Janet",
  "role": "admin",
  "active": true
}
```

**Typical errors**

- `404`: user does not exist (detail `User not found: …`).
- `409`: duplicate `username` or `email`.
- `422`: invalid body (Pydantic validation / malformed UUID in path).

### `curl` examples (each CRUD operation)

Replace `BASE_URL` (e.g. `http://localhost:8000`) and `USER_ID` from the `POST` response.

```bash
BASE_URL=http://localhost:8000

# Create — 201 Created
curl -s -X POST "$BASE_URL/users/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jdoe",
    "email": "jdoe@example.com",
    "first_name": "Jane",
    "last_name": "Doe",
    "role": "user",
    "active": true
  }' | jq .

# Copy id from JSON above, for example:
USER_ID=550e8400-e29b-41d4-a716-446655440000

# Read (collection) — 200 OK
curl -s "$BASE_URL/users/?skip=0&limit=10" | jq .

# Read (item) — 200 OK
curl -s "$BASE_URL/users/$USER_ID" | jq .

# Update (partial) — 200 OK
curl -s -X PATCH "$BASE_URL/users/$USER_ID" \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Janet","role":"admin"}' | jq .

# Delete — 204 No Content (empty body)
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X DELETE "$BASE_URL/users/$USER_ID"

# Read after delete — 404
curl -s "$BASE_URL/users/$USER_ID" | jq .
```

Interactive docs: **`GET /docs`** (Swagger UI with descriptions, modeled error responses, and examples) and **`GET /redoc`** (ReDoc).

## GCP: Cloud Build → Cloud Run

[`cloudbuild.yaml`](cloudbuild.yaml) runs **`pytest`** (with `DATABASE_URL=sqlite://`), builds a **`linux/amd64`** image, pushes to **Artifact Registry**, and deploys to **Cloud Run** mounting **`DATABASE_URL`** from **Secret Manager** (`_DATABASE_SECRET`). Adjust substitutions at the top of the file (region, service name, repo, CPU/memory, secret name).

Grant the **Cloud Build** service account (`PROJECT_NUMBER@cloudbuild.gserviceaccount.com`) at least **`roles/run.admin`**, **`roles/artifactregistry.writer`**, **`roles/iam.serviceAccountUser`**, and **`roles/secretmanager.secretAccessor`** on the database secret as needed.

Enable **`run.googleapis.com`**, **`artifactregistry.googleapis.com`**, **`cloudbuild.googleapis.com`** on the project, create the Artifact Registry Docker repo if missing, store a Postgres URL as a Secret Manager secret, and run:

```bash
export PROJECT_ID=your-project-id

gcloud builds submit \
  --project="$PROJECT_ID" \
  --config cloudbuild.yaml \
  --substitutions=SHORT_SHA="$(git rev-parse --short HEAD)"
```

If **`SHORT_SHA`** is omitted, the image tag uses **`BUILD_ID`**. `.gcloudignore` keeps upload context small.

### GitHub Actions (optional)

Tests run on every push/PR; deployment on **`main`** builds the image with Docker and runs **`gcloud run deploy`** (see [`.github/workflows/ci-cd-cloud-run.yml`](.github/workflows/ci-cd-cloud-run.yml)). Configure **`GCP_PROJECT_ID`** and **`GCP_WORKLOAD_IDENTITY_PROVIDER`** ([Workload Identity Federation with GitHub Actions](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines#github)). Optional **`vars`**: **`GCP_REGION`**, **`GCP_SERVICE_NAME`** (comments in workflow).

## Logging

- Startup message in the FastAPI **lifespan**.
- HTTP middleware logging method, path, status code, and approximate duration.
- CRUD layer with `INFO` / `WARNING` messages on relevant operations.
