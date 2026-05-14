"""Global metadata for OpenAPI / Swagger UI."""

API_TITLE = "Users Management API"

API_DESCRIPTION = """
REST API for **user management** backed by PostgreSQL (works with **Supabase**).

### Primary resource
- Collection: **`/users`**
- **Registration**: **`POST /users/register`** — public sign-up (same contract as **`POST /users/`**).
- Identifier: **`id`** (UUID v4)

### REST shape
- **Collection vs item**: **`GET /users/`** returns part of the collection; **`GET`**, **`PATCH`**, **`DELETE`**
  on **`/users/{id}`** target one stable item (`id`).
- **Verbs**: **`POST`** appends items; **`GET`** is safe; **`PATCH`** is partial (no **`PUT`** replace);
  **`DELETE`** removes an item (**`404`** on later calls after success).
- **Created**: **`POST /users/`** and **`POST /users/register`** return **`201`** and **`Location`** for
  **`GET /users/{id}`** (RFC 7231).
- **Paging**: **`skip`** / **`limit`** with fixed sort (**`created_at`**, then **`id`**).

### Conventions
- Timestamps use **ISO 8601** with timezone (**UTC** recommended).
- **Text fields** (`username`, names) are **trimmed**; empty / whitespace-only strings are rejected (**`422`**).
- **Email** is **trimmed and lowercased** before validation and persistence so uniqueness matches user intent.
- Allowed roles: **`admin`**, **`user`**, **`guest`**.
- Partial updates use **`PATCH`** (only fields supplied are applied).
- **`LOG_LEVEL`** env (optional) controls application log verbosity (**`INFO`** default).
- **Throttling** (**`429`**): optional in-process limits (**slowapi**) via **`RATE_LIMIT_*`** env; see README.

### Common HTTP status codes
| Code | Meaning |
|------|---------|
| **201** | Resource created (includes **`Location`** header on **`POST`** create/register) |
| **204** | Success with no body (`DELETE`) |
| **404** | User not found |
| **409** | Conflict (duplicate `username` or `email`) |
| **422** | Invalid body or parameters |
| **429** | Too many requests (**slowapi** quota) |

### Error responses
Most errors return **`application/json`**.
- **`404`** / **`409`**: **`{ "detail": "<message>" }`** (single human-readable line; useful for dashboards).
- **`422`**: FastAPI **`HTTPValidationError`** — **`detail`** is a **list** of validation issues
  (each with `loc`, `msg`, `type`). Typical causes: malformed UUID paths, **`skip`**/**`limit`**
  out of range, invalid email/role JSON.
- **`429`**: **`Rate limit exceeded`** from **slowapi** (JSON with `detail`; respect client backoff).

### Exploring the contract interactively
| URL | Purpose |
|-----|---------|
| **`/docs`** | **Swagger UI** — try requests, see schemas |
| **`/redoc`** | **ReDoc** — read-only narrative view |
| **`/openapi.json`** | Raw OpenAPI 3 schema (import into Postman, codegen, gateways) |

No API key path is enforced in this demo; guard edge access at the boundary (VPC, IAP, gateway)
when moving beyond development.

"""

OPENAPI_TAGS = [
    {
        "name": "users",
        "description": (
            "**REST resource `users`** — collection at **`GET/POST /users/`**; "
            "registration alias **`POST /users/register`** (same request/response as create). "
            "Items at **`GET|PATCH|DELETE /users/{user_id}`** with UUID **`id`**. "
            "See top-level docs for paging, **`Location`** on **`201`**, and conflict semantics."
        ),
        "externalDocs": {
            "description": "FastAPI — metadata & OpenAPI customization",
            "url": "https://fastapi.tiangolo.com/tutorial/metadata/",
        },
    },
]
