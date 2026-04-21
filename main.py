import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="API Schema Validator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SCHEMA_STORE = "templates"
COLLECTIONS_STORE = "collections"
os.makedirs(SCHEMA_STORE, exist_ok=True)
os.makedirs(COLLECTIONS_STORE, exist_ok=True)


def schema_file(schema_name: str) -> str:
    return os.path.join(SCHEMA_STORE, f"{schema_name}.json")

def collection_file(collection_name: str) -> str:
    return os.path.join(COLLECTIONS_STORE, f"{collection_name}.json")


@app.get("/")
def serve_frontend():
    return FileResponse("index.html")


@app.post("/templates/{schema_name}")
def register_schema(schema_name: str, schema: dict):
    with open(schema_file(schema_name), "w") as f:
        json.dump(schema, f)
    return {"message": f"Schema '{schema_name}' registered"}


@app.get("/templates")
def list_schemas():
    return [f.replace(".json", "") for f in os.listdir(SCHEMA_STORE) if f.endswith(".json")]


@app.get("/templates/{schema_name}")
def fetch_schema(schema_name: str):
    if not os.path.exists(schema_file(schema_name)):
        raise HTTPException(status_code=404, detail="Schema not found")
    with open(schema_file(schema_name)) as f:
        return json.load(f)


@app.post("/validate/{schema_name}")
def run_validation(schema_name: str, incoming: dict):
    if not os.path.exists(schema_file(schema_name)):
        raise HTTPException(status_code=404, detail="Schema not found")

    with open(schema_file(schema_name)) as f:
        schema = json.load(f)

    violations = []

    for field, expected_type in schema.items():
        if field not in incoming:
            violations.append(f"Missing field: '{field}'")
        else:
            actual_type = type(incoming[field]).__name__
            if actual_type != expected_type:
                if expected_type == "float" and actual_type == "int":
                    pass
                else:
                    violations.append(f"'{field}': expected {expected_type}, got {actual_type}")

    for field in incoming:
        if field not in schema:
            violations.append(f"Unexpected field: '{field}'")

    if violations:
        return {"valid": False, "errors": violations}
    return {"valid": True}


@app.delete("/templates/{schema_name}")
def delete_schema(schema_name: str):
    if not os.path.exists(schema_file(schema_name)):
        raise HTTPException(status_code=404, detail="Schema not found")
    os.remove(schema_file(schema_name))
    for fname in os.listdir(COLLECTIONS_STORE):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(COLLECTIONS_STORE, fname)
        with open(path) as f:
            data = json.load(f)
        updated = [e for e in data if e.get("schemaName") != schema_name]
        with open(path, "w") as f:
            json.dump(updated, f, indent=2)
    return {"message": f"Schema '{schema_name}' deleted"}


class CollectionEntry(BaseModel):
    schemaName: str
    registerBody: str
    validateBody: str = ""


@app.post("/collections/{collection_name}")
def append_to_collection(collection_name: str, entry: CollectionEntry):
    path = collection_file(collection_name)
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
    else:
        data = []
    data.append(entry.dict())
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return {"message": f"Schema '{entry.schemaName}' added to '{collection_name}.json'"}


@app.get("/collections")
def list_collections():
    return [f.replace(".json", "") for f in os.listdir(COLLECTIONS_STORE) if f.endswith(".json")]


@app.get("/collections/{collection_name}")
def get_collection(collection_name: str):
    path = collection_file(collection_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Collection not found")
    with open(path) as f:
        return json.load(f)


@app.delete("/collections/{collection_name}")
def delete_collection(collection_name: str):
    path = collection_file(collection_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Collection not found")
    os.remove(path)
    return {"message": f"Collection '{collection_name}' deleted"}


class PayloadList(BaseModel):
    payloads: list

@app.post("/payloads/save")
def save_payloads(data: PayloadList):
    with open("payloads.json", "w") as f:
        json.dump(data.payloads, f, indent=2)

    # build a lookup of schemaName -> latest validateBody from saved payloads
    lookup = {}
    for p in data.payloads:
        lookup[p["schemaName"]] = p["validateBody"]

    # update any collection files that have matching schemas
    for fname in os.listdir(COLLECTIONS_STORE):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(COLLECTIONS_STORE, fname)
        with open(path) as f:
            col = json.load(f)
        updated = False
        for entry in col:
            if entry.get("schemaName") in lookup:
                entry["validateBody"] = lookup[entry["schemaName"]]
                updated = True
        if updated:
            with open(path, "w") as f:
                json.dump(col, f, indent=2)

    return {"message": f"Saved {len(data.payloads)} payloads"}


@app.post("/payloads/clear")
def clear_payloads():
    with open("payloads.json", "w") as f:
        json.dump([], f)
    return {"message": "payloads.json cleared"}