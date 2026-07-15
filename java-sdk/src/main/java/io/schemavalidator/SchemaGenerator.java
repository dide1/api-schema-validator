package io.schemavalidator;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.schemavalidator.model.SchemaUploadResult;
import io.schemavalidator.model.Visibility;

import java.lang.reflect.*;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.util.*;

/**
 * Generates a JSON Schema (draft 2020-12) from a Java class via reflection.
 *
 * Supports: primitives, String, enums, arrays, Collections, Maps, and nested objects.
 * Respects {@code @JsonProperty} for field names and any {@code @NotNull}/{@code @NonNull}
 * annotation for the required array.
 */
public class SchemaGenerator {

    public Map<String, Object> generate(Class<?> clazz) {
        Map<String, Object> schema = new LinkedHashMap<>();
        schema.put("$schema", "https://json-schema.org/draft/2020-12/schema");
        schema.putAll(schemaForType(clazz, new HashSet<>()));
        return schema;
    }

    /**
     * Generate a JSON Schema from {@code clazz} and upload it to the validator service.
     */
    public SchemaUploadResult generateAndUpload(Class<?> clazz, String schemaName, SchemaValidatorClient client) {
        return generateAndUpload(clazz, schemaName, client, Visibility.PRIVATE, null);
    }

    public SchemaUploadResult generateAndUpload(Class<?> clazz, String schemaName, SchemaValidatorClient client,
                                                 Visibility visibility, String teamId) {
        return client.uploadSchema(schemaName, generate(clazz), visibility, teamId);
    }

    // --- Type dispatch ---

    private Map<String, Object> schemaForType(Type type, Set<Class<?>> visited) {
        if (type instanceof ParameterizedType) {
            return schemaForParameterized((ParameterizedType) type, visited);
        }
        if (type instanceof GenericArrayType) {
            Map<String, Object> s = new LinkedHashMap<>();
            s.put("type", "array");
            s.put("items", schemaForType(((GenericArrayType) type).getGenericComponentType(), visited));
            return s;
        }
        if (type instanceof Class) {
            return schemaForClass((Class<?>) type, visited);
        }
        return new LinkedHashMap<>();
    }

    private Map<String, Object> schemaForClass(Class<?> clazz, Set<Class<?>> visited) {
        if (clazz == String.class || clazz == Character.class || clazz == char.class) {
            return Map.of("type", "string");
        }
        if (clazz == Boolean.class || clazz == boolean.class) {
            return Map.of("type", "boolean");
        }
        if (isIntegerType(clazz)) {
            return Map.of("type", "integer");
        }
        if (isNumberType(clazz)) {
            return Map.of("type", "number");
        }
        if (clazz.isEnum()) {
            List<String> values = new ArrayList<>();
            for (Object c : clazz.getEnumConstants()) values.add(c.toString());
            Map<String, Object> s = new LinkedHashMap<>();
            s.put("type", "string");
            s.put("enum", values);
            return s;
        }
        if (clazz.isArray()) {
            Map<String, Object> s = new LinkedHashMap<>();
            s.put("type", "array");
            s.put("items", schemaForClass(clazz.getComponentType(), visited));
            return s;
        }
        if (Collection.class.isAssignableFrom(clazz)) {
            return Map.of("type", "array");
        }
        if (Map.class.isAssignableFrom(clazz)) {
            return Map.of("type", "object");
        }
        if (clazz == Object.class || clazz == Void.class) {
            return new LinkedHashMap<>();
        }
        if (visited.contains(clazz)) {
            return Map.of("type", "object");
        }
        return buildObjectSchema(clazz, visited);
    }

    private Map<String, Object> schemaForParameterized(ParameterizedType type, Set<Class<?>> visited) {
        Class<?> raw = (Class<?>) type.getRawType();
        Type[] args = type.getActualTypeArguments();

        if (Collection.class.isAssignableFrom(raw)) {
            Map<String, Object> s = new LinkedHashMap<>();
            s.put("type", "array");
            if (args.length > 0) s.put("items", schemaForType(args[0], visited));
            return s;
        }
        if (Map.class.isAssignableFrom(raw)) {
            Map<String, Object> s = new LinkedHashMap<>();
            s.put("type", "object");
            if (args.length > 1) s.put("additionalProperties", schemaForType(args[1], visited));
            return s;
        }
        return schemaForClass(raw, visited);
    }

    // --- Object introspection ---

    private Map<String, Object> buildObjectSchema(Class<?> clazz, Set<Class<?>> visited) {
        Set<Class<?>> newVisited = new HashSet<>(visited);
        newVisited.add(clazz);

        Map<String, Object> properties = new LinkedHashMap<>();
        List<String> required = new ArrayList<>();

        for (Field field : allFields(clazz)) {
            if (Modifier.isStatic(field.getModifiers()) || Modifier.isTransient(field.getModifiers())) continue;
            String name = fieldName(field);
            properties.put(name, schemaForType(field.getGenericType(), newVisited));
            if (isRequired(field)) required.add(name);
        }

        Map<String, Object> schema = new LinkedHashMap<>();
        schema.put("type", "object");
        if (!properties.isEmpty()) schema.put("properties", properties);
        if (!required.isEmpty()) schema.put("required", required);
        return schema;
    }

    private List<Field> allFields(Class<?> clazz) {
        List<Field> fields = new ArrayList<>();
        for (Class<?> c = clazz; c != null && c != Object.class; c = c.getSuperclass()) {
            fields.addAll(Arrays.asList(c.getDeclaredFields()));
        }
        return fields;
    }

    private String fieldName(Field field) {
        JsonProperty jp = field.getAnnotation(JsonProperty.class);
        return (jp != null && !jp.value().isEmpty()) ? jp.value() : field.getName();
    }

    private boolean isRequired(Field field) {
        return Arrays.stream(field.getAnnotations())
                .anyMatch(a -> {
                    String n = a.annotationType().getSimpleName();
                    return n.equals("NotNull") || n.equals("NonNull");
                });
    }

    // --- Type helpers ---

    private boolean isIntegerType(Class<?> c) {
        return c == Integer.class || c == int.class
                || c == Long.class || c == long.class
                || c == Short.class || c == short.class
                || c == Byte.class || c == byte.class
                || c == BigInteger.class;
    }

    private boolean isNumberType(Class<?> c) {
        return c == Double.class || c == double.class
                || c == Float.class || c == float.class
                || c == BigDecimal.class
                || (Number.class.isAssignableFrom(c) && !isIntegerType(c));
    }
}
