package io.schemavalidator.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public class TemplateSummary {

    @JsonProperty("schema_name")
    private String schemaName;

    @JsonProperty("owner_id")
    private String ownerId;

    @JsonProperty("owner_name")
    private String ownerName;

    @JsonProperty("visibility")
    private String visibility;

    @JsonProperty("team_id")
    private String teamId;

    @JsonProperty("updated_at")
    private String updatedAt;

    public String getSchemaName() { return schemaName; }
    public String getOwnerId() { return ownerId; }
    public String getOwnerName() { return ownerName; }
    public String getVisibility() { return visibility; }
    public String getTeamId() { return teamId; }
    public String getUpdatedAt() { return updatedAt; }
}
