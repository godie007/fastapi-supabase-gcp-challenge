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

### GitHub Actions — tests on every push/PR, deploy on `main`

The workflow [`.github/workflows/ci-cd-cloud-run.yml`](.github/workflows/ci-cd-cloud-run.yml) runs **`pytest` first** on all branch pushes and on pull requests. **Deploy** (`gcloud builds submit` with [`cloudbuild.yaml`](cloudbuild.yaml), which runs tests again before building and updating Cloud Run) runs **only when tests succeed on `main`** (including **`workflow_dispatch`** from the Actions tab while `main` is checked out).

#### One-command GCP setup (Workload Identity Federation)

From the repo root, after [`gcloud auth login`](https://cloud.google.com/sdk/docs/authorizing) and sufficient IAM roles on the project (`roles/iam.workloadIdentityPoolAdmin`, `roles/iam.serviceAccountAdmin`, `roles/resourcemanager.projectIamAdmin`, etc.):

```bash
chmod +x scripts/setup-github-actions-wif.sh
./scripts/setup-github-actions-wif.sh YOUR_GITHUB_USER_OR_ORG/YOUR_REPO_NAME
# Optional second argument overrides project ID (default: integral-vim-494001-v4)
```

Example: `./scripts/setup-github-actions-wif.sh acme/fastapi-supabase-gcp-challenge`

The script enables APIs, creates a workload identity pool (`github`) + OIDC provider (`github-actions`), creates **`github-actions-deploy@…`** with **`roles/cloudbuild.builds.editor`**, **`roles/serviceusage.serviceUsageConsumer`**, and **`roles/storage.objectAdmin`** on the project (for **local** or **manual** `gcloud builds submit` using that SA). For **GitHub Actions**, [`.github/workflows/ci-cd-cloud-run.yml`](.github/workflows/ci-cd-cloud-run.yml) uses **direct Workload Identity Federation** (no SA impersonation): IAM uses **`principalSet`** **`attribute.repository/owner/repo`** and **`attribute.repository_owner/owner`** for Cloud Build / Service Usage / Storage / Token Creator on the **project**, and **`roles/storage.admin`** on **gs://PROJECT_NUMBER_cloudbuild** when it exists (**`storage.objectAdmin`** omits **`storage.buckets.get`**, which **`gcloud builds submit`** needs on that bucket). Optional **`roles/iam.workloadIdentityUser`** + **`roles/iam.serviceAccountTokenCreator`** on **`github-actions-deploy`** apply if you add **`service_account`** to **`google-github-actions/auth`** later. **`principalSet://…/subject/repo:…:*`** is **not** valid in GCP IAM—use **`principal://…/subject/<exact JWT sub>`** via **`WIF_EXACT_SUBJECT`** when you need subject-scoped bindings.

Override IDs via env if needed: **`WIF_POOL_ID`**, **`WIF_PROVIDER_ID`**, **`WIF_SA_ACCOUNT_ID`**, **`GCP_PROJECT_ID`**. Advanced: **`WIF_EXACT_SUBJECT`** — paste the full GitHub OIDC **`sub`** claim (from **Debug GitHub OIDC claims**) before running the script.

**Repository secrets** or **Variables** for deploy (GitHub → **Settings → Secrets and variables → Actions**):

| Name | Value |
|------|--------|
| **`GCP_PROJECT_ID`** | e.g. `integral-vim-494001-v4` |
| **`GCP_WORKLOAD_IDENTITY_PROVIDER`** | Full provider resource name (`projects/…/providers/…`) |

The **`projects/NUMBER`** in that provider name **must** be the GCP project where the pool was created (same project as **`GCP_PROJECT_ID`** unless you knowingly split pools).

The workflow uses **`google-github-actions/auth`** **without** **`service_account`**: credentials are **direct federation** to the project (see [Authenticate using Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines) and the **`google-github-actions/auth`** README section on direct WIF). **`gcloud builds submit`** then runs as the federated **`principalSet`**, which must keep Cloud Build + Storage + Service Usage IAM from **`setup-github-actions-wif.sh`**. Federated tokens are short-lived; the auth action’s credential file refreshes during the job—if you hit auth timeouts on **very** long builds, use a [Cloud Build repository trigger](https://cloud.google.com/build/docs/automating-builds/create-github-app-triggers) or fix SA impersonation IAM instead.

**Optional:** **`github-actions-deploy@…`** is still useful for local CLI runs; you do **not** need **`GCP_WIF_SERVICE_ACCOUNT`** in GitHub for the default workflow.

The workflow reads **`secrets.*` first**, then falls back to **`vars.*`**.

The default **Cloud Build service account** still executes build steps (Docker push, Cloud Run deploy — same IAM as [above](#iam-for-the-cloud-build-service-account)). If **`gs://PROJECT_NUMBER_cloudbuild`** does not exist yet, run one **`gcloud builds submit`** locally once (or let Cloud Build create it), then re-run the setup script so **bucket-level** **`roles/storage.admin`** bindings apply.

Set up federation following Google’s guide for GitHub: [Workload Identity Federation with GitHub Actions](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines#github).

To deploy from another branch, change the `if:` condition in the workflow `deploy` job to match your branch name.

**`auth` error: “The given credential is rejected by the attribute condition.”**  
GitHub’s JWT claims (`sub`, `repository`) vary by org settings and OIDC customization; strict CEL on the provider often rejects valid tokens.

**Fix (recommended):** use a **permissive** condition that still references a JWT claim (GCP rejects a literal `true`). Access is enforced by **project IAM** on **`principalSet`** (`attribute.repository` / `attribute.repository_owner`), not only by provider admission:

```bash
gcloud iam workload-identity-pools providers update-oidc github-actions \
  --project="integral-vim-494001-v4" \
  --location="global" \
  --workload-identity-pool="github" \
  --attribute-condition="assertion.sub != ''"
```

Or re-run **`./scripts/setup-github-actions-wif.sh owner/repo`** — default condition is **`assertion.sub != ''`**. Export **`WIF_STRICT_ATTRIBUTE_CONDITION=1`** first if you want strict `sub`/`repository` CEL; **`WIF_PROVIDER_ATTRIBUTE_CONDITION`** overrides the expression entirely.

Inspect claims from Actions: **Actions → Debug GitHub OIDC claims → Run workflow** ([`debug-github-oidc.yml`](.github/workflows/debug-github-oidc.yml)).

Optional strict CEL (only if it matches your org’s JWT exactly):

```bash
gcloud iam workload-identity-pools providers update-oidc github-actions \
  --project="integral-vim-494001-v4" \
  --location="global" \
  --workload-identity-pool="github" \
  --attribute-condition="(assertion.sub.startsWith('repo:codla/fastapi-supabase-gcp-challenge:')) || (assertion.repository == 'codla/fastapi-supabase-gcp-challenge')"
```

**`auth` / `setup-gcloud`: `Permission 'iam.serviceAccounts.getAccessToken' denied`**  
That permission is only used when **`google-github-actions/auth`** is configured with **`service_account`** (impersonation). This repo’s deploy workflow uses **direct federation** instead, so **`getAccessToken`** should not run.

If you **added impersonation yourself** (or restored an older workflow) and still see this:

1. **Re-run** **`./scripts/setup-github-actions-wif.sh owner/repo`** — it binds **`attribute.repository`** and **`attribute.repository_owner`** on the project **and** on **`github-actions-deploy`** with **`workloadIdentityUser`** + **`serviceAccountTokenCreator`** (optional **`WIF_EXACT_SUBJECT`** for **`principal://…/subject/…`**).
2. Match **`owner/repo`** to GitHub’s **`repository`** / **`sub`** claims (**Debug GitHub OIDC claims**).
3. Ensure **`GCP_WORKLOAD_IDENTITY_PROVIDER`**’s **`projects/NUMBER`** matches the pool project where those bindings were applied.

You can also mint tokens using **`principal://iam.googleapis.com/${POOL_PATH}/subject/${FULL_SUB_CLAIM}`** if you need one exact **`sub`** (copy **`sub`** from the debug workflow into IAM).

**`gcloud builds submit`: forbidden from accessing `*_cloudbuild` bucket / `serviceusage.services.use`**  
`gcloud builds submit` uploads sources to **gs://PROJECT_NUMBER_cloudbuild**. With **direct federation**, **`principalSet`** principals need **`roles/serviceusage.serviceUsageConsumer`** and **`roles/storage.objectAdmin`** on the **project**, plus **`roles/storage.admin`** **on that bucket** so **`storage.buckets.get`** succeeds (**`roles/storage.objectAdmin` alone does not include bucket metadata reads**). Re-run **`./scripts/setup-github-actions-wif.sh owner/repo`** after the bucket exists.

**One-shot project IAM** (mirrors **`setup-github-actions-wif.sh`**):

```bash
export PROJECT_ID=integral-vim-494001-v4
export PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
export REPO_SLUG='codla/fastapi-supabase-gcp-challenge'
export REPO_OWNER="${REPO_SLUG%%/*}"
export POOL_PATH="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github"

for MEMBER in \
  "principalSet://iam.googleapis.com/${POOL_PATH}/attribute.repository/${REPO_SLUG}" \
  "principalSet://iam.googleapis.com/${POOL_PATH}/attribute.repository_owner/${REPO_OWNER}"; do
  for ROLE in \
    roles/cloudbuild.builds.editor \
    roles/serviceusage.serviceUsageConsumer \
    roles/storage.objectAdmin \
    roles/iam.serviceAccountTokenCreator; do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="$MEMBER" \
      --role="$ROLE"
  done
done
```

Do **not** use **`principalSet://…/subject/repo:org/repo:*`** — IAM returns **`Invalid principalSet member`**. For an exact GitHub **`sub`**, use **`principal://iam.googleapis.com/${POOL_PATH}/subject/repo:org/repo:ref:refs/heads/main`** (see **`WIF_EXACT_SUBJECT`** in the setup script).

On **`github-actions-deploy`** only if you configure **`google-github-actions/auth`** with **`service_account`** (impersonation — requires **`getAccessToken`**):

```bash
export SA_EMAIL="github-actions-deploy@${PROJECT_ID}.iam.gserviceaccount.com"
for MEMBER in \
  "principalSet://iam.googleapis.com/${POOL_PATH}/attribute.repository/${REPO_SLUG}" \
  "principalSet://iam.googleapis.com/${POOL_PATH}/attribute.repository_owner/${REPO_OWNER}"; do
  for ROLE in roles/iam.workloadIdentityUser roles/iam.serviceAccountTokenCreator; do
    gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
      --project="$PROJECT_ID" \
      --member="$MEMBER" \
      --role="$ROLE"
  done
done
```

Explicit **bucket** IAM (after the bucket exists — use **`roles/storage.admin`** for the GitHub **`principalSet`** members too):

```bash
# Example: federated principal for repo slug MY_ORG/MY_REPO (adjust POOL_PATH / member).
gcloud storage buckets add-iam-policy-binding "gs://${PROJECT_NUMBER}_cloudbuild" \
  --project="$PROJECT_ID" \
  --member="principalSet://iam.googleapis.com/${POOL_PATH}/attribute.repository/${REPO_SLUG}" \
  --role="roles/storage.admin"

gcloud storage buckets add-iam-policy-binding "gs://${PROJECT_NUMBER}_cloudbuild" \
  --project="$PROJECT_ID" \
  --member="serviceAccount:github-actions-deploy@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.admin"
```

Or re-run **`./scripts/setup-github-actions-wif.sh owner/repo`** (applies SA + principalSet + bucket bindings when the bucket exists). If an **organization policy** denies Storage or Service Usage for your project or principals, an admin must allowlist the project or bucket.

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
