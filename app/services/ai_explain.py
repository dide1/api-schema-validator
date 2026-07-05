import json

import anthropic

from app.logging_config import get_logger
from app.models.schemas import ValidationErrorDetail

logger = get_logger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def explain_errors(errors: list[ValidationErrorDetail], schema: dict) -> str | None:
    if not errors:
        return None

    error_lines = "\n".join(f"- field '{e.path}': {e.message}" for e in errors)
    prompt = (
        "A JSON payload failed validation against the following schema. "
        "Translate the errors into a single plain-English fix suggestion (1–3 sentences) "
        "that a developer can act on immediately. Be specific about field names and expected values.\n\n"
        f"Schema:\n{json.dumps(schema, indent=2)}\n\n"
        f"Validation errors:\n{error_lines}\n\n"
        "Reply with only the fix suggestion, no preamble."
    )

    try:
        response = _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except anthropic.APIError as exc:
        logger.warning("Claude API call failed for error explanation", extra={"error": str(exc)})
        return None
