# Referencia de la API — Usuarios

Documentación consolidada complementaria de **Swagger UI** (`/docs`) y **OpenAPI JSON** (`/openapi.json`). El contrato ejecutable sigue siendo el schema generado por FastAPI al arrancar el servicio.

---

## Alcance del producto

- **CRUD tipado** sobre el recurso **usuario** persistido en **PostgreSQL** (p. ej. Supabase mediante `DATABASE_URL`).
- **Sin autenticación OAuth/JWT integrada**: el ejemplo es una API abierta pensada como demostración; en producción añádase frontera (API Gateway con clave/IAP/VPC‑SC, etc.).
- **Registro** es un alias de creación (`POST /users/register` ≡ mismo cuerpo y reglas que `POST /users/`).

---

## Recurso y rutas base

Raíz efectiva según cómo montes router: **`/users`** …

| Método | Ruta | Resumen |
|--------|------|--------|
| `POST` | `/users/` | Alta; **`201`** + cabecera **`Location`** (`GET /users/{id}`). |
| `POST` | `/users/register` | Mismo comportamiento que `POST /users/` (onboarding/documentación). |
| `GET` | `/users/` | Colección paginada (**`skip`**, **`limit`**). |
| `GET` | `/users/{user_id}` | Recurso por UUID. |
| `PATCH` | `/users/{user_id}` | Actualización parcial. |
| `DELETE` | `/users/{user_id}` | Borrado; **`204`** sin cuerpo. |

---

## Reglas de validación relevantes

- **`username`**, **`first_name`**, **`last_name`**: texto recortado; no se admiten sólo espacios.
- **`email`**: recortado y normalizado en **minúsculas** para unicidad lógica.
- **`role`**: `admin` \| `user` \| `guest`.
- Índices BD: unicidad **`username`** y **`email`** (detectados como **`409`** con mensajes explícitos).

---

## Códigos HTTP habituales

| Código | Cuándo |
|--------|--------|
| **200** | `GET` / `PATCH` correctos con cuerpo de usuario JSON. |
| **201** | Creación/registro OK; usar **`Location`** para ir al recurso nuevo. |
| **204** | `DELETE` correcto sin cuerpo. |
| **404** | `user_id` inexistente. |
| **409** | Conflicto de unicidad (`username` / `email`). |
| **422** | Validación (`body`, query o UUID de ruta inválidos). |
| **429** | Cuota **slowapi** rebasada (demasiadas peticiones por cliente). |

---

## Formato de errores (`application/json`)

- **`404`** y **`409`** (respuestas de negocio mapeadas a `HTTPException`):  
  **`{ "detail": "mensaje corto incluyendo dato contextual" }`**
- **`422`**: estructura estándar de FastAPI (**lista** en **`detail`** con elementos `loc` / `msg` / `type`).
- **`429`**: cuerpo JSON de **slowapi** con **`detail`**; backoff / respetar **`Retry-After`** si aparece.

Ejemplos rápidos con `curl`: ver sección correspondiente del [**README principal**](../README.md).

---

## Paginación

- **`GET /users/?skip=…&limit=…`**: orden estable **`created_at` ASC**, luego **`id` ASC**.
- **`skip`** ≥ 0; **`limit`** entre 1 y 500.

---

## Cómo consumir OpenAPI desde herramientas

1. Arrancar el servicio (`uvicorn` local o URL de Cloud Run).
2. Abrir **`/openapi.json`** y descargar el JSON **o**
3. Abrir **`/docs`** (**Swagger**) / **`/redoc`** (**ReDoc**).
4. Importar en Postman / Insomnia / generadores cliente (`openapi-generator`, etc.).

---

## Traducción con el modelo de datos

La representación HTTP refleja la tabla **`users`** (UUID `id`, `created_at`, `updated_at`, `active`, …); ver migraciones en **`supabase/migrations/`** y [`README.md`](../README.md) (snippet SQL).

