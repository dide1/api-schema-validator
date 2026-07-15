package io.schemavalidator.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Collections;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public class BatchResultItem {

    @JsonProperty("index")
    private int index;

    @JsonProperty("valid")
    private boolean valid;

    @JsonProperty("errors")
    private List<ValidationError> errors = Collections.emptyList();

    public int getIndex() { return index; }
    public boolean isValid() { return valid; }
    public List<ValidationError> getErrors() { return errors; }
}
