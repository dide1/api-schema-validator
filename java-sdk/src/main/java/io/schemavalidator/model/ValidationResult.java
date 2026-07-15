package io.schemavalidator.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Collections;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public class ValidationResult {

    @JsonProperty("valid")
    private boolean valid;

    @JsonProperty("errors")
    private List<ValidationError> errors = Collections.emptyList();

    @JsonProperty("suggestion")
    private String suggestion;

    public boolean isValid() { return valid; }
    public List<ValidationError> getErrors() { return errors; }
    public String getSuggestion() { return suggestion; }
}
