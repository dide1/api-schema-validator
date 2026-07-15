package io.schemavalidator.autoconfigure;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "schema-validator")
public class SchemaValidatorProperties {

    /** Base URL of the schema-validator API, e.g. https://api.example.com */
    private String url;

    /** Bearer token for authentication. Leave blank if auth is disabled. */
    private String token;

    /** Connection timeout in seconds (default: 10). */
    private int connectTimeoutSeconds = 10;

    public String getUrl() { return url; }
    public void setUrl(String url) { this.url = url; }

    public String getToken() { return token; }
    public void setToken(String token) { this.token = token; }

    public int getConnectTimeoutSeconds() { return connectTimeoutSeconds; }
    public void setConnectTimeoutSeconds(int connectTimeoutSeconds) {
        this.connectTimeoutSeconds = connectTimeoutSeconds;
    }
}
