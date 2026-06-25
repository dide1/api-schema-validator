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


class UnauthorizedError(Exception):
    """Raised when authentication is required or invalid."""

    def __init__(self, message: str = "Not authenticated") -> None:
        self.message = message
        super().__init__(message)


class ForbiddenError(Exception):
    """Raised when the user lacks permission for an action."""

    def __init__(self, message: str = "Permission denied") -> None:
        self.message = message
        super().__init__(message)


class BadRequestError(Exception):
    """Raised when the request is invalid."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class TemplateNotFoundError(Exception):
    """Raised when template metadata does not exist."""

    def __init__(self, schema_name: str) -> None:
        self.schema_name = schema_name
        super().__init__(f"Template '{schema_name}' not found")
