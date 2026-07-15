package io.schemavalidator.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public class SchemaDeleteResult {

    @JsonProperty("success")
    private boolean success;

    @JsonProperty("schema_name")
    private String schemaName;

    @JsonProperty("message")
    private String message;

    public boolean isSuccess() { return success; }
    public String getSchemaName() { return schemaName; }
    public String getMessage() { return message; }
}
