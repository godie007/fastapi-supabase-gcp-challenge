#!/usr/bin/env bash
# Creates Workload Identity Federation (GitHub OIDC) + a deploy service account so
# `.github/workflows/ci-cd-cloud-run.yml` can run `gcloud builds submit`.
#
# Prerequisites: gcloud logged in, IAM permissions (Workload Identity Pool Admin,
# Service Account Admin, Project IAM Admin, Service Usage Admin).
#
# Usage:
#   ./scripts/setup-github-actions-wif.sh GITHUB_OWNER/GITHUB_REPO_NAME [GCP_PROJECT_ID]
#
# Example:
#   ./scripts/setup-github-actions-wif.sh acme-corp/fastapi-supabase-gcp-challenge
#   ./scripts/setup-github-actions-wif.sh acme-corp/fastapi-supabase-gcp-challenge integral-vim-494001-v4

set -euo pipefail

readonly DEFAULT_PROJECT_ID="${GCP_PROJECT_ID:-integral-vim-494001-v4}"
readonly POOL_ID="${WIF_POOL_ID:-github}"
readonly PROVIDER_ID="${WIF_PROVIDER_ID:-github-actions}"
readonly SA_ACCOUNT_ID="${WIF_SA_ACCOUNT_ID:-github-actions-deploy}"

usage() {
  echo "Usage: $0 GITHUB_OWNER/GITHUB_REPO_NAME [GCP_PROJECT_ID]" >&2
  echo "  GCP_PROJECT_ID defaults to ${DEFAULT_PROJECT_ID} or env GCP_PROJECT_ID." >&2
  exit 1
}

[[ ${1:-} ]] || usage
[[ "$1" == *"/"* ]] || usage

GITHUB_REPO="$1"
GITHUB_OWNER="${GITHUB_REPO%%/*}"
PROJECT_ID="${2:-$DEFAULT_PROJECT_ID}"

case "${GITHUB_REPO}" in
  */*/*)
    echo "Invalid repo slug: use exactly owner/name with a single slash (e.g. my-org/my-repo)." >&2
    exit 1
    ;;
  */*) ;;
  *)
    echo "Invalid repo slug: use owner/name (e.g. my-org/my-repo)." >&2
    exit 1
    ;;
esac

PROJECT_NUMBER="$(
  gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)'
)"

POOL_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"
PRINCIPAL_SET_MEMBER="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository/${GITHUB_REPO}"

SA_EMAIL="${SA_ACCOUNT_ID}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==> Project: ${PROJECT_ID} (${PROJECT_NUMBER})"
echo "==> GitHub repo (OIDC repository claim): ${GITHUB_REPO}"
echo "==> Pool / provider: ${POOL_ID} / ${PROVIDER_ID}"
echo "==> Service account: ${SA_EMAIL}"
echo

echo "==> Enabling APIs (idempotent)"
gcloud services enable \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  --project="${PROJECT_ID}"

echo "==> Workload Identity Pool"
if ! gcloud iam workload-identity-pools describe "${POOL_ID}" \
  --project="${PROJECT_ID}" \
  --location="global" \
  &>/dev/null; then
  gcloud iam workload-identity-pools create "${POOL_ID}" \
    --project="${PROJECT_ID}" \
    --location="global" \
    --display-name="GitHub Actions (${POOL_ID})"
fi

echo "==> OIDC provider (GitHub Actions)"
if ! gcloud iam workload-identity-pools providers describe "${PROVIDER_ID}" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="${POOL_ID}" \
  &>/dev/null; then
  gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_ID}" \
    --project="${PROJECT_ID}" \
    --location="global" \
    --workload-identity-pool="${POOL_ID}" \
    --display-name="GitHub Actions OIDC" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository_owner == '${GITHUB_OWNER}'"
else
  echo "    (provider already exists — skipping create; update mappings/conditions in Console if needed)"
fi

echo "==> Service account"
if ! gcloud iam service-accounts describe "${SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  &>/dev/null; then
  gcloud iam service-accounts create "${SA_ACCOUNT_ID}" \
    --project="${PROJECT_ID}" \
    --display-name="GitHub Actions → Cloud Build submit"
fi

echo "==> IAM: submit Cloud Build jobs"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudbuild.builds.editor"

echo "==> IAM: impersonate service account from GitHub (${GITHUB_REPO})"
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="${PRINCIPAL_SET_MEMBER}"

PROVIDER_NAME="$(
  gcloud iam workload-identity-pools providers describe "${PROVIDER_ID}" \
    --project="${PROJECT_ID}" \
    --location="global" \
    --workload-identity-pool="${POOL_ID}" \
    --format='value(name)'
)"

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Done. Add these GitHub Actions repository Variables:"
echo "  Settings → Secrets and variables → Actions → Variables"
echo
echo "  GCP_PROJECT_ID"
echo "  ${PROJECT_ID}"
echo
echo "  GCP_WORKLOAD_IDENTITY_PROVIDER"
echo "  ${PROVIDER_NAME}"
echo
echo "  GCP_WIF_SERVICE_ACCOUNT"
echo "  ${SA_EMAIL}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
echo "Notes:"
echo "  • GitHub owner in tokens must match attribute condition: '${GITHUB_OWNER}'."
echo "  • Cloud Build default SA still runs steps; keep Run / Artifact Registry / Secret IAM as in README."
echo
