class SchemaNotFoundError(Exception):
    """Raised when a requested JSON schema file does not exist."""

    def __init__(self, schema_name: str) -> None:
        self.schema_name = schema_name
        super().__init__(f"Schema '{schema_name}' not found")


class ValidationServiceError(Exception):
    """Raised when validation fails due to an unexpected internal error."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
