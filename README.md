# Users API (FastAPI + Supabase/Postgres + GCP)

[![GitHub Actions — CI/CD](https://github.com/godie007/fastapi-supabase-gcp-challenge/actions/workflows/ci-cd-cloud-run.yml/badge.svg)](https://github.com/godie007/fastapi-supabase-gcp-challenge/actions/workflows/ci-cd-cloud-run.yml)

**Deployment (Cloud Run, demo):** [**https://fastapi-users-api-395887947282.us-central1.run.app**](https://fastapi-users-api-395887947282.us-central1.run.app) · [**`/docs`**](https://fastapi-users-api-395887947282.us-central1.run.app/docs) · [**`/openapi.json`**](https://fastapi-users-api-395887947282.us-central1.run.app/openapi.json)  
*(URL aligned with [`docs/CLOUD-RUN.md`](docs/CLOUD-RUN.md); change it if your service or project differ.)*

REST API to manage users with typed roles, Pydantic validation, basic structured logging, and a CI/CD pipeline on Google Cloud Build to Cloud Run.

## Stack

- **FastAPI** + **Uvicorn**
- **SQLAlchemy 2** + **psycopg2** (Postgres; compatible with **Supabase** connection strings)
- **Pydantic v2** (`EmailStr`, `ConfigDict`, OpenAPI examples)
- **pytest** + **httpx** (`TestClient`)
- **slowapi** (rate limiting / **`429`**; configurable via env) (submission)

This repository fulfills the **FastAPI users REST API** challenge: Postgres persistence (e.g. Supabase), **pytest** tests, **OpenAPI/Swagger** docs at `/docs`, error handling (`404` / `409` / validation), basic **logging**, and **GCP CI/CD** via `cloudbuild.yaml` (tests → Docker build → push → **Cloud Run**).

### Mapping — evaluation criteria

| Criterion | How it is addressed |
|-----------|---------------------|
| **Code quality** | Layered packages, explicit typing (incl. DB engine/session), DRY OpenAPI responses, `StrEnum` roles, `raise ... from None` on mapped DB errors; **`ruff`** in `pyproject.toml` + `requirements-dev.txt`. |
| **API design** | `/users` resource, **`POST /users/register`** (sign-up alias), verbs and codes (`201`, `204`, `404`, `409`), `PATCH` partial updates. |
| **Data handling** | Pydantic (`EmailStr`, length limits), role `Enum`, SQLAlchemy + DB constraints; explicit uniqueness conflicts. |
| **Testing** | **`api`**, **`domain`**, **`unit`**, and **`integration`** layers; Postgres in CI; **`pytest-cov`** with a **`>= 80%`** threshold on `app/`. |
| **Documentation** | CI badges, deployment URL, enhanced OpenAPI; [`docs/API.md`](docs/API.md) (complementary reference); `curl` examples in README. |
| **Abuse / quotas** | **`slowapi`** (env `RATE_LIMIT_*`) + edge hardening (Cloud Armor / API Gateway); `limit` ≤ 500 on list endpoints. |
| **Cloud / CI/CD** | `cloudbuild.yaml` + Artifact Registry + Cloud Run; checklist [`docs/GCP-DEPLOY.md`](docs/GCP-DEPLOY.md); details for **`DATABASE_URL`** (Secret Manager), IAM (`docs/IAM-SETUP.md`). |

### Repository layout

- **`app/core`** — Settings (`pydantic-settings`), SQLAlchemy engine/session, shared HTTP/error helpers  
- **`app/models`** — ORM entities  
- **`app/schemas`** — Pydantic I/O models and error envelopes  
- **`app/crud`** — Persistence logic invoked by routers  
- **`app/api`** — `deps.py` (shared FastAPI dependencies), `router.py`, **`endpoints/`** — thin HTTP handlers  
- **`tests/`** — Organized pytest (`api`, `domain`, `unit`, `integration`)  

Also: **`Dockerfile`**, **`cloudbuild.yaml`**, **`supabase/migrations/`** (Postgres DDL and triggers), **[`docs/API.md`](docs/API.md)** (complementary API reference).

## API and platform documentation

| Resource | Contents |
|---------|-----------|
| **Interactive (runtime)** | **`/docs`** (Swagger UI), **`/redoc`**, **`/openapi.json`** — see also the description in the OpenAPI header (`app/openapi_metadata.py`). |
| **Written reference** | **[`docs/API.md`](docs/API.md)** — resources, pagination, status codes, error format. |
| **`curl` examples** | **Example API calls** section below in this README. |
| **GCP (deployment)** | **[`docs/GCP-DEPLOY.md`](docs/GCP-DEPLOY.md)** checklist + deep links (**Cloud Run**, **IAM**, **secrets**). |

## API abuse prevention and quotas

- **In the application** (basic mitigation): [slowapi](https://github.com/laurentS/slowapi) enforces per-**client IP** quotas (`X-Forwarded-For` behind reverse proxies). Environment variables: **`RATE_LIMIT_ENABLED`**, **`RATE_LIMIT_DEFAULT`**, **`RATE_LIMIT_WRITE_POST`** (see [`.env.example`](.env.example)). **`429 Too Many Requests`** is documented in OpenAPI.
- **Pagination**: `GET /users/` caps **`limit`** at **500** rows to avoid oversized payloads.
- **At the edge (production)** (recommended in addition to in-process limits): [**Cloud Armor**](https://cloud.google.com/armor) (WAF / rate-based rules), [**API Gateway**](https://cloud.google.com/api-gateway) with quotas or keys, IAP, or another **API key** in front of Cloud Run; see [Cloud Run — security](https://cloud.google.com/run/docs/securing/service-identity).
- **Tests**: pytest disables rate limits (`RATE_LIMIT_ENABLED=false` in [`tests/conftest.py`](tests/conftest.py)) so assertions are not skewed by throttling.

## Local setup


### Environment variables

Create a `.env` file at the project root:

```bash
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/postgres
# optional: DEBUG, INFO (default), WARNING, ERROR, CRITICAL
# LOG_LEVEL=INFO
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

- **`tests/api/`**: HTTP contracts (status codes, headers, **`422`** validation, **`409`** on create/`PATCH`).
- **`tests/domain/`**: Business scenarios (pagination, global uniqueness, lifecycle, **`409`** messages).
- **`tests/unit/`**: Fast — **`@pytest.mark.unit`**, mostly Pydantic and domain exceptions.
- **`tests/integration/`**: **`@pytest.mark.integration`** — same app against a persistent engine for the session: **PostgreSQL** if you set **`INTEGRATION_DATABASE_URL`**; otherwise **in-memory SQLite** (no skips; fine for development — see [`tests/integration/conftest.py`](tests/integration/conftest.py)).

Markers are declared in [`pytest.ini`](pytest.ini).

**Coverage** (`pytest-cov` in `requirements-dev.txt`; CI runs **`--cov=app`** with an **`80%`** threshold):

```bash
pip install -r requirements-dev.txt
pytest tests --cov=app --cov-report=term-missing
```

```bash
pip install -r requirements.txt
pytest -v
```

`pytest tests` runs all packages (**integration included**, with ephemeral SQLite if you do not define Postgres). To force **PostgreSQL** locally:

```bash
export INTEGRATION_DATABASE_URL='postgresql+psycopg2://USER:PASSWORD@localhost:5432/myapp_test'
pytest -v
```

**CI/CD**: `.github/workflows/ci-cd-cloud-run.yml` and `cloudbuild.yaml` spin up **Postgres 16 Alpine** for tests only (`app_integration_test`, user `test`), export `INTEGRATION_DATABASE_URL`, and run **`pytest`** **before** build/deploy.

### Style and tooling (Python)

[`pyproject.toml`](pyproject.toml) configures **[Ruff](https://docs.astral.sh/ruff/)** (lint + format, import order like isort, `pyupgrade` / bugbear rules). Optional locally:

```bash
pip install -r requirements-dev.txt
ruff check app tests
ruff format app tests
```

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
| POST | `/users/register` | Register / sign-up — same body and rules as **`POST /users/`** (`201`) |
| GET | `/users/` | List users (pagination `skip`, `limit`) |
| GET | `/users/{id}` | Get user by UUID (`404` if missing) |
| PATCH | `/users/{id}` | Partial update (`404` / `409` as applicable) |
| DELETE | `/users/{id}` | Delete user (`204 No Content`) |

**Registration** is an explicit alias for onboarding documentation; there is no separate password or session (out of scope for this API).

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

### REST design (resources)

- **Collection** `GET /users/`: page of users ordered by `created_at` and `id` (stable paging with `skip` / `limit`).
- **Item** `GET|PATCH|DELETE /users/{id}`: a single user row as a named resource.
- **`POST /users/`** and **`POST /users/register`**: **`201 Created`** plus **`Location`** header → canonical URI of the new resource (`GET` by the same id).
- **`PATCH`**: partial representation update; **`DELETE`** removes the resource (a second call returns **`404`** after the first success).

### Example API calls (`curl`)

Set a base URL and, after creating a user, use the **`id`** returned by **`POST`** (UUID v4) as **`USER_ID`**.

```bash
export BASE_URL=http://localhost:8000
```

#### 1. `POST /users/` — Create user (**`201`**)

Creates a profile; **`id`**, **`created_at`**, and **`updated_at`** are assigned server-side. The **`Location`** response header equals **`${BASE_URL}/users/{id}`** (inspect with **`curl -i`**).

```bash
curl -sS -X POST "${BASE_URL}/users/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jdoe",
    "email": "jdoe@example.com",
    "first_name": "Jane",
    "last_name": "Doe",
    "role": "user",
    "active": true
  }'
```

Recommended: **`export USER_ID='<paste-id-from-post-response>'`**.

**Registration (alias)** — same JSON and status codes as **`POST /users/`**:

```bash
curl -sS -X POST "${BASE_URL}/users/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "signupuser",
    "email": "signupuser@example.com",
    "first_name": "Sam",
    "last_name": "Ple",
    "role": "user",
    "active": true
  }'
```

#### 2. `GET /users/` — List users (**`200`**)

Query parameters **`skip`** (default `0`, ≥ 0) and **`limit`** (default `100`, range 1–500). Rows are ordered by **`created_at`**, then **`id`**, so paging is deterministic.

```bash
curl -sS "${BASE_URL}/users/?skip=0&limit=10"
```

#### 3. `GET /users/{id}` — Get user by id (**`200`** / **`404`**)

Path parameter **`id`** must be a valid UUID matching an existing row.

```bash
curl -sS "${BASE_URL}/users/${USER_ID}"
```

#### 4. `PATCH /users/{id}` — Partial update (**`200`** / **`404`** / **`409`**)

Only fields present in the body are modified (no full replacement semantics).

```bash
curl -sS -X PATCH "${BASE_URL}/users/${USER_ID}" \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Janet","role":"admin","active":true}'
```

#### 5. `DELETE /users/{id}` — Delete user (**`204`** / **`404`**)

Successful delete returns **`204`** with **no JSON body**.

```bash
curl -sS -o /dev/null -w "%{http_code}\n" -X DELETE "${BASE_URL}/users/${USER_ID}"
```

(Optional) confirm removal:

```bash
curl -sS -w "\n%{http_code}\n" "${BASE_URL}/users/${USER_ID}"
```

#### Error response examples (`curl`)

**`404`** — user does not exist:

```bash
curl -sS "${BASE_URL}/users/00000000-0000-0000-0000-000000000099"
```

**`409`** — duplicate email on create (attempt a second **`POST`** reusing **`jdoe@example.com`**):

```bash
curl -sS -w "\nHTTP %{http_code}\n" -X POST "${BASE_URL}/users/" \
  -H "Content-Type: application/json" \
  -d '{"username":"jdoe2","email":"jdoe@example.com","first_name":"X","last_name":"Y","role":"guest"}'
```

**`422`** — malformed UUID on path:

```bash
curl -sS "${BASE_URL}/users/not-a-uuid"
```

**Pretty-print with `jq`**: append **`| jq .`** to any **`curl`** that returns JSON (`GET` / **`POST`** / **`PATCH`** with body).

## GCP: implementation (Cloud Build → Cloud Run)

**Quick checklist** and IAM/secrets links: **[`docs/GCP-DEPLOY.md`](docs/GCP-DEPLOY.md)** — service details, diagrams, and day-to-day operations in **[`docs/CLOUD-RUN.md`](docs/CLOUD-RUN.md)**.

[`cloudbuild.yaml`](cloudbuild.yaml) runs **`pytest`** (SQLite + ephemeral Postgres for integration), builds a **`linux/amd64`** image, pushes to **Artifact Registry**, and deploys to **Cloud Run** mounting **`DATABASE_URL`** from **Secret Manager** (`_DATABASE_SECRET`). Adjust substitutions at the top of the file (region, service name, repo, CPU/memory, secret name).

**Steps before the first `gcloud builds submit`:**

1. Enable **`run.googleapis.com`**, **`artifactregistry.googleapis.com`**, **`cloudbuild.googleapis.com`**, and **Secret Manager** on the project.
2. Create a Docker repository in Artifact Registry (name consistent with `_AR_REPOSITORY`).
3. Store the Postgres URL (**`postgresql+psycopg2://…`**) as the secret referenced by **`_DATABASE_SECRET`**.
4. Grant Cloud Build IAM (**`roles/run.admin`**, **`roles/artifactregistry.writer`**, **`roles/iam.serviceAccountUser`**, **`roles/secretmanager.secretAccessor`** on the secret as applicable).

Grant the **Cloud Build** service account (`PROJECT_NUMBER@cloudbuild.gserviceaccount.com`) according to those roles where your org policy permits.

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

- **Access**: middleware logs method, path, status code, and duration (`app/main.py`).
- **Startup**: lifespan logs application start; root level from **`LOG_LEVEL`** (default **`INFO`**, see `.env.example`).
- **Registration**: **`POST /users/register`** logs completion with `id` and `username` (`app.api.endpoints.users`).
- **Persistence**: CRUD **`INFO`** / **`WARNING`** on create/update/delete and integrity conflicts (`app/crud/user.py`).

Set **`LOG_LEVEL`** next to **`DATABASE_URL`** in `.env` or the runtime environment (e.g. Cloud Run **Variables**).

