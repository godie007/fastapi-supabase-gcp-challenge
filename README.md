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
| **Code quality** | Packages `app/core`, `models`, `schemas`, `crud`, `api`; typing and brief docstrings at entry points. |
| **API design** | `/users` resource, HTTP verbs and status codes (`201`, `204`, `404`, `409`), partial updates with `PATCH`. |
| **Data handling** | Pydantic (`EmailStr`, length limits), role `Enum`, SQLAlchemy + DB constraints; explicit uniqueness conflicts. |
| **Testing** | `app/tests/` with happy paths and errors; isolated SQLite in CI without credentials. |
| **Documentation** | README + JSON and **curl** examples per endpoint; Swagger UI at `/docs`. |
| **Cloud / CI/CD** | Multi-stage `Dockerfile`, `cloudbuild.yaml` (pytest → image → Artifact Registry → Cloud Run), **`DATABASE_URL` from Secret Manager**. |

## Local setup

### Environment variables

Create a `.env` file at the project root:

```bash
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/postgres
```

Use `.env.example` as a template. If the password contains URL-reserved characters (e.g. `#`), percent-encode them (`#` → `%23`) so the URL parses correctly.

Supabase typically uses host `db.<project-ref>.supabase.co`; check Session pooler settings if your environment requires them.

### Run with Docker Compose

Starts Postgres with the initial schema and the API:

```bash
docker compose up --build
```

The API is at `http://localhost:8000` and interactive docs at `http://localhost:8000/docs`.

### Run without Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://...
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Tests

Tests use in-memory SQLite with `dependency_overrides` on `get_db`, without external credentials:

```bash
pip install -r requirements.txt
pytest app/tests -v
```

The Cloud Build test step sets `DATABASE_URL=sqlite://` for the same behavior.

## SQL schema (Supabase / Postgres)

If you manage the database outside Docker Compose, create a table equivalent to `app/models/user.py`:

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

Inserts are performed by the application (UUID generated in Python). The **`updated_at`** column is kept current by the ORM (`onupdate`) and, on Postgres/Supabase, by the trigger from migrations (`set_users_updated_at`).

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

## CI/CD on Google Cloud Platform

The [`cloudbuild.yaml`](cloudbuild.yaml) pipeline deploys the API to **Cloud Run**:

1. **pytest** — install dependencies and run `app/tests` with `DATABASE_URL=sqlite://`.
2. **Docker build** — **`linux/amd64`** image (required for Cloud Run from diverse builders), tagged with **`SHORT_SHA`** when present (Git-connected triggers) or **`BUILD_ID`** when you run `gcloud builds submit` without a SHA.
3. **Artifact Registry** — push to **`${_REGION}-docker.pkg.dev/$PROJECT_ID/${_AR_REPOSITORY}/${_IMAGE_NAME}:<tag>`**.
4. **Cloud Run** — `gcloud run deploy` with **`DATABASE_URL`** from **Secret Manager** (`${_DATABASE_SECRET}:latest`), **`--port 8080`**, **`--memory`**, **`--cpu`**, **`--timeout`**, **`--max-instances`**, **`--concurrency`**, **`--allow-unauthenticated`**.

Tune Cloud Run via substitutions in `cloudbuild.yaml`: **`_DATABASE_SECRET`**, **`_MEMORY`**, **`_CPU`**, **`_CLOUD_RUN_TIMEOUT`**, **`_MAX_INSTANCES`** (defaults match a small API).

`.gcloudignore` trims upload context to speed up **`gcloud builds submit`**.

### IAM for the Cloud Build service account

Grant **`PROJECT_NUMBER@cloudbuild.gserviceaccount.com`** at least:

- **`roles/run.admin`** — deploy and update Cloud Run services  
- **`roles/artifactregistry.writer`** — push images  
- **`roles/iam.serviceAccountUser`** — act as the Cloud Run runtime service account (often needed on first deploy)

Keep **`roles/secretmanager.secretAccessor`** on the DB secret for Cloud Build (deploy references the secret) and for the **Cloud Run default compute** service account.

### Manual build + deploy (same pipeline)

From the repo root (optional Git tag for traceability):

```bash
export PROJECT_ID=integral-vim-494001-v4   # adjust to your GCP project

gcloud builds submit \
  --project="$PROJECT_ID" \
  --config cloudbuild.yaml \
  --substitutions=SHORT_SHA="$(git rev-parse --short HEAD)"
```

If you omit **`SHORT_SHA`**, the image tag falls back to **`BUILD_ID`** automatically.

### GitHub trigger (continuous deploy to Cloud Run)

**Console (recommended):** **Google Cloud Console → Cloud Build → Triggers → Connect repository** (GitHub), then **Create trigger**: configuration type **Cloud Build configuration file**, location **Repository**, path **`cloudbuild.yaml`**, branch **`^main$`** (or your default branch).

**gcloud (classic GitHub mirror / older setups):** flags vary by whether you use **Cloud Build repositories (2nd gen)** or the legacy GitHub integration; run `gcloud builds triggers create github --help` for your CLI version. Typical shape:

```bash
export PROJECT_ID=your-gcp-project
export REGION=us-central1

gcloud builds triggers create github \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --name="deploy-users-api-cloud-run" \
  --repo-owner="YOUR_GITHUB_USER_OR_ORG" \
  --repo-name="fastapi-supabase-gcp-challenge" \
  --branch-pattern="^main$" \
  --build-config="cloudbuild.yaml"
```

Connected-repo triggers usually populate **`SHORT_SHA`** automatically on each push.

Prerequisites: APIs enabled (`run.googleapis.com`, `artifactregistry.googleapis.com`, `cloudbuild.googleapis.com`), **`app-images`** repository in Artifact Registry (**`us-central1`**), secret **`fastapi-supabase-gcp-challenge`** (or your **`_DATABASE_SECRET`**) with a single-line Postgres URI valid for SQLAlchemy, and **`roles/secretmanager.secretAccessor`** on that secret for the default Cloud Run compute service account and **`PROJECT_NUMBER@cloudbuild.gserviceaccount.com`**.

## Deployment commands (reference)

Variables used in this project (adjust if you rename resources):

```bash
export PROJECT_ID=integral-vim-494001-v4
export REGION=us-central1
export AR_REPO=app-images
export IMAGE_NAME=fastapi-users-api
export SERVICE=fastapi-users-api
export SECRET_NAME=fastapi-supabase-gcp-challenge
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
```

### 1. Context and APIs

```bash
gcloud config set project "$PROJECT_ID"

gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  --project="$PROJECT_ID"
```

### 2. Artifact Registry (Docker repository)

```bash
gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" --project="$PROJECT_ID" \
  || gcloud artifacts repositories create "$AR_REPO" \
       --repository-format=docker --location="$REGION" --project="$PROJECT_ID"
```

### 3. Local image → registry (alternative if `gcloud run deploy --source` fails)

On Apple Silicon, force **`linux/amd64`** for Cloud Run:

```bash
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

docker build --platform linux/amd64 \
  -t "${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${IMAGE_NAME}:latest" .

docker push "${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${IMAGE_NAME}:latest"
```

### 4. Secret permissions for `DATABASE_URL`

Cloud Run (default compute SA) and Cloud Build must **read** the secret:

```bash
for MEMBER in \
  "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  "${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"; do
  gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${MEMBER}" \
    --role="roles/secretmanager.secretAccessor"
done
```

### 5. Deploy / update Cloud Run

```bash
gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${IMAGE_NAME}:latest" \
  --allow-unauthenticated \
  --update-secrets=DATABASE_URL="${SECRET_NAME}:latest"
```

If your organization **disallows public invocation**, `--allow-unauthenticated` may fail; the service may stay restricted and you must call it with identity (step 7).

### 6. After changing the secret **value** in Secret Manager

Redeploy (you can use the **same** image) so instances mount the new secret version:

```bash
gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${IMAGE_NAME}:latest" \
  --update-secrets=DATABASE_URL="${SECRET_NAME}:latest"
```

### 7. Call the Cloud Run URL with identity

If `GET /docs` returns **403** without auth headers, use an identity token:

```bash
export RUN_URL="https://${SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app"

TOKEN="$(gcloud auth print-identity-token)"
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer ${TOKEN}" "${RUN_URL}/docs"
curl -s -H "Authorization: Bearer ${TOKEN}" "${RUN_URL}/users/"
```

The exact host also appears in the Cloud Run console (**Service URL**).

## Logging

- Startup message in the FastAPI **lifespan**.
- HTTP middleware logging method, path, status code, and approximate duration.
- CRUD layer with `INFO` / `WARNING` messages on relevant operations.
