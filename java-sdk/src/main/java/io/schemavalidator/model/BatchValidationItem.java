package io.schemavalidator.model;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Map;

public class BatchValidationItem {

    @JsonProperty("schema_name")
    private final String schemaName;

    @JsonProperty("payload")
    private final Map<String, Object> payload;

    public BatchValidationItem(String schemaName, Map<String, Object> payload) {
        this.schemaName = schemaName;
        this.payload = payload;
    }

    public String getSchemaName() { return schemaName; }
    public Map<String, Object> getPayload() { return payload; }
}
