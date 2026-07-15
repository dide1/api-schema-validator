package io.schemavalidator;

import com.fasterxml.jackson.annotation.JsonProperty;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class SchemaGeneratorTest {

    private SchemaGenerator generator;

    @BeforeEach
    void setUp() {
        generator = new SchemaGenerator();
    }

    @Test
    void includesDraftVersion() {
        Map<String, Object> schema = generator.generate(SimpleBean.class);
        assertEquals("https://json-schema.org/draft/2020-12/schema", schema.get("$schema"));
    }

    @Test
    void stringFieldMapsToStringType() {
        Map<String, Object> schema = generator.generate(SimpleBean.class);
        Map<?, ?> props = (Map<?, ?>) schema.get("properties");
        assertEquals(Map.of("type", "string"), props.get("name"));
    }

    @Test
    void intFieldMapsToIntegerType() {
        Map<String, Object> schema = generator.generate(SimpleBean.class);
        Map<?, ?> props = (Map<?, ?>) schema.get("properties");
        assertEquals(Map.of("type", "integer"), props.get("age"));
    }

    @Test
    void booleanFieldMapsToBooleanType() {
        Map<String, Object> schema = generator.generate(SimpleBean.class);
        Map<?, ?> props = (Map<?, ?>) schema.get("properties");
        assertEquals(Map.of("type", "boolean"), props.get("active"));
    }

    @Test
    void jsonPropertyAnnotationRenamesField() {
        Map<String, Object> schema = generator.generate(AnnotatedBean.class);
        Map<?, ?> props = (Map<?, ?>) schema.get("properties");
        assertTrue(props.containsKey("user_name"), "should use @JsonProperty name");
        assertFalse(props.containsKey("userName"), "should not use Java field name");
    }

    @Test
    void listFieldMapsToArrayType() {
        Map<String, Object> schema = generator.generate(CollectionBean.class);
        Map<?, ?> props = (Map<?, ?>) schema.get("properties");
        Map<?, ?> tagsSchema = (Map<?, ?>) props.get("tags");
        assertEquals("array", tagsSchema.get("type"));
        assertEquals(Map.of("type", "string"), tagsSchema.get("items"));
    }

    @Test
    void enumFieldMapsToStringWithEnum() {
        Map<String, Object> schema = generator.generate(EnumBean.class);
        Map<?, ?> props = (Map<?, ?>) schema.get("properties");
        Map<?, ?> statusSchema = (Map<?, ?>) props.get("status");
        assertEquals("string", statusSchema.get("type"));
        List<?> values = (List<?>) statusSchema.get("enum");
        assertTrue(values.contains("ACTIVE"));
        assertTrue(values.contains("INACTIVE"));
    }

    @Test
    void nestedObjectGeneratesObjectSchema() {
        Map<String, Object> schema = generator.generate(NestedBean.class);
        Map<?, ?> props = (Map<?, ?>) schema.get("properties");
        Map<?, ?> addressSchema = (Map<?, ?>) props.get("address");
        assertEquals("object", addressSchema.get("type"));
        Map<?, ?> addressProps = (Map<?, ?>) addressSchema.get("properties");
        assertNotNull(addressProps.get("street"));
    }

    @Test
    void circularReferenceDoesNotStackOverflow() {
        assertDoesNotThrow(() -> generator.generate(SelfReferencing.class));
    }

    // --- Test fixtures ---

    static class SimpleBean {
        String name;
        int age;
        boolean active;
    }

    static class AnnotatedBean {
        @JsonProperty("user_name")
        String userName;
    }

    static class CollectionBean {
        List<String> tags;
    }

    enum Status { ACTIVE, INACTIVE }

    static class EnumBean {
        Status status;
    }

    static class Address {
        String street;
        String city;
    }

    static class NestedBean {
        String name;
        Address address;
    }

    static class SelfReferencing {
        String id;
        SelfReferencing parent;
    }
}
