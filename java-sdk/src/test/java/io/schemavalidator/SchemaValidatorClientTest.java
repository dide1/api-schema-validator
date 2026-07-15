package io.schemavalidator;

import io.schemavalidator.model.BatchValidationItem;
import io.schemavalidator.model.BatchValidationResult;
import io.schemavalidator.model.Visibility;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

import static org.junit.jupiter.api.Assertions.*;

class SchemaValidatorClientTest {

    @Test
    void builderRequiresBaseUrl() {
        assertThrows(NullPointerException.class, () ->
                SchemaValidatorClient.builder().token("tok").build());
    }

    @Test
    void builderCreatesClient() {
        assertNotNull(SchemaValidatorClient.builder()
                .baseUrl("http://localhost:8000")
                .token("test-token")
                .build());
    }

    @Test
    void validateRejectsNullSchemaName() {
        SchemaValidatorClient client = client();
        assertThrows(NullPointerException.class, () ->
                client.validate(null, Map.of("key", "value")));
    }

    @Test
    void validateRejectsNullPayload() {
        SchemaValidatorClient client = client();
        assertThrows(NullPointerException.class, () ->
                client.validate("user", (Map<String, Object>) null));
    }

    @Test
    void validateObjectRejectsNullObject() {
        SchemaValidatorClient client = client();
        assertThrows(NullPointerException.class, () ->
                client.validate("user", (Object) null));
    }

    @Test
    void validateBatchRejectsEmptyItems() {
        assertThrows(IllegalArgumentException.class, () ->
                client().validateBatch(List.of()));
    }

    @Test
    void validateAsyncRejectsNullSchemaName() {
        assertThrows(NullPointerException.class, () ->
                client().validateAsync(null, Map.of()));
    }

    @Test
    void validateAsyncReturnsCompletableFuture() {
        // Just verify the method exists and returns a CompletableFuture
        // (actual HTTP call would fail against localhost — that's expected)
        SchemaValidatorClient client = client();
        CompletableFuture<BatchValidationResult> future = client.validateBatchAsync(
                List.of(new BatchValidationItem("user", Map.of("name", "Alice"))));
        assertNotNull(future);
    }

    @Test
    void batchResultAllValidWhenEmpty() {
        BatchValidationResult result = new BatchValidationResult();
        assertTrue(result.allValid());
        assertTrue(result.failures().isEmpty());
    }

    @Test
    void visibilityValuesMatchApi() {
        assertEquals("private", Visibility.PRIVATE.getValue());
        assertEquals("team", Visibility.TEAM.getValue());
        assertEquals("public", Visibility.PUBLIC.getValue());
    }

    @Test
    void batchItemStoresFields() {
        Map<String, Object> payload = Map.of("name", "Alice", "age", 30);
        BatchValidationItem item = new BatchValidationItem("user", payload);
        assertEquals("user", item.getSchemaName());
        assertEquals(payload, item.getPayload());
    }

    private SchemaValidatorClient client() {
        return SchemaValidatorClient.builder().baseUrl("http://localhost:8000").build();
    }
}
