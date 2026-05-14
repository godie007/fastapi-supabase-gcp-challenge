# API de usuarios (FastAPI + Supabase/Postgres + GCP)

API REST para gestionar usuarios con roles tipados, validación Pydantic, logging estructurado básico y pipeline de CI/CD en Google Cloud Build hacia Cloud Run.

## Stack

- **FastAPI** + **Uvicorn**
- **SQLAlchemy 2** + **psycopg2** (Postgres; compatible con cadena de conexión de **Supabase**)
- **Pydantic v2** (`EmailStr`, `ConfigDict`, ejemplos en OpenAPI)
- **pytest** + **httpx** (`TestClient`)
- **Docker** (imagen multietapa) y **Cloud Build** → **Artifact Registry** → **Cloud Run**

## Software Engineer Challenge (submission)

Este repositorio cubre el challenge de **API REST de usuarios con FastAPI**, persistencia en **Postgres** (p. ej. Supabase), **tests con pytest**, documentación **OpenAPI/Swagger** en `/docs`, manejo de errores (`404`/`409`/validación), **logging** básico y **CI/CD en GCP** mediante `cloudbuild.yaml` (tests → build Docker → push → **Cloud Run**).

### Mapping — evaluation criteria

| Criterio | Cómo se aborda |
|----------|----------------|
| **Code quality** | Paquetes `app/core`, `models`, `schemas`, `crud`, `api`; tipado y docstrings breves en puntos de entrada. |
| **API design** | Recurso `/users`, verbos HTTP y códigos (`201`, `204`, `404`, `409`), actualización parcial con `PATCH`. |
| **Data handling** | Pydantic (`EmailStr`, límites), `Enum` de rol, SQLAlchemy + restricciones en BD; conflictos de unicidad explícitos. |
| **Testing** | `app/tests/` con caminos felices y errores; SQLite aislado en CI sin credenciales. |
| **Documentation** | README + ejemplos JSON y **curl** por endpoint; Swagger UI en `/docs`. |
| **Cloud / CI/CD** | `Dockerfile` multietapa, `cloudbuild.yaml` con pytest, imagen y despliegue a Cloud Run. |

## Configuración local

### Variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```bash
DATABASE_URL=postgresql+psycopg2://usuario:clave@host:5432/postgres
```

Hay una plantilla en `.env.example`. Si la contraseña incluye caracteres reservados en URLs (por ejemplo `#`), codifícala (`#` → `%23`) para que la cadena sea válida.

En Supabase suele usarse el host `db.<project-ref>.supabase.co`; revisa también el pooler (Session mode) si tu entorno lo requiere.

### Ejecutar con Docker Compose

Levanta Postgres con esquema inicial y la API:

```bash
docker compose up --build
```

La API quedará en `http://localhost:8000` y la documentación interactiva en `http://localhost:8000/docs`.

### Ejecutar sin Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://...
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Tests

Los tests usan SQLite en memoria con `dependency_overrides` sobre `get_db`, sin credenciales externas:

```bash
pip install -r requirements.txt
pytest app/tests -v
```

En Cloud Build el paso de pruebas define `DATABASE_URL=sqlite://` para cumplir el mismo comportamiento.

## Esquema SQL (Supabase / Postgres)

Si gestionas la base fuera de Docker Compose, puedes crear la tabla equivalente a `app/models/user.py`:

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

Los inserts los realiza la aplicación (UUID generado en Python). El campo **`updated_at`** se mantiene al día con la capa ORM (`onupdate`) y, en Postgres/Supabase, con el trigger aplicado en migraciones (`set_users_updated_at`).

## Endpoints

Base URL de ejemplo: `http://localhost:8000`.

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/users/` | Crea un usuario (`201 Created`) |
| GET | `/users/` | Lista usuarios (paginación `skip`, `limit`) |
| GET | `/users/{id}` | Obtiene un usuario por UUID (`404` si no existe) |
| PATCH | `/users/{id}` | Actualización parcial (`404` / `409` según caso) |
| DELETE | `/users/{id}` | Elimina usuario (`204 No Content`) |

### Ejemplos JSON

**POST `/users/` — cuerpo de entrada**

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

**Respuesta (`201`)**

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

**PATCH `/users/{id}` — ejemplo parcial**

```json
{
  "first_name": "Janet",
  "role": "admin",
  "active": true
}
```

**Errores típicos**

- `404`: usuario inexistente (detalle `User not found: …`).
- `409`: `username` o `email` duplicado.
- `422`: cuerpo inválido (validación Pydantic / UUID mal formado en rutas).

### Ejemplos con `curl` (cada operación CRUD)

Sustituye `BASE_URL` (p. ej. `http://localhost:8000`) y el `USER_ID` devuelto por el `POST`.

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

# Copia el id del JSON anterior, por ejemplo:
USER_ID=550e8400-e29b-41d4-a716-446655440000

# Read (collection) — 200 OK
curl -s "$BASE_URL/users/?skip=0&limit=10" | jq .

# Read (item) — 200 OK
curl -s "$BASE_URL/users/$USER_ID" | jq .

# Update (parcial) — 200 OK
curl -s -X PATCH "$BASE_URL/users/$USER_ID" \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Janet","role":"admin"}' | jq .

# Delete — 204 No Content (sin cuerpo)
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X DELETE "$BASE_URL/users/$USER_ID"

# Read tras borrar — 404
curl -s "$BASE_URL/users/$USER_ID" | jq .
```

Documentación interactiva: **`GET /docs`** (Swagger UI) y **`GET /redoc`**.

## CI/CD en Google Cloud Platform

El archivo `cloudbuild.yaml` cumple el challenge (**tests**, **build** de imagen Docker y **despliegue** en Cloud Run). El orden aplicado es:

1. **Instalar dependencias y ejecutar pytest** (`python:3.12-slim`, `DATABASE_URL=sqlite://` para no requerir Postgres en CI).
2. **Construir la imagen** con Docker usando el `Dockerfile` multietapa.
3. **Publicar la imagen** en Artifact Registry (`${_REGION}-docker.pkg.dev/$PROJECT_ID/${_AR_REPOSITORY}/${_IMAGE_NAME}:$SHORT_SHA`).
4. **Desplegar en Cloud Run** con `gcloud run deploy`, inyectando `DATABASE_URL` mediante la sustitución **`_DATABASE_URL`** (por ejemplo la URI de Postgres de Supabase).

Ejemplo de disparo manual:

```bash
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions=SHORT_SHA=$(git rev-parse --short HEAD),_DATABASE_URL="postgresql+psycopg2://..."
```

Requisitos previos habituales: API habilitadas (`run.googleapis.com`, `artifactregistry.googleapis.com`, `cloudbuild.googleapis.com`), repositorio de Artifact Registry creado y permisos del service account de Cloud Build para empujar imágenes y desplegar en Cloud Run.

Para producción suele preferirse **Secret Manager** y `--set-secrets` / `--update-secrets` en lugar de pasar la URI en texto plano como sustitución; la cadena anterior sirve como referencia para entornos de prueba.

## Logging

- Mensaje de arranque en el **lifespan** de FastAPI.
- Middleware HTTP que registra método, ruta, código de estado y duración aproximada.
- Capa CRUD con mensajes `INFO`/`WARNING` en operaciones relevantes.
