package io.schemavalidator.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public class SchemaDetail {

    @JsonProperty("schema_name")
    private String schemaName;

    @JsonProperty("schema")
    private Map<String, Object> schema;

    @JsonProperty("owner_id")
    private String ownerId;

    @JsonProperty("visibility")
    private String visibility;

    @JsonProperty("team_id")
    private String teamId;

    @JsonProperty("updated_at")
    private String updatedAt;

    public String getSchemaName() { return schemaName; }
    public Map<String, Object> getSchema() { return schema; }
    public String getOwnerId() { return ownerId; }
    public String getVisibility() { return visibility; }
    public String getTeamId() { return teamId; }
    public String getUpdatedAt() { return updatedAt; }
}
