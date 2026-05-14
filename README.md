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
| **Code quality** | Layered packages, explicit typing (incl. DB engine/session), DRY OpenAPI responses, `StrEnum` roles, `raise ... from None` on mapped DB errors; **`ruff`** in `pyproject.toml` + `requirements-dev.txt`. |
| **API design** | `/users` resource, **`POST /users/register`** (sign-up alias), verbs and codes (`201`, `204`, `404`, `409`), `PATCH` partial updates. |
| **Data handling** | Pydantic (`EmailStr`, length limits), role `Enum`, SQLAlchemy + DB constraints; explicit uniqueness conflicts. |
| **Testing** | SQLite (rápido) + integración Postgres en CI; invariantes de negocio y contrato REST. |
| **Documentation** | README + JSON and **curl** examples per endpoint; Swagger UI at `/docs`. |
| **Cloud / CI/CD** | Multi-stage `Dockerfile`, `cloudbuild.yaml` (pytest → image → Artifact Registry → Cloud Run), **`DATABASE_URL` from Secret Manager**. |

### Repository layout

- **`app/core`** — Settings (`pydantic-settings`), SQLAlchemy engine/session, shared HTTP/error helpers  
- **`app/models`** — ORM entities  
- **`app/schemas`** — Pydantic I/O models and error envelopes  
- **`app/crud`** — Persistence logic invoked by routers  
- **`app/api`** — `deps.py` (shared FastAPI dependencies), `router.py`, **`endpoints/`** — thin HTTP handlers  
- **`tests/`** — pytest: contract tests, business-scenario suites, optional **`integration/`** (Postgres)  

Also: **`Dockerfile`**, **`cloudbuild.yaml`**, **`supabase/migrations/`** (Postgres DDL and triggers).

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

- **`tests/test_users.py`**: contracts HTTP (CRUD status codes).
- **`tests/test_users_business.py`**: reglas de negocio (paginación, unicidad en `PATCH`, cuentas desactivadas, borrados, roles).
- **`tests/integration/`** (`@pytest.mark.integration`): mismo contrato contra **Postgres** vía **`INTEGRATION_DATABASE_URL`** (DDL en tablas mapeadas; ver [`tests/integration/conftest.py`](tests/integration/conftest.py)).

Sin Postgres local, esa carpeta **se omite**:

```bash
pip install -r requirements.txt
pytest -v
```

Con Postgres efímero o una base `_test`:

```bash
export INTEGRATION_DATABASE_URL='postgresql+psycopg2://USER:PASSWORD@localhost:5432/myapp_test'
pytest -v   # ejecuta SQLite + integración
```

**CI/CD**: `.github/workflows/ci-cd-cloud-run.yml` y `cloudbuild.yaml` levantan **Postgres 16 Alpine** solo para los tests (`app_integration_test`, usuario `test`), exportan `INTEGRATION_DATABASE_URL` y ejecutan **`pytest`** **antes** de construir/desplegar.

### Estilo y buenas prácticas (Python)

En [`pyproject.toml`](pyproject.toml) está configurado **[Ruff](https://docs.astral.sh/ruff/)** (lint + formato, import order tipo isort, reglas `pyupgrade` / bugbear). Opcional en local:

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

### Diseño REST (recursos)

- **Colección** `GET /users/`: página de usuarios ordenada por `created_at` y `id` (paginación estable con `skip` / `limit`).
- **Item** `GET|PATCH|DELETE /users/{id}`: una fila-usuario como recurso nominal.
- **`POST /users/`** y **`POST /users/register`**: **`201 Created`** más cabecera **`Location`** → URI canónica del nuevo recurso (`GET` del mismo id).
- **`PATCH`**: cambio parcial de representación; **`DELETE`** elimina el recurso (segunda llamada devuelve **`404`** tras el primer éxito).

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

Interactive docs (**OpenAPI**) with runnable requests: **`GET /docs`** (Swagger UI), **`GET /redoc`** (ReDoc), **`GET /openapi.json`** (raw schema).

## GCP: Cloud Build → Cloud Run

[`cloudbuild.yaml`](cloudbuild.yaml) runs **`pytest`** (SQLite + ephemeral Postgres for integration), builds a **`linux/amd64`** image, pushes to **Artifact Registry**, and deploys to **Cloud Run** mounting **`DATABASE_URL`** from **Secret Manager** (`_DATABASE_SECRET`). Adjust substitutions at the top of the file (region, service name, repo, CPU/memory, secret name).

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

- **Access**: middleware logs method, path, status code, and duration (`app/main.py`).
- **Startup**: lifespan logs application start; root level from **`LOG_LEVEL`** (default **`INFO`**, see `.env.example`).
- **Registration**: **`POST /users/register`** logs completion with `id` and `username` (`app.api.endpoints.users`).
- **Persistence**: CRUD **`INFO`** / **`WARNING`** on create/update/delete and integrity conflicts (`app/crud/user.py`).

Set **`LOG_LEVEL`** next to **`DATABASE_URL`** in `.env` or the runtime environment (e.g. Cloud Run **Variables**).


