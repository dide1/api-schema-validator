package io.schemavalidator.model;

import com.fasterxml.jackson.annotation.JsonValue;

public enum Visibility {
    PRIVATE("private"),
    TEAM("team"),
    PUBLIC("public");

    private final String value;

    Visibility(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }
}
