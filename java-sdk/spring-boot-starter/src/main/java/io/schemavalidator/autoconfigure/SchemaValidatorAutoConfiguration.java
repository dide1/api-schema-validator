package io.schemavalidator.autoconfigure;

import io.schemavalidator.SchemaGenerator;
import io.schemavalidator.SchemaValidatorClient;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;

@AutoConfiguration
@EnableConfigurationProperties(SchemaValidatorProperties.class)
@ConditionalOnProperty(prefix = "schema-validator", name = "url")
public class SchemaValidatorAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public SchemaValidatorClient schemaValidatorClient(SchemaValidatorProperties props) {
        SchemaValidatorClient.Builder builder = SchemaValidatorClient.builder()
                .baseUrl(props.getUrl())
                .connectTimeout(props.getConnectTimeoutSeconds());
        if (props.getToken() != null && !props.getToken().isBlank()) {
            builder.token(props.getToken());
        }
        return builder.build();
    }

    @Bean
    @ConditionalOnMissingBean
    public SchemaGenerator schemaGenerator() {
        return new SchemaGenerator();
    }
}
