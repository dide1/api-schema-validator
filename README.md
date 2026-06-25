# API Schema Validator

Production-ready REST API for validating JSON payloads against user-defined JSON Schemas, with batch validation and Git check-in/check-out integration.

## Tech Stack

- Python 3.11+
- FastAPI + Pydantic v2
- jsonschema (Draft 2020-12)
- GitPython
- uvicorn

## Setup

### 1. Create a virtual environment

```bash
cd api-schema-validator
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy or edit `.env` in the project root:

```env
REPO_PATH=.
SCHEMAS_DIR=./schemas
```

- `REPO_PATH` — Git repository root (defaults to project directory)
- `SCHEMAS_DIR` — Directory containing `*.json` schema files

### 4. Initialize Git (required for Git endpoints)

```bash
git init
git add .
git commit -m "Initial commit"
```

### 5. Run the server

From the project root:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API base URL: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- Health check: `GET http://localhost:8000/health`

## Postman Setup

1. Create an environment variable `baseUrl` = `http://localhost:8000`.
2. Set the collection base URL to `{{baseUrl}}`.
3. Use `Content-Type: application/json` for all POST requests.

### Example requests

#### Single validation — `POST {{baseUrl}}/validate/single`

```json
{
  "schema_name": "user",
  "payload": {
    "id": 1,
    "email": "jane@example.com",
    "name": "Jane Doe"
  }
}
```

#### Batch validation — `POST {{baseUrl}}/validate/batch`

```json
{
  "items": [
    {
      "schema_name": "user",
      "payload": { "id": 1, "email": "a@b.com", "name": "A" }
    },
    {
      "schema_name": "user",
      "payload": { "id": "bad", "email": "not-an-email" }
    }
  ]
}
```

#### List schemas — `GET {{baseUrl}}/schemas`

#### Upload schema — `POST {{baseUrl}}/schemas/upload`

```json
{
  "schema_name": "product",
  "schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["sku"],
    "properties": {
      "sku": { "type": "string" }
    }
  }
}
```

#### Git check-in — `POST {{baseUrl}}/git/checkin`

```json
{
  "message": "Add product schema"
}
```

#### Git checkout — `POST {{baseUrl}}/git/checkout`

```json
{
  "target": "main"
}
```

#### Git status — `GET {{baseUrl}}/git/status`

## Adding a Schema Manually

1. Create a JSON Schema file in the `schemas/` directory, e.g. `schemas/order.json`.
2. Use Draft 2020-12 (`$schema`: `https://json-schema.org/draft/2020-12/schema`).
3. Reference it by filename without extension: `"schema_name": "order"`.

Example `schemas/order.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["order_id"],
  "properties": {
    "order_id": { "type": "string" }
  }
}
```

Alternatively, upload via `POST /schemas/upload`.

## Frontend

A React SPA in `frontend/` provides template management, validation, and OAuth login.

### Run locally

Terminal 1 — API:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2 — frontend:

```bash
make frontend-dev
```

Open `http://localhost:5173`. Vite proxies API requests to port 8000.

### Enable authentication locally

Add to `.env`:

```env
AUTH_ENABLED=true
JWT_SECRET=your-dev-secret
FRONTEND_URL=http://localhost:5173
OAUTH_REDIRECT_BASE=http://localhost:8000
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
ADMIN_EMAILS=you@example.com
```

Register OAuth redirect URIs:

- `http://localhost:8000/auth/callback/google`
- `http://localhost:8000/auth/callback/github`

### Roles and visibility

| Role | Upload / edit / delete | Validate | Admin panel |
|------|------------------------|----------|-------------|
| admin | All templates | Yes | Yes |
| editor | Own + team templates | Yes | No |
| viewer | No | Yes | No |

Each template has visibility: **private** (owner only), **team** (team members), or **public** (all authenticated users).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/auth/config` | Whether auth is enabled |
| GET | `/auth/login/{provider}` | OAuth redirect (google, github) |
| GET | `/auth/callback/{provider}` | OAuth callback |
| GET | `/auth/me` | Current user profile |
| GET | `/auth/users` | List users (admin) |
| PUT | `/auth/users/{id}` | Update user role/team (admin) |
| POST | `/validate/single` | Validate one payload |
| POST | `/validate/batch` | Validate multiple payloads |
| GET | `/schemas` | List accessible schemas |
| GET | `/schemas/{name}` | Get schema JSON |
| POST | `/schemas/upload` | Upload schema (editor+) |
| PUT | `/schemas/{name}` | Update schema (editor+) |
| DELETE | `/schemas/{name}` | Delete schema (editor+) |
| POST | `/schemas/verify` | Verify schema without saving |
| POST | `/git/checkin` | Stage all and commit (local only) |
| POST | `/git/checkout` | Checkout branch or commit (local only) |
| GET | `/git/status` | Repository status (local only) |

## Error Responses

| Status | Condition |
|--------|-----------|
| 401 | Not authenticated |
| 403 | Permission denied |
| 404 | Schema not found |
| 422 | Invalid request body or invalid schema definition |
| 500 | Git failure, validation service error, or unhandled error |

Validation failures on payloads return `200` with `"valid": false` and structured `errors` — not HTTP errors.

## Testing

### Automated tests (pytest)

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
# or
make test
```

Tests use an isolated temp `schemas/` copy and temp git repo so they do not modify your project files.

### Smoke test (local or Lambda)

With the API running locally:

```bash
export BASE_URL=http://127.0.0.1:8001
make smoke
```

After deploy, point at your Function URL:

```bash
export BASE_URL=https://xxxxxxxx.lambda-url.us-east-2.on.aws
make smoke
```

On Lambda, health checks expect `"runtime":"aws-lambda"` in the response body for the bundled script; local smoke only checks `"status":"ok"`.

## AWS Lambda Deployment

The API runs on Lambda via [Mangum](https://github.com/Kludex/mangum) (ASGI adapter). Git routes are **disabled** on Lambda; validation and schema upload/list work.

### Prerequisites

- [AWS CLI](https://aws.amazon.com/cli/) configured (`aws configure`)
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- Python 3.11

### Deploy

```bash
# From project root
sam build
sam deploy --guided   # first time: stack name, region, confirm changeset
```

After deploy, note the **ApiFunctionUrl** output — use it as Postman `baseUrl` (no trailing slash).

Example: `https://xxxxxxxx.lambda-url.us-east-1.on.aws`

### Health check on Lambda

`GET {ApiFunctionUrl}/health` returns:

```json
{
  "status": "ok",
  "runtime": "aws-lambda"
}
```

### Lambda behavior

| Feature | On Lambda |
|---------|-----------|
| `/validate/*`, `/schemas`, `/auth/*` | Yes |
| OAuth login (Google, GitHub) | Yes (configure client IDs in SAM parameters) |
| Schema storage | S3 (durable) + DynamoDB metadata |
| User / template metadata | DynamoDB |
| `/git/*` | Not registered |

### Deploy with frontend

```bash
sam deploy --guided
# Note ApiFunctionUrl and FrontendBucketName outputs

export FRONTEND_BUCKET=<FrontendBucketName>
make frontend-deploy
```

Set `FrontendUrl` SAM parameter to your frontend URL for CORS and OAuth redirects.

### OAuth setup for production

1. Create Google OAuth credentials and GitHub OAuth App.
2. Set redirect URIs to `{ApiFunctionUrl}/auth/callback/google` and `.../github`.
3. Pass `GoogleClientId`, `GoogleClientSecret`, `GitHubClientId`, `GitHubClientSecret`, and `AdminEmails` as SAM parameters.
4. Set a strong `JwtSecret` parameter.

### Local Lambda simulation

```bash
make build
make local-api   # http://127.0.0.1:3000 (requires Docker for SAM)
```

Or test the handler module:

```bash
pip install -r requirements-lambda.txt
AWS_LAMBDA_FUNCTION_NAME=local uvicorn app.main:app --port 8001
```

### Files

| File | Purpose |
|------|---------|
| `handler.py` | Lambda handler (`handler.handler`) |
| `template.yaml` | SAM infrastructure |
| `requirements-lambda.txt` | Slim deps (no GitPython/uvicorn) |
| `Makefile` | `build`, `deploy`, `local-api` shortcuts |

Copy `samconfig.toml.example` to `samconfig.toml` to skip `--guided` on repeat deploys.

## Project Structure

```
api-schema-validator/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── dependencies/
│   ├── routers/
│   │   ├── validate.py
│   │   ├── auth.py
│   │   └── git_ops.py
│   ├── services/
│   │   ├── validator.py
│   │   ├── template_service.py
│   │   ├── auth_service.py
│   │   └── git_service.py
│   ├── storage/
│   ├── models/
│   └── exceptions/
├── frontend/
├── schemas/
├── tests/
├── scripts/smoke_test.sh
├── handler.py
├── template.yaml
├── requirements.txt
├── requirements-dev.txt
├── requirements-lambda.txt
├── .env
└── README.md
```
