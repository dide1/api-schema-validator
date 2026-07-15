package io.schemavalidator.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public class ValidationError {

    @JsonProperty("path")
    private String path;

    @JsonProperty("message")
    private String message;

    @JsonProperty("validator")
    private String validator;

    public String getPath() { return path; }
    public String getMessage() { return message; }
    public String getValidator() { return validator; }

    @Override
    public String toString() {
        return path + ": " + message;
    }
}
