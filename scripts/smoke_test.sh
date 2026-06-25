#!/usr/bin/env bash
# Smoke-test a deployed API (local uvicorn or Lambda Function URL).
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
BASE_URL="${BASE_URL%/}"

PASS=0
FAIL=0

pass() {
  echo "PASS: $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "FAIL: $1"
  FAIL=$((FAIL + 1))
}

expect_status() {
  local name="$1"
  local method="$2"
  local path="$3"
  local expected="$4"
  local body="${5:-}"
  local tmp
  tmp="$(mktemp)"
  local code
  if [[ -n "$body" ]]; then
    code="$(curl -s -o "$tmp" -w "%{http_code}" -X "$method" \
      -H "Content-Type: application/json" \
      -d "$body" \
      "$BASE_URL$path")"
  else
    code="$(curl -s -o "$tmp" -w "%{http_code}" -X "$method" "$BASE_URL$path")"
  fi
  if [[ "$code" == "$expected" ]]; then
    pass "$name (HTTP $code)"
  else
    fail "$name (expected HTTP $expected, got $code): $(cat "$tmp")"
  fi
  rm -f "$tmp"
}

expect_body_contains() {
  local name="$1"
  local method="$2"
  local path="$3"
  local needle="$4"
  local body="${5:-}"
  local tmp
  tmp="$(mktemp)"
  if [[ -n "$body" ]]; then
    curl -s -o "$tmp" -X "$method" -H "Content-Type: application/json" -d "$body" "$BASE_URL$path"
  else
    curl -s -o "$tmp" -X "$method" "$BASE_URL$path"
  fi
  if grep -q "$needle" "$tmp"; then
    pass "$name"
  else
    fail "$name (missing '$needle'): $(cat "$tmp")"
  fi
  rm -f "$tmp"
}

echo "Smoke testing: $BASE_URL"
echo "---"

expect_status "health" GET "/health" 200
expect_body_contains "health body" GET "/health" '"status":"ok"'

expect_status "list schemas" GET "/schemas" 200
expect_body_contains "schemas include user" GET "/schemas" '"user"'

VALID_PAYLOAD='{"schema_name":"user","payload":{"id":1,"email":"jane@example.com","name":"Jane Doe"}}'
expect_status "validate valid" POST "/validate/single" 200 "$VALID_PAYLOAD"
expect_body_contains "validate valid body" POST "/validate/single" '"valid":true' "$VALID_PAYLOAD"

INVALID_PAYLOAD='{"schema_name":"user","payload":{"id":"bad","email":"not-an-email","name":""}}'
expect_status "validate invalid" POST "/validate/single" 200 "$INVALID_PAYLOAD"
expect_body_contains "validate invalid body" POST "/validate/single" '"valid":false' "$INVALID_PAYLOAD"

echo "---"
echo "Results: $PASS passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
