"""Global metadata for OpenAPI / Swagger UI."""

API_TITLE = "Users Management API"

API_DESCRIPTION = """
REST API for **user management** backed by PostgreSQL (works with **Supabase**).

### Primary resource
- Collection: **`/users`**
- **Registration**: **`POST /users/register`** — public sign-up (same contract as **`POST /users/`**).
- Identifier: **`id`** (UUID v4)

### Conventions
- Timestamps use **ISO 8601** with timezone (**UTC** recommended).
- Allowed roles: **`admin`**, **`user`**, **`guest`**.
- Partial updates use **`PATCH`** (only fields supplied are applied).
- **`LOG_LEVEL`** env (optional) controls application log verbosity (**`INFO`** default).

### Common HTTP status codes
| Code | Meaning |
|------|---------|
| **201** | Resource created |
| **204** | Success with no body (`DELETE`) |
| **404** | User not found |
| **409** | Conflict (duplicate `username` or `email`) |
| **422** | Invalid body or parameters (Pydantic validation) |

### Documentation
- **Swagger UI** (`/docs`) and **ReDoc** (`/redoc`) always reflect the current API contract.
- The repository **`README`** includes **copy‑paste `curl` examples for every endpoint** (`POST`, `GET` list/item, `PATCH`, `DELETE`) plus common error scenarios.
"""

OPENAPI_TAGS = [
    {
        "name": "users",
        "description": (
            "**CRUD** + **registration** (`POST /users/register`): create or sign up, read (single and "
            "collection), partial update, and delete."
        ),
        "externalDocs": {
            "description": "FastAPI — automatic OpenAPI documentation",
            "url": "https://fastapi.tiangolo.com/tutorial/metadata/",
        },
    },
]
