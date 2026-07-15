package io.schemavalidator.exception;

public class SchemaValidatorException extends RuntimeException {

    private final int statusCode;

    public SchemaValidatorException(String message, int statusCode) {
        super(message);
        this.statusCode = statusCode;
    }

    public SchemaValidatorException(String message, int statusCode, Throwable cause) {
        super(message, cause);
        this.statusCode = statusCode;
    }

    public int getStatusCode() {
        return statusCode;
    }

    public boolean isUnauthorized() {
        return statusCode == 401;
    }

    public boolean isForbidden() {
        return statusCode == 403;
    }

    public boolean isNotFound() {
        return statusCode == 404;
    }
}
