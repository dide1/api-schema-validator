package io.schemavalidator;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.schemavalidator.exception.SchemaValidatorException;
import io.schemavalidator.model.*;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.CompletableFuture;

public class SchemaValidatorClient {

    private final String baseUrl;
    private final String token;
    private final HttpClient httpClient;
    private final ObjectMapper mapper;

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {};

    private SchemaValidatorClient(Builder builder) {
        this.baseUrl = builder.baseUrl.replaceAll("/$", "");
        this.token = builder.token;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(builder.connectTimeoutSeconds))
                .build();
        this.mapper = new ObjectMapper();
    }

    // --- Validation (sync) ---

    public ValidationResult validate(String schemaName, Map<String, Object> payload) {
        return validate(schemaName, payload, false);
    }

    public ValidationResult validate(String schemaName, Map<String, Object> payload, boolean explain) {
        Objects.requireNonNull(schemaName, "schemaName must not be null");
        Objects.requireNonNull(payload, "payload must not be null");
        String url = baseUrl + "/validate/single" + (explain ? "?explain=true" : "");
        return post(url, buildValidateBody(schemaName, payload), ValidationResult.class);
    }

    /** Serialize any Java object via Jackson and validate it against the named schema. */
    public ValidationResult validate(String schemaName, Object object) {
        return validate(schemaName, object, false);
    }

    public ValidationResult validate(String schemaName, Object object, boolean explain) {
        Objects.requireNonNull(object, "object must not be null");
        return validate(schemaName, mapper.convertValue(object, MAP_TYPE), explain);
    }

    public BatchValidationResult validateBatch(List<BatchValidationItem> items) {
        Objects.requireNonNull(items, "items must not be null");
        if (items.isEmpty()) throw new IllegalArgumentException("items must not be empty");
        return post(baseUrl + "/validate/batch", Map.of("items", items), BatchValidationResult.class);
    }

    // --- Validation (async) ---

    public CompletableFuture<ValidationResult> validateAsync(String schemaName, Map<String, Object> payload) {
        return validateAsync(schemaName, payload, false);
    }

    public CompletableFuture<ValidationResult> validateAsync(String schemaName, Map<String, Object> payload,
                                                              boolean explain) {
        Objects.requireNonNull(schemaName, "schemaName must not be null");
        Objects.requireNonNull(payload, "payload must not be null");
        String url = baseUrl + "/validate/single" + (explain ? "?explain=true" : "");
        return postAsync(url, buildValidateBody(schemaName, payload), ValidationResult.class);
    }

    public CompletableFuture<ValidationResult> validateAsync(String schemaName, Object object) {
        Objects.requireNonNull(object, "object must not be null");
        return validateAsync(schemaName, mapper.convertValue(object, MAP_TYPE));
    }

    public CompletableFuture<BatchValidationResult> validateBatchAsync(List<BatchValidationItem> items) {
        Objects.requireNonNull(items, "items must not be null");
        if (items.isEmpty()) throw new IllegalArgumentException("items must not be empty");
        return postAsync(baseUrl + "/validate/batch", Map.of("items", items), BatchValidationResult.class);
    }

    // --- Schemas ---

    public List<TemplateSummary> listSchemas() {
        Map<?, ?> raw = get(baseUrl + "/schemas", Map.class);
        try {
            String json = mapper.writeValueAsString(raw.get("templates"));
            return mapper.readValue(json,
                    mapper.getTypeFactory().constructCollectionType(List.class, TemplateSummary.class));
        } catch (IOException e) {
            throw new SchemaValidatorException("Failed to parse listSchemas response: " + e.getMessage(), 0, e);
        }
    }

    public SchemaDetail getSchema(String schemaName) {
        Objects.requireNonNull(schemaName, "schemaName must not be null");
        return get(baseUrl + "/schemas/" + schemaName, SchemaDetail.class);
    }

    public SchemaUploadResult uploadSchema(String schemaName, Map<String, Object> schema) {
        return uploadSchema(schemaName, schema, Visibility.PRIVATE, null);
    }

    public SchemaUploadResult uploadSchema(String schemaName, Map<String, Object> schema,
                                           Visibility visibility, String teamId) {
        Objects.requireNonNull(schemaName, "schemaName must not be null");
        Objects.requireNonNull(schema, "schema must not be null");
        Map<String, Object> body = new HashMap<>();
        body.put("schema_name", schemaName);
        body.put("schema", schema);
        body.put("visibility", visibility != null ? visibility.getValue() : Visibility.PRIVATE.getValue());
        if (teamId != null) body.put("team_id", teamId);
        return post(baseUrl + "/schemas/upload", body, SchemaUploadResult.class);
    }

    public SchemaUploadResult updateSchema(String schemaName, Map<String, Object> schema) {
        return updateSchema(schemaName, schema, null, null);
    }

    public SchemaUploadResult updateSchema(String schemaName, Map<String, Object> schema,
                                           Visibility visibility, String teamId) {
        Objects.requireNonNull(schemaName, "schemaName must not be null");
        Map<String, Object> body = new HashMap<>();
        if (schema != null) body.put("schema", schema);
        if (visibility != null) body.put("visibility", visibility.getValue());
        if (teamId != null) body.put("team_id", teamId);
        return put(baseUrl + "/schemas/" + schemaName, body, SchemaUploadResult.class);
    }

    public SchemaDeleteResult deleteSchema(String schemaName) {
        Objects.requireNonNull(schemaName, "schemaName must not be null");
        return delete(baseUrl + "/schemas/" + schemaName, SchemaDeleteResult.class);
    }

    // --- HTTP internals ---

    private Map<String, Object> buildValidateBody(String schemaName, Map<String, Object> payload) {
        Map<String, Object> body = new HashMap<>();
        body.put("schema_name", schemaName);
        body.put("payload", payload);
        return body;
    }

    private <T> T get(String url, Class<T> type) {
        return execute(requestBuilder(url).GET().build(), type);
    }

    private <T> T post(String url, Object body, Class<T> type) {
        HttpRequest req = requestBuilder(url)
                .POST(jsonBody(body))
                .header("Content-Type", "application/json")
                .build();
        return execute(req, type);
    }

    private <T> CompletableFuture<T> postAsync(String url, Object body, Class<T> type) {
        HttpRequest req = requestBuilder(url)
                .POST(jsonBody(body))
                .header("Content-Type", "application/json")
                .build();
        return httpClient.sendAsync(req, HttpResponse.BodyHandlers.ofString())
                .thenApply(response -> parseResponse(response, type));
    }

    private <T> T put(String url, Object body, Class<T> type) {
        HttpRequest req = requestBuilder(url)
                .PUT(jsonBody(body))
                .header("Content-Type", "application/json")
                .build();
        return execute(req, type);
    }

    private <T> T delete(String url, Class<T> type) {
        return execute(requestBuilder(url).DELETE().build(), type);
    }

    private HttpRequest.Builder requestBuilder(String url) {
        HttpRequest.Builder b = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Accept", "application/json")
                .timeout(Duration.ofSeconds(30));
        if (token != null && !token.isEmpty()) {
            b.header("Authorization", "Bearer " + token);
        }
        return b;
    }

    private HttpRequest.BodyPublisher jsonBody(Object body) {
        try {
            return HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(body));
        } catch (IOException e) {
            throw new SchemaValidatorException("Failed to serialize request body: " + e.getMessage(), 0, e);
        }
    }

    private <T> T execute(HttpRequest request, Class<T> type) {
        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            return parseResponse(response, type);
        } catch (SchemaValidatorException e) {
            throw e;
        } catch (IOException | InterruptedException e) {
            if (e instanceof InterruptedException) Thread.currentThread().interrupt();
            throw new SchemaValidatorException("Request failed: " + e.getMessage(), 0, e);
        }
    }

    private <T> T parseResponse(HttpResponse<String> response, Class<T> type) {
        int status = response.statusCode();
        if (status >= 200 && status < 300) {
            try {
                return mapper.readValue(response.body(), type);
            } catch (IOException e) {
                throw new SchemaValidatorException("Failed to parse response: " + e.getMessage(), status, e);
            }
        }
        throw new SchemaValidatorException(extractErrorDetail(response.body()), status);
    }

    private String extractErrorDetail(String body) {
        try {
            Map<?, ?> map = mapper.readValue(body, Map.class);
            Object detail = map.get("detail");
            return detail != null ? detail.toString() : body;
        } catch (IOException e) {
            return body;
        }
    }

    // --- Builder ---

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private String baseUrl;
        private String token;
        private int connectTimeoutSeconds = 10;

        public Builder baseUrl(String baseUrl) { this.baseUrl = baseUrl; return this; }
        public Builder token(String token) { this.token = token; return this; }
        public Builder connectTimeout(int seconds) { this.connectTimeoutSeconds = seconds; return this; }

        public SchemaValidatorClient build() {
            Objects.requireNonNull(baseUrl, "baseUrl must not be null");
            return new SchemaValidatorClient(this);
        }
    }
}
