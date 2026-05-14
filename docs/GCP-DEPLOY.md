# Despliegue en Google Cloud Platform (resumen)

Guía rápida en español. Los detalles técnicos, diagramas y valores concretos de servicio están en [**CLOUD-RUN.md**](CLOUD-RUN.md), [**IAM-SETUP.md**](IAM-SETUP.md), [**SECRETS-MANAGEMENT.md**](SECRETS-MANAGEMENT.md) y [**CICD-WORKFLOW.md**](CICD-WORKFLOW.md).

---

## Qué hay desplegado (patrón)

1. **`cloudbuild.yaml`**: ejecuta **tests** → **build** Docker (`linux/amd64`) → **push** Artifact Registry → **`gcloud run deploy`**.
2. La app en Cloud Run necesita **`DATABASE_URL`** como **referencia de Secret Manager** (`--set-secrets` en substituciones de build).
3. GitHub Actions (opcional) repite una variante pipeline: PR/push ejecutan pytest; **`main`** despliegue tras tests.

---

## Checklist antes del primer deploy

- [ ] **APIs** habilitadas en el proyecto: **Cloud Run**, **Artifact Registry**, **Cloud Build**, **Secret Manager**.
- [ ] **Repositorio Docker** en Artifact Registry (nombre alineado con `_AR_REPOSITORY` en `cloudbuild.yaml`).
- [ ] Secreto en **Secret Manager** con la cadena Postgres (`DATABASE_URL` completa tipo `postgresql+psycopg2://…`).
- [ ] Cuenta de servicio de **Cloud Build** con permiso para:
  - publicar imagen (**Artifact Registry Writer**),
  - desplegar Cloud Run (**Run Admin**) y usar cuenta de ejecución del servicio (**Service Account User**),
  - leer el secreto (**Secret Accessor** sobre el recurso correspondiente).
- [ ] Opcional: GitHub configurado con **Workload Identity Federation** (`GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`) para el job de deploy en `main`.

---

## Ejecución del pipeline desde tu máquina

```bash
export PROJECT_ID=tu-proyecto

gcloud builds submit \
  --project="$PROJECT_ID" \
  --config cloudbuild.yaml \
  --substitutions=SHORT_SHA="$(git rev-parse --short HEAD)"
```

Ajustar en la cabecera de **`cloudbuild.yaml`**: **`_REGION`**, **`_SERVICE_NAME`**, **`_AR_REPOSITORY`**, **`_IMAGE_NAME`**, **`_DATABASE_SECRET`**, CPU/memoria/timeout (**`_CPU`**, **`_MEMORY`**, **`_CLOUD_RUN_TIMEOUT`**), cómputo (**`machineType`**, **`diskSizeGb`**), escalado (**`_MIN_INSTANCES`**, **`_MAX_INSTANCES`**, **`_CONCURRENCY`**), acceso público (**`_ALLOW_UNAUTHENTICATED`**: **`true`** / **`false`**) e imágenes de test opcionales (**`_POSTGRES_TEST_IMAGE`**, **`_PYTHON_TEST_IMAGE`**).

---

## Post‑despliegue

- Obtener URL del servicio: consola Cloud Run o `gcloud run services describe`.
- Probar **`/docs`** y **`GET /openapi.json`** en la URL pública (si ingress es público).
- Revisar logs en **Logging** (Cloud Run revisión activa).

---

## Relación API ↔ infra

La documentación HTTP es la misma en local y en GCP; sólo cambia el **origen (`BASE_URL`)** y la política de acceso público/acotado sobre Cloud Run.

