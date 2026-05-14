# IAM and CI/CD Setup Documentation

This document describes the IAM roles, service accounts, and permissions required for the GitHub Actions CI/CD pipeline to deploy to Google Cloud Run.

---

## Overview

The CI/CD pipeline uses **GitHub Actions** with **Workload Identity Federation** (WIF) to authenticate to Google Cloud without storing service account keys. The pipeline:

1. Runs pytest tests on every push/PR
2. Builds a Docker image on pushes to `main`
3. Pushes the image to **Artifact Registry**
4. Deploys to **Cloud Run**

---

## Service Accounts

### 1. GitHub Actions Workload Identity (No SA Required)

The workflow uses **direct Workload Identity Federation** — no service account is created or used for authentication. The GitHub OIDC token is exchanged directly for GCP credentials.

### 2. GitHub Actions Deploy (Optional, for local CLI)

If you need to run `gcloud builds submit` locally, a service account exists:

- **Email**: `github-actions-deploy@integral-vim-494001-v4.iam.gserviceaccount.com`
- **Purpose**: Manual CLI builds and local development
- **Roles assigned**: `roles/cloudbuild.builds.editor`, `roles/serviceusage.serviceUsageConsumer`, `roles/storage.objectAdmin`

### 3. Cloud Run Runtime (Default Compute SA)

- **Email**: `395887947282-compute@developer.gserviceaccount.com`
- **Purpose**: Executes the Cloud Run service containers
- **Used by**: Cloud Run service runtime

### 4. Cloud Build Service Account

- **Email**: `395887947282@cloudbuild.gserviceaccount.com`
- **Purpose**: Executes Cloud Build steps (if using Cloud Build triggers)
- **Roles**: `roles/run.admin`, `roles/artifactregistry.writer`, `roles/iam.serviceAccountUser`

---

## IAM Roles and Permissions

### For GitHub Actions (Workload Identity Federation Principal)

The federated identity uses this principal format:

```
principal://iam.googleapis.com/projects/395887947282/locations/global/workloadIdentityPools/github/subject/repo:godie007/fastapi-supabase-gcp-challenge:ref:refs/heads/main
```

Required project-level roles:

| Role | Purpose |
|------|---------|
| `roles/artifactregistry.writer` | Push Docker images to Artifact Registry |
| `roles/run.admin` | Deploy and update Cloud Run services |
| `roles/iam.serviceAccountUser` | Act as the Cloud Run runtime service account (required for deployment) |
| `roles/iam.serviceAccountTokenCreator` | Impersonate service accounts (if using SA impersonation) |
| `roles/cloudbuild.builds.editor` | Run Cloud Build triggers (if using triggers) |
| `roles/serviceusage.serviceUsageConsumer` | Use GCP APIs (required for builds/deployments) |
| `roles/storage.objectAdmin` | Access Cloud Storage buckets (for build artifacts) |

### For Cloud Build Service Account

| Role | Purpose |
|------|---------|
| `roles/run.admin` | Deploy to Cloud Run |
| `roles/artifactregistry.writer` | Push images |
| `roles/iam.serviceAccountUser` | Use the runtime service account |
| `roles/secretmanager.secretAccessor` | Read DATABASE_URL from Secret Manager |

### For Cloud Run Runtime (Default Compute SA)

| Role | Purpose |
|------|---------|
| `roles/secretmanager.secretAccessor` | Read DATABASE_URL from Secret Manager |

---

## Workload Identity Federation Setup

### Components Created

1. **Workload Identity Pool**
   - ID: `github`
   - Location: `global`
   - Project: `395887947282`

2. **OIDC Provider**
   - ID: `github-actions`
   - Issuer: `https://token.actions.githubusercontent.com`
   - Attribute mapping:
     ```
     google.subject = assertion.sub
     attribute.repository = assertion.repository
     attribute.repository_owner = assertion.repository_owner
     attribute.actor = assertion.actor
     attribute.ref = assertion.ref
     ```

3. **Attribute Condition**
   ```
   assertion.sub != ''
   ```

### Provider Resource Name

```
projects/395887947282/locations/global/workloadIdentityPools/github/providers/github-actions
```

This value is stored in GitHub secrets as `GCP_WORKLOAD_IDENTITY_PROVIDER`.

---

## GitHub Repository Secrets

Configure these in **GitHub → Settings → Secrets and variables → Actions**:

| Secret Name | Value | Required |
|-------------|-------|----------|
| `GCP_PROJECT_ID` | `integral-vim-494001-v4` | Yes |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/395887947282/locations/global/workloadIdentityPools/github/providers/github-actions` | Yes |
| `GCP_WIF_SERVICE_ACCOUNT` | (Optional) Email of SA for impersonation | No |

### Optional Variables

| Variable Name | Default Value | Description |
|--------------|---------------|-------------|
| `GCP_REGION` | `us-central1` | Cloud Run region |
| `GCP_SERVICE_NAME` | `fastapi-users-api` | Cloud Run service name |

---

## GitHub Actions Workflow

The workflow file is `.github/workflows/ci-cd-cloud-run.yml`.

### Job: Test

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

### Job: Deploy

```yaml
deploy:
  runs-on: ubuntu-latest
  needs: test
  if: github.ref == 'refs/heads/main' && (github.event_name == 'push' || github.event_name == 'workflow_dispatch')
  steps:
    - uses: actions/checkout@v4
    - id: auth
      uses: google-github-actions/auth@v2
      with:
        workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
        project_id: ${{ secrets.GCP_PROJECT_ID }}
        export_environment_variables: true
        access_token_lifetime: 3600s
        access_token_scopes: https://www.googleapis.com/auth/cloud-platform
    - name: Set up Docker
      uses: docker/setup-buildx-action@v3
    - name: Get GCP Access Token
      run: |
        ACCESS_TOKEN=$(gcloud auth print-access-token)
        echo "::add-mask::$ACCESS_TOKEN"
        echo "ACCESS_TOKEN=$ACCESS_TOKEN" >> $GITHUB_ENV
    - name: Authenticate to Artifact Registry
      uses: docker/login-action@v3
      with:
        registry: us-central1-docker.pkg.dev
        username: oauth2accesstoken
        password: ${{ env.ACCESS_TOKEN }}
    - name: Build and push image
      uses: docker/build-push-action@v6
      with:
        context: .
        push: true
        platforms: linux/amd64
        tags: us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/app-images/fastapi-users-api:${{ github.sha }}
    - name: Deploy to Cloud Run
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

---

## GCP Resources Required

### APIs Enabled

- `run.googleapis.com` (Cloud Run)
- `artifactregistry.googleapis.com` (Artifact Registry)
- `cloudbuild.googleapis.com` (Cloud Build)
- `iam.googleapis.com` (IAM)
- `secretmanager.googleapis.com` (Secret Manager)
- `storage.googleapis.com` (Cloud Storage)

### Artifact Registry Repository

- **Name**: `app-images`
- **Location**: `us-central1`
- **Format**: Docker
- **URL**: `us-central1-docker.pkg.dev/integral-vim-494001-v4/app-images`

### Cloud Run Service

- **Name**: `fastapi-users-api`
- **Region**: `us-central1`
- **URL**: `https://fastapi-users-api-395887947282.us-central1.run.app`
- **Port**: `8080`
- **Memory**: `512Mi`
- **CPU**: `1`
- **Max Instances**: `10`
- **Concurrency**: `80`

---

## Command Reference: Applying IAM Permissions

### Add roles to the Workload Identity principal (main branch)

```bash
PROJECT_ID="integral-vim-494001-v4"
PROJECT_NUMBER="395887947282"
POOL_PATH="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github"
PRINCIPAL="principal://${POOL_PATH}/subject/repo:godie007/fastapi-supabase-gcp-challenge:ref:refs/heads/main"

# Artifact Registry writer
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="$PRINCIPAL" \
  --role="roles/artifactregistry.writer"

# Cloud Run admin
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="$PRINCIPAL" \
  --role="roles/run.admin"

# Service Account User
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="$PRINCIPAL" \
  --role="roles/iam.serviceAccountUser"

# Token Creator (optional, for SA impersonation)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="$PRINCIPAL" \
  --role="roles/iam.serviceAccountTokenCreator"

# Cloud Build editor (if using triggers)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="$PRINCIPAL" \
  --role="roles/cloudbuild.builds.editor"

# Service Usage Consumer
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="$PRINCIPAL" \
  --role="roles/serviceusage.serviceUsageConsumer"

# Storage Object Admin
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="$PRINCIPAL" \
  --role="roles/storage.objectAdmin"
```

### Add roles to the Cloud Build service account

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:395887947282@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:395887947282@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:395887947282@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

### Grant secret access to Cloud Run runtime SA

```bash
SECRET_NAME="fastapi-supabase-gcp-challenge"
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --project="$PROJECT_ID" \
  --member="serviceAccount:395887947282-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Testing the Pipeline

### Run tests locally

```bash
pytest app/tests -v
```

### Trigger a workflow

Push to main branch or manually trigger from GitHub Actions UI:

```bash
git push origin main
```

### Check workflow status

```bash
gh run list --limit 5
gh run view <run-id>
```

### Verify Cloud Run service

```bash
gcloud run services describe fastapi-users-api \
  --region us-central1 \
  --platform managed
```

---

## Troubleshooting

### Error: Permission 'artifactregistry.repositories.uploadArtifacts' denied

**Cause**: The Workload Identity principal lacks `roles/artifactregistry.writer`.

**Fix**: Run the IAM binding commands above for the principal.

### Error: Permission 'iam.serviceaccounts.actAs' denied

**Cause**: The principal cannot act as the Cloud Run runtime service account.

**Fix**: Add `roles/iam.serviceAccountUser` to the principal.

### Error: The given credential is rejected by the attribute condition

**Cause**: The WIF provider's attribute condition is too strict.

**Fix**: Update the provider condition:

```bash
gcloud iam workload-identity-pools providers update-oidc github-actions \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="github" \
  --attribute-condition="assertion.sub != ''"
```

---

## Summary

| Component | Principal / SA | Roles |
|-----------|---------------|-------|
| GitHub Actions (WIF) | Principal: `subject/repo:...:ref:refs/heads/main` | `artifactregistry.writer`, `run.admin`, `iam.serviceAccountUser` |
| Cloud Build | `395887947282@cloudbuild.gserviceaccount.com` | `run.admin`, `artifactregistry.writer`, `iam.serviceAccountUser` |
| Cloud Run Runtime | `395887947282-compute@developer.gserviceaccount.com` | `secretmanager.secretAccessor` |