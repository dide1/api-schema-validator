package io.schemavalidator.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Collections;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public class BatchValidationResult {

    @JsonProperty("results")
    private List<BatchResultItem> results = Collections.emptyList();

    public List<BatchResultItem> getResults() { return results; }

    public boolean allValid() {
        return results.stream().allMatch(BatchResultItem::isValid);
    }

    public List<BatchResultItem> failures() {
        return results.stream()
                .filter(r -> !r.isValid())
                .collect(java.util.stream.Collectors.toList());
    }
}
