# Secrets Management Documentation

This document explains how secrets are managed in the application using Google Cloud Secret Manager and GitHub Secrets.

---

## Overview

```mermaid
graph TB
    subgraph "GitHub"
        GHS[GitHub Secrets]
        GHA[GitHub Actions]
    end

    subgraph "Secret Manager"
        SM[Secret Manager]
        DB_URL[DATABASE_URL<br/>fastapi-supabase-gcp-challenge]
    end

    subgraph "Cloud Run"
        CR[Cloud Run<br/>Container]
        ENV[Environment<br/>Variables]
    end

    subgraph "PostgreSQL"
        DB[(PostgreSQL<br/>Supabase)]
    end

    GHS -->|Configure| GHA
    GHA -->|Deploy with<br/>--update-secrets| CR
    CR -->|Mount| DB_URL
    DB_URL -->|Connect| DB
```

---

## GitHub Secrets

### Required Secrets

Navigate to: **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value | Required | Description |
|-------------|-------|----------|-------------|
| `GCP_PROJECT_ID` | `integral-vim-494001-v4` | Yes | GCP Project ID |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/395887947282/locations/global/workloadIdentityPools/github/providers/github-actions` | Yes | WIF Provider resource name |

### Optional Secrets

| Secret Name | Default | Required | Description |
|-------------|---------|----------|-------------|
| `GCP_REGION` | `us-central1` | No | Cloud Run region |
| `GCP_SERVICE_NAME` | `fastapi-users-api` | No | Cloud Run service name |

### Secret Usage in Workflow

```yaml
# Authentication
- id: auth
  uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
    project_id: ${{ secrets.GCP_PROJECT_ID }}

# Deployment with secrets
- name: Deploy to Cloud Run
  env:
    PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
    REGION: ${{ vars.GCP_REGION || 'us-central1' }}
    SERVICE_NAME: ${{ vars.GCP_SERVICE_NAME || 'fastapi-users-api' }}
  run: |
    gcloud run deploy "${SERVICE_NAME}" \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --update-secrets=DATABASE_URL=fastapi-supabase-gcp-challenge:latest
```

---

## Google Cloud Secret Manager

### Secret Configuration

| Property | Value |
|----------|-------|
| Secret Name | `fastapi-supabase-gcp-challenge` |
| Project | `integral-vim-494001-v4` |
| Region | `global` |
| Type | `String` |
| Labels | (none) |

### Create Secret

```bash
# Create the secret
gcloud secrets create fastapi-supabase-gcp-challenge \
  --replication-policy=automatic \
  --project="integral-vim-494001-v4"

# Add the secret version
echo "postgresql+psycopg2://postgres:YOUR_PASSWORD@db.your-project.supabase.co:5432/postgres" | \
gcloud secrets versions add fastapi-supabase-gcp-challenge \
  --data-file=- \
  --project="integral-vim-494001-v4"
```

### View Secret Details

```bash
# Describe the secret
gcloud secrets describe fastapi-supabase-gcp-challenge \
  --project="integral-vim-494001-v4"

# List secret versions
gcloud secrets versions list fastapi-supabase-gcp-challenge \
  --project="integral-vim-494001-v4"
```

### Access Policy

Grant access to service accounts that need to read the secret:

```bash
# Grant to Cloud Run runtime SA
gcloud secrets add-iam-policy-binding fastapi-supabase-gcp-challenge \
  --member="serviceAccount:395887947282-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project="integral-vim-494001-v4"

# Grant to Cloud Build SA (if using triggers)
gcloud secrets add-iam-policy-binding fastapi-supabase-gcp-challenge \
  --member="serviceAccount:395887947282@cloudbuild.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project="integral-vim-494001-v4"
```

### View Access Policy

```bash
gcloud secrets get-iam-policy fastapi-supabase-gcp-challenge \
  --project="integral-vim-494001-v4"
```

---

## Passing Secrets to Cloud Run

### Method 1: Using `--update-secrets` Flag

```bash
gcloud run deploy fastapi-users-api \
  --project="integral-vim-494001-v4" \
  --region="us-central1" \
  --image="us-central1-docker.pkg.dev/integral-vim-494001-v4/app-images/fastapi-users-api:latest" \
  --update-secrets=DATABASE_URL=fastapi-supabase-gcp-challenge:latest
```

### Method 2: Mount as Volume

```bash
gcloud run deploy fastapi-users-api \
  --project="integral-vim-494001-v4" \
  --region="us-central1" \
  --image="..." \
  --secret-envs=DATABASE_URL=projects/integral-vim-494001-v4/secrets/fastapi-supabase-gcp-challenge/versions/latest
```

### Method 3: From GitHub Actions (Current Implementation)

The workflow uses the `--update-secrets` approach in the deploy step:

```yaml
- name: Deploy to Cloud Run
  env:
    PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
    REGION: ${{ vars.GCP_REGION || 'us-central1' }}
    SERVICE_NAME: ${{ vars.GCP_SERVICE_NAME || 'fastapi-users-api' }}
    IMAGE: us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/app-images/fastapi-users-api:${{ github.sha }}
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
      --allow-unauthenticated \
      --update-secrets=DATABASE_URL=fastapi-supabase-gcp-challenge:latest
```

---

## Rotating Secrets

### Manual Rotation

```bash
# Add new version
echo "postgresql+psycopg2://postgres:NEW_PASSWORD@db.your-project.supabase.co:5432/postgres" | \
gcloud secrets versions add fastapi-supabase-gcp-challenge \
  --data-file=- \
  --project="integral-vim-494001-v4"

# Redeploy to use new version
gcloud run deploy fastapi-users-api \
  --project="integral-vim-494001-v4" \
  --region="us-central1" \
  --update-secrets=DATABASE_URL=fastapi-supabase-gcp-challenge:latest
```

### Using Specific Version

```bash
# Use specific version instead of latest
gcloud run deploy fastapi-users-api \
  --project="integral-vim-494001-v4" \
  --region="us-central1" \
  --update-secrets=DATABASE_URL=fastapi-supabase-gcp-challenge:1
```

---

## Secret in Application

### Environment Variable Access

The application reads the DATABASE_URL as an environment variable:

```python
# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str

    class Config:
        env_file = ".env"
```

### Container Startup

Cloud Run mounts the secret as an environment variable:

```yaml
# Cloud Run service configuration
env:
- name: DATABASE_URL
  valueSource:
    secretKeyRef:
      secret: fastapi-supabase-gcp-challenge
      version: latest
```

---

## Security Best Practices

### 1. Use Automatic Replication

```bash
gcloud secrets create "secret-name" \
  --replication-policy=automatic
```

### 2. Enable Secret Rotation

```bash
# Enable automatic rotation (if supported)
gcloud secrets update "secret-name" \
  --rotation-period=60d \
  --next-rotation-time=2025-01-01T00:00:00Z
```

### 3. Audit Access

```bash
# Cloud Audit Logs
gcloud logging read "protoPayload.methodName=google.cloud.secretsmanager.v1.AccessSecretVersion" \
  --project="integral-vim-494001-v4"
```

### 4. Use Labels

```bash
gcloud secrets create "secret-name" \
  --labels="environment=production,application=fastapi"
```

---

## Troubleshooting

### Secret Not Found

**Error**: `ERROR: (gcloud.run.deploy) NOT_FOUND: Secret 'fastapi-supabase-gcp-challenge' not found in project '...'`

**Solution**:
```bash
# Verify secret exists
gcloud secrets describe fastapi-supabase-gcp-challenge \
  --project="your-project"
```

### Permission Denied

**Error**: `Permission 'secretmanager.versions.access' denied on resource`

**Solution**:
```bash
# Add IAM policy binding
gcloud secrets add-iam-policy-binding "secret-name" \
  --member="serviceAccount:your-sa@project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Secret Value Not Updated

**Error**: Container still uses old secret value after update

**Solution**: Redeploy to trigger secret refresh:
```bash
gcloud run deploy service-name \
  --project="project-id" \
  --region="region" \
  --update-secrets=SECRET_NAME=secret-name:latest
```

---

## Summary

| Secret | Location | Purpose |
|--------|----------|---------|
| `GCP_PROJECT_ID` | GitHub Secrets | GCP project identification |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | GitHub Secrets | WIF authentication |
| `DATABASE_URL` | Secret Manager | PostgreSQL connection string |
| `GCP_REGION` | GitHub Variables | Cloud Run region |
| `GCP_SERVICE_NAME` | GitHub Variables | Cloud Run service name |