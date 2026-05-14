# GitHub Actions CI/CD Workflow Documentation

This document explains the GitHub Actions workflow used for continuous integration and deployment.

---

## Overview

```mermaid
graph TB
    subgraph "Triggers"
        PUSH[Push to any branch]
        PR[Pull Request]
        MANUAL[Workflow Dispatch]
    end

    subgraph "Jobs"
        TEST[Test Job]
        BUILD[Build Job]
        DEPLOY[Deploy Job]
    end

    subgraph "GCP Services"
        WIF[Workload Identity]
        AR[Artifact Registry]
        CR[Cloud Run]
    end

    PUSH --> TEST
    PR --> TEST
    MANUAL --> TEST
    TEST --> BUILD
    BUILD --> DEPLOY
    DEPLOY --> WIF
    WIF --> AR
    AR --> CR
```

---

## Workflow File

**Location**: `.github/workflows/ci-cd-cloud-run.yml`

```yaml
name: CI/CD — Tests then Cloud Run

on:
  push:
    branches:
      - "**"
  pull_request:
  workflow_dispatch:

permissions:
  contents: read
  id-token: write
```

---

## Triggers

| Trigger | Event | Job Executed |
|---------|-------|--------------|
| Push to any branch | `push: branches: ["**"]` | Test |
| Pull request | `pull_request` | Test |
| Manual dispatch | `workflow_dispatch` | Test + Deploy |

---

## Permissions

```yaml
permissions:
  contents: read        # Read repository contents
  id-token: write      # Write OIDC tokens for WIF
```

### Permission Explanation

- `contents: read`: Required to checkout code
- `id-token: write`: Required to obtain OIDC token for Workload Identity Federation

---

## Job: Test

### Configuration

```yaml
test:
  name: Tests (pytest)
  runs-on: ubuntu-latest
  if: always()
```

### Steps

```mermaid
sequenceDiagram
    participant Runner as GitHub Runner
    participant GitHub as GitHub
    participant Python as Python
    participant Test as pytest

    Runner->>GitHub: actions/checkout@v4
    GitHub-->>Runner: Code
    Runner->>Python: actions/setup-python@v5
    Python-->>Runner: Python 3.12
    Runner->>Python: pip install -r requirements.txt
    Python-->>Runner: Dependencies
    Runner->>Test: pytest tests -v --cov=app --cov-fail-under=80
    Test-->>Runner: Test Results
```

### Step Details

#### 1. Checkout Code

```yaml
- uses: actions/checkout@v4
```

Downloads the repository code.

#### 2. Setup Python

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"
```

Installs Python 3.12.

#### 3. Install Dependencies

```yaml
- name: Install dependencies
  run: |
    pip install --no-cache-dir -r requirements.txt
    pip install --no-cache-dir pytest-cov
```

#### 4. Run Tests

```yaml
- name: Run pytest (SQLite + Postgres integration)
  env:
    DATABASE_URL: sqlite://
    INTEGRATION_DATABASE_URL: postgresql+psycopg2://test:test@127.0.0.1:5432/app_integration_test
  run: pytest tests -v --cov=app --cov-report=term-missing --cov-fail-under=80
```

SQLite for default tests; ephemeral **Postgres 16** (GitHub `services`) for `@pytest.mark.integration`. Coverage enforced at **80%** minimum on **`app/`**.

**Environment Variables:**

| Variable | Value | Purpose |
|----------|-------|---------|
| `DATABASE_URL` | `sqlite://` | Fast API tests backed by SQLite |
| `INTEGRATION_DATABASE_URL` | `postgresql+psycopg2://…app_integration_test` | Integration tests against Postgres |

---

## Job: Deploy

### Configuration

```yaml
deploy:
  name: Build & Deploy to Cloud Run
  runs-on: ubuntu-latest
  needs: test
  if: >-
    github.ref == 'refs/heads/main' &&
    (github.event_name == 'push' || github.event_name == 'workflow_dispatch')
```

### Dependencies

- **Needs**: `test` (runs only after tests pass)
- **Condition**: Only on `main` branch push or manual dispatch

### Steps

```mermaid
sequenceDiagram
    participant Runner as GitHub Runner
    participant WIF as Workload Identity
    participant GCP as Google Cloud
    participant AR as Artifact Registry
    participant CR as Cloud Run

    Runner->>WIF: Authenticate (google-github-actions/auth)
    WIF-->>Runner: GCP Credentials

    Runner->>GCP: gcloud auth print-access-token
    GCP-->>Runner: Access Token

    Runner->>AR: docker login (oauth2accesstoken)
    AR-->>Runner: Authenticated

    Runner->>AR: docker build & push
    AR-->>Runner: Image pushed

    Runner->>CR: gcloud run deploy
    CR-->>Runner: Service deployed
```

### Step Details

#### 1. Checkout Code

```yaml
- uses: actions/checkout@v4
```

#### 2. Authenticate to Google Cloud

```yaml
- id: auth
  name: Authenticate to Google Cloud
  uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER || vars.GCP_WORKLOAD_IDENTITY_PROVIDER }}
    project_id: ${{ secrets.GCP_PROJECT_ID || vars.GCP_PROJECT_ID }}
    export_environment_variables: true
    access_token_lifetime: 3600s
    access_token_scopes: https://www.googleapis.com/auth/cloud-platform
```

**Inputs:**

| Input | Source | Description |
|-------|--------|-------------|
| `workload_identity_provider` | Secret/Variable | WIF provider resource name |
| `project_id` | Secret/Variable | GCP project ID |
| `export_environment_variables` | `true` | Export GCP credentials |
| `access_token_lifetime` | `3600s` | Token valid for 1 hour |
| `access_token_scopes` | Cloud Platform | Full GCP API access |

**Outputs:**

| Output | Description |
|--------|-------------|
| `access_token` | GCP access token |

#### 3. Set up Docker

```yaml
- name: Set up Docker
  uses: docker/setup-buildx-action@v3
```

Sets up Docker BuildKit for building multi-platform images.

#### 4. Get GCP Access Token

```yaml
- name: Get GCP Access Token
  run: |
    ACCESS_TOKEN=$(gcloud auth print-access-token)
    echo "::add-mask::$ACCESS_TOKEN"
    echo "ACCESS_TOKEN=$ACCESS_TOKEN" >> $GITHUB_ENV
```

Gets a fresh access token for Docker login.

#### 5. Authenticate to Artifact Registry

```yaml
- name: Authenticate to Artifact Registry
  uses: docker/login-action@v3
  with:
    registry: us-central1-docker.pkg.dev
    username: oauth2accesstoken
    password: ${{ env.ACCESS_TOKEN }}
```

**Inputs:**

| Input | Value | Description |
|-------|-------|-------------|
| `registry` | `us-central1-docker.pkg.dev` | Artifact Registry URL |
| `username` | `oauth2accesstoken` | Authentication method |
| `password` | `${{ env.ACCESS_TOKEN }}` | Access token |

#### 6. Build and Push Image

```yaml
- name: Build and push image
  uses: docker/build-push-action@v6
  with:
    context: .
    push: true
    platforms: linux/amd64
    tags: us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID || vars.GCP_PROJECT_ID }}/app-images/fastapi-users-api:${{ github.sha }}
```

**Inputs:**

| Input | Value | Description |
|-------|-------|-------------|
| `context` | `.` | Build context |
| `push` | `true` | Push after build |
| `platforms` | `linux/amd64` | Required for Cloud Run |
| `tags` | Image tag | Using commit SHA |

**Image URL Pattern:**
```
us-central1-docker.pkg.dev/{PROJECT_ID}/app-images/fastapi-users-api:{SHA}
```

#### 7. Deploy to Cloud Run

```yaml
- name: Deploy to Cloud Run
  env:
    PROJECT_ID: ${{ secrets.GCP_PROJECT_ID || vars.GCP_PROJECT_ID }}
    REGION: ${{ vars.GCP_REGION || 'us-central1' }}
    SERVICE_NAME: ${{ vars.GCP_SERVICE_NAME || 'fastapi-users-api' }}
    IMAGE: us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID || vars.GCP_PROJECT_ID }}/app-images/fastapi-users-api:${{ github.sha }}
  run: |
    gcloud run deploy "${SERVICE_NAME}" \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --platform=managed \
      --image="${IMAGE}" \
      --port=8080 \
      --memory=512Mi \
      --cpu=1 \
      --timeout=300 \
      --max-instances=10 \
      --min-instances=0 \
      --concurrency=80 \
      --allow-unauthenticated
```

**Environment Variables:**

| Variable | Source | Default |
|----------|--------|---------|
| `PROJECT_ID` | Secret | Required |
| `REGION` | Variable | `us-central1` |
| `SERVICE_NAME` | Variable | `fastapi-users-api` |
| `IMAGE` | Calculated | From build step |

**gcloud flags:**

| Flag | Value | Description |
|------|-------|-------------|
| `project` | PROJECT_ID | GCP project |
| `region` | REGION | Cloud Run region |
| `platform` | managed | Cloud Run managed |
| `image` | IMAGE | Container image |
| `port` | 8080 | Container port |
| `memory` | 512Mi | Memory allocation |
| `cpu` | 1 | vCPU allocation |
| `timeout` | 300s | Request timeout |
| `max-instances` | 10 | Max scaling |
| `min-instances` | 0 | Min scaling |
| `concurrency` | 80 | Requests/instance |
| `allow-unauthenticated` | - | Public access |

---

## Secret and Variable Precedence

```mermaid
graph TB
    subgraph "Precedence Order"
        A[secrets.SECRET_NAME]
        B[vars.SECRET_NAME]
        C[Default Values]
    end

    A --> Top[Highest]
    B --> Middle
    C --> Bottom[Lowest]
```

The workflow uses: `${{ secrets.X || vars.X || 'default' }}`

---

## Monitoring

### Check Workflow Runs

```bash
# List recent runs
gh run list --limit 10

# View specific run
gh run view <run-id>

# View logs
gh run view <run-id> --log

# View failed step logs
gh run view <run-id> --log-failed
```

### Workflow Status

```bash
# Check if workflow is enabled
gh workflow list

# Enable/disable workflow
gh workflow enable ci-cd-cloud-run.yml
gh workflow disable ci-cd-cloud-run.yml
```

### Manual Trigger

```bash
# Trigger workflow manually
gh workflow run ci-cd-cloud-run.yml

# Trigger with inputs (if defined)
gh workflow run ci-cd-cloud-run.yml -f key=value
```

---

## Troubleshooting

### Tests Failing

```bash
# View test output
gh run view <run-id> --log-failed | grep -A 50 "Run pytest"

# Common causes:
# - Code changes breaking tests
# - Missing dependencies
# - DATABASE_URL issues
```

### Docker Build Failing

```bash
# Check build logs
gh run view <run-id> --log-failed | grep -A 20 "Build and push"
```

**Common issues:**
- Dockerfile not found
- Build context incorrect
- Platform not supported

### Deployment Failing

```bash
# Check deployment logs
gh run view <run-id> --log-failed | grep -A 30 "Deploy to Cloud Run"
```

**Common issues:**
- IAM permissions missing
- Artifact Registry not accessible
- Service name conflicts

---

## Security

### OIDC Token Security

- Short-lived tokens (1 hour)
- Scoped to specific project
- No long-lived credentials stored

### Workflow Security

```yaml
permissions:
  contents: read        # Minimal permissions
  id-token: write      # Only for WIF
```

### Best Practices

1. Use branch protection rules
2. Require status checks before merge
3. Use environment protection
4. Limit who can trigger workflows
5. Regularly review logs

---

## GitHub Actions Runner

| Property | Value |
|----------|-------|
| Runner | `ubuntu-latest` |
| OS | Ubuntu 24.04 LTS |
| Version | 20260413.86.1 |
| Docker | 28.0.4 |

---

## Summary

| Job | Trigger | Runs On | Condition |
|-----|---------|---------|-----------|
| Test | Push/PR/Manual | All branches | Always |
| Deploy | Push/Manual | `main` only | Tests pass |

| Step | Duration | Status |
|------|----------|--------|
| Checkout | ~2s | Required |
| Setup Python | ~10s | Required |
| Run Tests | ~15s | Pass/Fail |
| Build & Push | ~60s | Success |
| Deploy | ~30s | Success |