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

# Provider attribute condition (CEL must reference assertion.* ; literal `true` is rejected by GCP).
# - Default: admit GitHub tokens that include a non-empty `sub` (always present on Actions OIDC).
# - Strict CEL (optional): export WIF_STRICT_ATTRIBUTE_CONDITION=1 before running this script.
# - Override entirely: export WIF_PROVIDER_ATTRIBUTE_CONDITION='your cel expression'
if [[ -n "${WIF_PROVIDER_ATTRIBUTE_CONDITION:-}" ]]; then
  readonly WIF_ATTR_CONDITION="${WIF_PROVIDER_ATTRIBUTE_CONDITION}"
elif [[ "${WIF_STRICT_ATTRIBUTE_CONDITION:-0}" == "1" ]]; then
  readonly WIF_ATTR_CONDITION="(assertion.sub.startsWith('repo:${GITHUB_REPO}:')) || (assertion.repository == '${GITHUB_REPO}')"
else
  readonly WIF_ATTR_CONDITION="assertion.sub != ''"
fi

PROJECT_NUMBER="$(
  gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)'
)"

POOL_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"
GITHUB_OWNER="${GITHUB_REPO%%/*}"
PRINCIPAL_SET_REPOSITORY="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository/${GITHUB_REPO}"
PRINCIPAL_SET_REPOSITORY_OWNER="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository_owner/${GITHUB_OWNER}"

SA_EMAIL="${SA_ACCOUNT_ID}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==> Project: ${PROJECT_ID} (${PROJECT_NUMBER})"
echo "==> GitHub repo (OIDC repository claim): ${GITHUB_REPO}"
echo "==> GitHub owner (repository_owner claim): ${GITHUB_OWNER}"
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
    --attribute-condition="${WIF_ATTR_CONDITION}"
else
  echo "    (provider already exists — will sync attribute condition)"
fi

gcloud iam workload-identity-pools providers update-oidc "${PROVIDER_ID}" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="${POOL_ID}" \
  --attribute-condition="${WIF_ATTR_CONDITION}"

echo "==> Service account"
if ! gcloud iam service-accounts describe "${SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  &>/dev/null; then
  gcloud iam service-accounts create "${SA_ACCOUNT_ID}" \
    --project="${PROJECT_ID}" \
    --display-name="GitHub Actions → Cloud Build submit"
fi

echo "==> IAM: submit Cloud Build jobs (legacy SA — optional for non-GitHub clients)"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudbuild.builds.editor"

echo "==> IAM: GitHub federation → project (Cloud Build + Service Usage + Storage for submit tarball)"
# builds.submit uploads sources to the project's default Cloud Build bucket; callers need
# serviceusage.services.use and object access on that bucket (project-level storage.objectUser covers it).
for ROLE in \
  roles/cloudbuild.builds.editor \
  roles/serviceusage.serviceUsageConsumer \
  roles/storage.objectUser; do
  for MEMBER in "${PRINCIPAL_SET_REPOSITORY}" "${PRINCIPAL_SET_REPOSITORY_OWNER}"; do
    if [[ "${MEMBER}" == "${PRINCIPAL_SET_REPOSITORY_OWNER}" ]] && [[ "${WIF_SKIP_REPOSITORY_OWNER_BIND:-0}" == "1" ]]; then
      echo "    skip ${ROLE} for repository_owner (WIF_SKIP_REPOSITORY_OWNER_BIND=1)"
      continue
    fi
    echo "    ${ROLE} ← ${MEMBER}"
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="${MEMBER}" \
      --role="${ROLE}"
  done
done

echo "==> IAM: GitHub federation → service account (optional; SA impersonation not required for Actions)"
for MEMBER in "${PRINCIPAL_SET_REPOSITORY}" "${PRINCIPAL_SET_REPOSITORY_OWNER}"; do
  if [[ "${MEMBER}" == "${PRINCIPAL_SET_REPOSITORY_OWNER}" ]] && [[ "${WIF_SKIP_REPOSITORY_OWNER_BIND:-0}" == "1" ]]; then
    echo "    skip repository_owner principal (WIF_SKIP_REPOSITORY_OWNER_BIND=1)"
    continue
  fi
  echo "    ${MEMBER}"
  for ROLE in roles/iam.workloadIdentityUser roles/iam.serviceAccountTokenCreator; do
    gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
      --project="${PROJECT_ID}" \
      --role="${ROLE}" \
      --member="${MEMBER}"
  done
done

PROVIDER_NAME="$(
  gcloud iam workload-identity-pools providers describe "${PROVIDER_ID}" \
    --project="${PROJECT_ID}" \
    --location="global" \
    --workload-identity-pool="${POOL_ID}" \
    --format='value(name)'
)"

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Done. Add these GitHub Actions credentials (same names as Secrets or Variables):"
echo "  Settings → Secrets and variables → Actions"
echo "  (Recommended: Repository secrets — workflow uses secrets first, then variables.)"
echo
echo "  GCP_PROJECT_ID"
echo "  ${PROJECT_ID}"
echo
echo "  GCP_WORKLOAD_IDENTITY_PROVIDER"
echo "  ${PROVIDER_NAME}"
echo
echo "  (Optional) GCP_WIF_SERVICE_ACCOUNT — legacy SA impersonation; Actions deploy does not use it."
echo "  ${SA_EMAIL}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
echo "Notes:"
echo "  • GitHub Actions deploy: direct WIF + project roles on principalSet(s):"
echo "      roles/cloudbuild.builds.editor, roles/serviceusage.serviceUsageConsumer, roles/storage.objectUser"
echo "      attribute.repository/${GITHUB_REPO}, attribute.repository_owner/${GITHUB_OWNER}"
echo "  • WIF provider attribute condition: ${WIF_ATTR_CONDITION}"
echo "    (override: export WIF_PROVIDER_ATTRIBUTE_CONDITION='CEL'; strict: export WIF_STRICT_ATTRIBUTE_CONDITION=1)"
echo "  • SA IAM bindings remain for optional impersonation flows (skip SA creation later if unused)."
echo "  • Cloud Build default SA still runs steps; keep Run / Artifact Registry / Secret IAM as in README."
echo "  • To inspect JWT claims from Actions: run workflow “Debug GitHub OIDC claims” (workflow_dispatch)."
echo
