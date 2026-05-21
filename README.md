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

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/validate/single` | Validate one payload |
| POST | `/validate/batch` | Validate multiple payloads |
| GET | `/schemas` | List available schemas |
| POST | `/schemas/upload` | Upload a new schema |
| POST | `/git/checkin` | Stage all and commit |
| POST | `/git/checkout` | Checkout branch or commit |
| GET | `/git/status` | Repository status |

## Error Responses

| Status | Condition |
|--------|-----------|
| 404 | Schema not found |
| 422 | Invalid request body or invalid schema definition |
| 500 | Git failure, validation service error, or unhandled error |

Validation failures on payloads return `200` with `"valid": false` and structured `errors` — not HTTP errors.

## Project Structure

```
api-schema-validator/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── routers/
│   │   ├── validate.py
│   │   └── git_ops.py
│   ├── services/
│   │   ├── validator.py
│   │   └── git_service.py
│   ├── models/
│   │   └── schemas.py
│   └── exceptions/
│       ├── errors.py
│       └── handlers.py
├── schemas/
├── requirements.txt
├── .env
└── README.md
```
