# Complete Architecture Documentation

This document provides a comprehensive overview of the FastAPI application architecture deployed on Google Cloud Platform, including CI/CD, IAM, Secrets, and Cloud Run.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Components](#components)
4. [GitHub Actions CI/CD Pipeline](#github-actions-cicd-pipeline)
5. [Google Cloud Platform Resources](#google-cloud-platform-resources)
6. [Secrets Management](#secrets-management)
7. [IAM and Security](#iam-and-security)
8. [Workload Identity Federation](#workload-identity-federation)
9. [Database Schema](#database-schema)
10. [API Endpoints](#api-endpoints)
11. [Troubleshooting](#troubleshooting)

---

## System Overview

The application is a RESTful API built with FastAPI that manages users with role-based access control. It is deployed on Google Cloud Run using a containerized Docker image, with authentication handled via Workload Identity Federation between GitHub Actions and GCP.

### Key Features

- **FastAPI** REST API with Pydantic validation
- **PostgreSQL/SQLAlchemy** for data persistence
- **pytest** for automated testing
- **Docker** containerization
- **GitHub Actions** for CI/CD
- **Google Cloud Run** for serverless deployment
- **Workload Identity Federation** for secure authentication
- **Secret Manager** for sensitive configuration

---

## Architecture Diagram

### High-Level Architecture

```mermaid
graph TB
    subgraph "GitHub"
        GH[GitHub Repository]
        GA[GitHub Actions]
        GHS[GitHub Secrets]
    end

    subgraph "Workload Identity Federation"
        WIFP[Workload Identity Provider<br/>github-actions]
        WIF[Workload Identity Pool<br/>github]
        STS[Google STS<br/>Token Exchange]
    end

    subgraph "Google Cloud Platform"
        AR[Artifact Registry<br/>app-images]
        CR[Cloud Run<br/>fastapi-users-api]
        SM[Secret Manager<br/>DATABASE_URL]
        GCS[Cloud Storage<br/>Build Artifacts]
        IAM[IAM & Admin]
        CB[Cloud Build<br/>Optional Trigger]
    end

    subgraph "Runtime"
        DB[(PostgreSQL<br/>Supabase)]
        API[FastAPI App<br/>uvicorn]
    end

    GH -->|push| GA
    GA -->|OIDC Token| WIFP
    WIFP -->|Validate| WIF
    WIF -->|Exchange| STS
    STS -->|Access Token| GCP[Google Cloud APIs]
    GCP -->|Push Image| AR
    GCP -->|Deploy| CR
    CR -->|Read Secret| SM
    SM -->|Credentials| DB
    API -->|Query| DB
    GHS -->|Configuration| GA
```

### CI/CD Pipeline Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GH as GitHub
    participant GHA as GitHub Actions
    participant WIF as Workload Identity
    participant GCP as Google Cloud
    participant AR as Artifact Registry
    participant CR as Cloud Run

    Dev->>GH: git push main
    GH->>GHA: Trigger Workflow

    Note over GHA: 1. Checkout Code
    Note over GHA: 2. Setup Python
    Note over GHA: 3. Run Tests (sqlite://)

    GHA->>WIF: Request OIDC Token
    WIF-->>GHA: OIDC Token
    GHA->>GCP: Authenticate with Token

    alt Tests Pass
        Note over GHA: 4. Build Docker Image
        GHA->>AR: Push Image (linux/amd64)
        Note over GHA: 5. Deploy to Cloud Run
        GCP->>CR: Deploy Container
        CR->>GCP: Service Running
    else Tests Fail
        GHA-->>Dev: Workflow Failed
    end
```

### IAM Permission Flow

```mermaid
graph LR
    subgraph "GitHub Actions"
        GHA[GitHub Actions<br/>Runner]
        OIDC[OIDC Token<br/>with claims]
    end

    subgraph "Workload Identity"
        WIFP[Provider<br/>github-actions]
        POOL[Pool<br/>github]
    end

    subgraph "Principal Binding"
        PB[IAM Policy<br/>Principal Binding]
    end

    subgraph "Roles"
        ARW[artifactregistry.writer]
        CRA[run.admin]
        SAU[iam.serviceAccountUser]
    end

    GHA -->|Generate| OIDC
    OIDC -->|Validate| WIFP
    WIFP -->|Map to| POOL
    POOL -->|Match| PB
    PB -->|Grant| ARW
    PB -->|Grant| CRA
    PB -->|Grant| SAU
```

---

## Components

### 1. GitHub Repository

- **Repository**: `godie007/fastapi-supabase-gcp-challenge`
- **Branch**: `main`
- **Contents**:
  - FastAPI application code
  - Dockerfile
  - GitHub Actions workflow
  - Tests

### 2. GitHub Actions

The CI/CD pipeline consists of two jobs:

#### Test Job
```yaml
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - name: Install dependencies
      run: pip install --no-cache-dir -r requirements.txt
    - name: Run pytest
      env:
        DATABASE_URL: sqlite://
      run: pytest app/tests -v
```

#### Deploy Job
```yaml
deploy:
  runs-on: ubuntu-latest
  needs: test
  if: github.ref == 'refs/heads/main'
  steps:
    - uses: actions/checkout@v4
    - id: auth
      uses: google-github-actions/auth@v2
      with:
        workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
        project_id: ${{ secrets.GCP_PROJECT_ID }}
    - name: Build and push image
    - name: Deploy to Cloud Run
```

---

## Google Cloud Platform Resources

### Project Information

| Property | Value |
|----------|-------|
| Project ID | `integral-vim-494001-v4` |
| Project Number | `395887947282` |
| Region | `us-central1` |

### Cloud Run Service

```yaml
Service Name: fastapi-users-api
URL: https://fastapi-users-api-395887947282.us-central1.run.app
Region: us-central1
Platform: managed
Port: 8080
Memory: 512Mi
CPU: 1
Max Instances: 10
Min Instances: 0
Concurrency: 80
Timeout: 300s
Ingress: all
Authentication: public (--allow-unauthenticated)
```

### Artifact Registry

```yaml
Repository: app-images
Location: us-central1
Format: Docker
URL: us-central1-docker.pkg.dev/integral-vim-494001-v4/app-images
```

### Image Tagging Strategy

```
us-central1-docker.pkg.dev/integral-vim-494001-v4/app-images/fastapi-users-api:{github.sha}
```

---

## Secrets Management

### Secret Manager

The application uses Secret Manager to store the database connection string.

#### Secret Configuration

| Property | Value |
|----------|-------|
| Secret Name | `fastapi-supabase-gcp-challenge` |
| Version | `latest` |
| Type | `String` |

#### Secret Value Format

```
postgresql+psycopg2://postgres:[password]@db.[project-ref].supabase.co:5432/postgres
```

#### Secret Access Policy

```bash
# Grant Cloud Run runtime SA access to the secret
gcloud secrets add-iam-policy-binding fastapi-supabase-gcp-challenge \
  --member="serviceAccount:395887947282-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project="integral-vim-494001-v4"
```

#### Passing Secret to Cloud Run

```yaml
- name: Deploy to Cloud Run
  run: |
    gcloud run deploy fastapi-users-api \
      --project="integral-vim-494001-v4" \
      --region="us-central1" \
      --image="us-central1-docker.pkg.dev/..." \
      --update-secrets=DATABASE_URL=fastapi-supabase-gcp-challenge:latest
```

---

## IAM and Security

### Service Accounts

| Name | Email | Purpose |
|------|-------|---------|
| GitHub Actions (WIF) | N/A (Federated Identity) | CI/CD Authentication |
| GitHub Actions Deploy | `github-actions-deploy@integral-vim-494001-v4.iam.gserviceaccount.com` | Local CLI builds (optional) |
| Cloud Run Runtime | `395887947282-compute@developer.gserviceaccount.com` | Running container instances |
| Cloud Build | `395887947282@cloudbuild.gserviceaccount.com` | Cloud Build trigger execution |

### IAM Roles

#### Workload Identity Principal (GitHub Actions)

The federated identity authenticates as:

```
principal://iam.googleapis.com/projects/395887947282/locations/global/workloadIdentityPools/github/subject/repo:godie007/fastapi-supabase-gcp-challenge:ref:refs/heads/main
```

Required roles:

| Role | Purpose |
|------|---------|
| `roles/artifactregistry.writer` | Push Docker images to Artifact Registry |
| `roles/run.admin` | Deploy and manage Cloud Run services |
| `roles/iam.serviceAccountUser` | Act as the runtime service account |
| `roles/iam.serviceAccountTokenCreator` | Create tokens (optional) |
| `roles/cloudbuild.builds.editor` | Run Cloud Build triggers |
| `roles/serviceusage.serviceUsageConsumer` | Use GCP APIs |
| `roles/storage.objectAdmin` | Access Cloud Storage |

#### Cloud Build Service Account

| Role | Purpose |
|------|---------|
| `roles/run.admin` | Deploy to Cloud Run |
| `roles/artifactregistry.writer` | Push images |
| `roles/iam.serviceAccountUser` | Use runtime SA |
| `roles/secretmanager.secretAccessor` | Read secrets |

#### Cloud Run Runtime Service Account

| Role | Purpose |
|------|---------|
| `roles/secretmanager.secretAccessor` | Read DATABASE_URL |

---

## Workload Identity Federation

### Overview

Workload Identity Federation allows GitHub Actions to authenticate to GCP without storing service account keys. Instead, GitHub's OIDC tokens are exchanged for GCP access tokens.

### Components

#### Workload Identity Pool

```yaml
Pool ID: github
Location: global
Project: 395887947282
State: ACTIVE
```

#### OIDC Provider

```yaml
Provider ID: github-actions
Pool: github
Issuer: https://token.actions.githubusercontent.com
State: ACTIVE
Attribute Mapping:
  google.subject = assertion.sub
  attribute.repository = assertion.repository
  attribute.repository_owner = assertion.repository_owner
  attribute.actor = assertion.actor
  attribute.ref = assertion.ref
Attribute Condition: assertion.sub != ''
```

### Provider Resource Name

```
projects/395887947282/locations/global/workloadIdentityPools/github/providers/github-actions
```

### GitHub OIDC Token Claims

The GitHub Actions OIDC token contains:

```json
{
  "sub": "repo:godie007/fastapi-supabase-gcp-challenge:ref:refs/heads/main",
  "repository": "godie007/fastapi-supabase-gcp-challenge",
  "repository_owner": "godie007",
  "actor": "godie007",
  "ref": "refs/heads/main",
  "iss": "https://token.actions.githubusercontent.com"
}
```

### Mapping to GCP Principal

| GitHub Claim | GCP Mapping |
|-------------|-------------|
| `sub` | `google.subject` |
| `repository` | `attribute.repository` |
| `repository_owner` | `attribute.repository_owner` |

---

## GitHub Secrets Configuration

### Required Secrets

Navigate to: **GitHub → Repository → Settings → Secrets and variables → Actions**

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `GCP_PROJECT_ID` | `integral-vim-494001-v4` | GCP Project ID |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/395887947282/locations/global/workloadIdentityPools/github/providers/github-actions` | Full WIF provider resource name |

### Optional Secrets

| Secret Name | Default | Description |
|------------|---------|-------------|
| `GCP_REGION` | `us-central1` | Cloud Run region |
| `GCP_SERVICE_NAME` | `fastapi-users-api` | Cloud Run service name |
| `GCP_WIF_SERVICE_ACCOUNT` | (email) | Service account for impersonation (not used in current workflow) |

### Workflow Secret Usage

```yaml
- id: auth
  uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
    project_id: ${{ secrets.GCP_PROJECT_ID }}
```

---

## Database Schema

### Users Table

```sql
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

### Supabase Connection

- **Host**: `db.[project-ref].supabase.co`
- **Port**: `5432`
- **Database**: `postgres`
- **Connection Pooler**: Session mode (recommended)

---

## API Endpoints

| Method | Endpoint | Description | Status Codes |
|--------|----------|-------------|--------------|
| POST | `/users/` | Create user | 201, 409, 422 |
| GET | `/users/` | List users (paginated) | 200 |
| GET | `/users/{id}` | Get user by UUID | 200, 404, 422 |
| PATCH | `/users/{id}` | Partial update user | 200, 404, 409, 422 |
| DELETE | `/users/{id}` | Delete user | 204, 404, 422 |
| GET | `/docs` | Swagger UI | 200 |
| GET | `/redoc` | ReDoc | 200 |

### Example Request

**POST `/users/`**
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

### Testing the API

```bash
# Get service URL
SERVICE_URL="https://fastapi-users-api-395887947282.us-central1.run.app"

# Create user
curl -X POST "$SERVICE_URL/users/" \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","first_name":"Test","last_name":"User","role":"user","active":true}'

# List users
curl "$SERVICE_URL/users/"
```

---

## Troubleshooting

### Common Errors and Solutions

#### 1. Permission Denied: artifactregistry.repositories.uploadArtifacts

**Cause**: WIF principal lacks Artifact Registry writer role.

**Solution**:
```bash
gcloud projects add-iam-policy-binding integral-vim-494001-v4 \
  --member="principal://iam.googleapis.com/projects/395887947282/locations/global/workloadIdentityPools/github/subject/repo:godie007/fastapi-supabase-gcp-challenge:ref:refs/heads/main" \
  --role="roles/artifactregistry.writer"
```

#### 2. Permission Denied: iam.serviceaccounts.actAs

**Cause**: Principal cannot act as Cloud Run runtime service account.

**Solution**:
```bash
gcloud projects add-iam-policy-binding integral-vim-494001-v4 \
  --member="principal://iam.googleapis.com/.../subject/repo:godie007/fastapi-supabase-gcp-challenge:ref:refs/heads/main" \
  --role="roles/iam.serviceAccountUser"
```

#### 3. The given credential is rejected by the attribute condition

**Cause**: WIF provider attribute condition is too strict.

**Solution**:
```bash
gcloud iam workload-identity-pools providers update-oidc github-actions \
  --project="integral-vim-494001-v4" \
  --location="global" \
  --workload-identity-pool="github" \
  --attribute-condition="assertion.sub != ''"
```

#### 4. Docker build fails with "Password required" for Artifact Registry

**Cause**: Docker login using wrong credentials or expired token.

**Solution**: Ensure the access token is obtained fresh:
```yaml
- name: Get GCP Access Token
  run: |
    ACCESS_TOKEN=$(gcloud auth print-access-token)
    echo "ACCESS_TOKEN=$ACCESS_TOKEN" >> $GITHUB_ENV
```

---

## Deployment Checklist

### Pre-deployment

- [ ] GitHub secrets configured (`GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`)
- [ ] GCP APIs enabled (run, artifactregistry, cloudbuild, iam, secretmanager)
- [ ] Artifact Registry repository created (`app-images`)
- [ ] Secret Manager secret created with DATABASE_URL
- [ ] IAM roles assigned to WIF principal

### Deployment

- [ ] Tests pass on all branches
- [ ] Push to `main` triggers deployment
- [ ] Docker image built and pushed to Artifact Registry
- [ ] Cloud Run service deployed successfully
- [ ] Service accessible via URL

### Post-deployment

- [ ] Verify service health: `curl https://fastapi-users-api-...run.app/docs`
- [ ] Check Cloud Run logs in GCP Console
- [ ] Confirm secret is mounted correctly

---

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [Artifact Registry Documentation](https://cloud.google.com/artifact-registry/docs)