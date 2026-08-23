"""C runtime emitted by the EDG native backend.

This is intentionally small.  The compiler can gradually move generated
variables from C primitive types to EdgValue without changing the public
compiler interface.
"""

RUNTIME_C = r'''#include <stdio.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>

typedef enum {
    EDG_NOTHING = 0,
    EDG_NUMBER,
    EDG_BOOL,
    EDG_STRING,
    EDG_ARRAY,
    EDG_DICT,
    EDG_FUNCTION,
    EDG_OBJECT
} EdgType;

typedef struct EdgValue EdgValue;
typedef struct {
    size_t length;
    size_t capacity;
    EdgValue *items;
} EdgArray;

struct EdgValue {
    EdgType type;
    union {
        double number;
        int boolean;
        char *string;
        void *object;
    } as;
};
static EdgValue edg_nothing(void) {
    EdgValue v = { EDG_NOTHING, { 0 } };
    return v;
}

static EdgValue edg_number(double x) {
    EdgValue v = { EDG_NUMBER, { 0 } };
    v.as.number = x;
    return v;
}

static EdgValue edg_bool(int x) {
    EdgValue v = { EDG_BOOL, { 0 } };
    v.as.boolean = !!x;
    return v;
}
static EdgValue edg_string(char *x) {
    EdgValue v = { EDG_STRING, { 0 } };
    v.as.string = x ? strdup(x) : strdup("");
    if (!v.as.string) { fprintf(stderr, "EDG: out of memory\\n"); exit(1); }
    return v;
}
static EdgValue edg_string_owned(char *x) {
    EdgValue v = { EDG_STRING, { 0 } };
    v.as.string = x ? x : strdup("");
    if (!v.as.string) { fprintf(stderr, "EDG: out of memory\\n"); exit(1); }
    return v;
}
static void edg_free_value(EdgValue v);
static EdgValue edg_clone_value(EdgValue v);
static void edg_assign_value(EdgValue *slot, EdgValue next);
static int edg_equal(EdgValue a, EdgValue b);
static EdgValue edg_array_new(size_t length) {
    EdgArray *a = malloc(sizeof(EdgArray));
    if (!a) { fprintf(stderr, "EDG: out of memory\n"); exit(1); }
    a->length = length;
    a->capacity = length;
    a->items = length ? calloc(length, sizeof(EdgValue)) : NULL;
    if (length && !a->items) { fprintf(stderr, "EDG: out of memory\n"); exit(1); }
    EdgValue v = { EDG_ARRAY, { 0 } };
    v.as.object = a;
    return v;
}
static EdgArray *edg_as_array(EdgValue v) {
    if (v.type != EDG_ARRAY) { fprintf(stderr, "EDG: value is not an array\n"); exit(1); }
    return (EdgArray *)v.as.object;
}
static EdgValue edg_array_value_get(EdgValue v, int i) {
    EdgArray *a = edg_as_array(v);
    if (i < 0 || (size_t)i >= a->length) { fprintf(stderr, "EDG array index out of bounds: %d (length %zu)\\n", i, a->length); exit(1); }
    return edg_clone_value(a->items[i]);
}
static void edg_array_value_set(EdgValue v, int i, EdgValue item) {
    EdgArray *a = edg_as_array(v);
    if (i < 0 || (size_t)i >= a->length) { fprintf(stderr, "EDG array index out of bounds: %d (length %zu)\n", i, a->length); exit(1); }
    EdgValue copy = edg_clone_value(item);
    edg_assign_value(&a->items[i], copy);
}
static double edg_array_value_len(EdgValue v) { return (double)edg_as_array(v)->length; }
static void edg_array_push(EdgValue v, EdgValue item) {
    EdgArray *a = edg_as_array(v);
    if (a->length == a->capacity) {
        size_t next = a->capacity ? a->capacity * 2 : 4;
        EdgValue *items = realloc(a->items, next * sizeof(EdgValue));
        if (!items) { fprintf(stderr, "EDG: out of memory\\n"); exit(1); }
        a->items = items;
        a->capacity = next;
    }
    a->items[a->length++] = edg_clone_value(item);
}
static EdgValue edg_array_pop(EdgValue v) {
    EdgArray *a = edg_as_array(v);
    if (a->length == 0) return edg_nothing();
    EdgValue item = a->items[--a->length];
    EdgValue result = edg_clone_value(item);
    edg_free_value(item);
    a->items[a->length] = edg_nothing();
    return result;
}
static int edg_array_contains(EdgValue v, EdgValue item) {
    EdgArray *a = edg_as_array(v);
    for (size_t i = 0; i < a->length; i++) {
        if (edg_equal(a->items[i], item)) return 1;
    }
    return 0;
}
static void edg_array_clear(EdgValue v) {
    EdgArray *a = edg_as_array(v);
    for (size_t i = 0; i < a->length; i++) edg_free_value(a->items[i]);
    a->length = 0;
}
static void edg_array_free(EdgValue v) {
    if (v.type != EDG_ARRAY || !v.as.object) return;
    EdgArray *a = (EdgArray *)v.as.object;
    for (size_t i = 0; i < a->length; i++) edg_free_value(a->items[i]);
    free(a->items);
    free(a);
}
static void edg_free_value(EdgValue v) {
    if (v.type == EDG_STRING) free(v.as.string);
    else if (v.type == EDG_ARRAY) edg_array_free(v);
}
static EdgValue edg_clone_value(EdgValue v) {
    if (v.type == EDG_STRING) return edg_string(v.as.string);
    if (v.type == EDG_ARRAY) {
        EdgArray *src = edg_as_array(v);
        EdgValue copy = edg_array_new(src->length);
        EdgArray *dst = edg_as_array(copy);
        for (size_t i = 0; i < src->length; i++) {
            edg_assign_value(&dst->items[i], edg_clone_value(src->items[i]));
        }
        return copy;
    }
    return v;
}
static int edg_same_owned_data(EdgValue a, EdgValue b) {
    if (a.type != b.type) return 0;
    if (a.type == EDG_STRING) return a.as.string == b.as.string;
    if (a.type == EDG_ARRAY) return a.as.object == b.as.object;
    return 0;
}
static void edg_assign_value(EdgValue *slot, EdgValue next) {
    if (!slot) return;
    if (!edg_same_owned_data(*slot, next)) edg_free_value(*slot);
    *slot = next;
}
static void edg_array_compact(EdgValue v) {
    EdgArray *a = edg_as_array(v);
    if (a->length == 0) {
        free(a->items);
        a->items = NULL;
        a->capacity = 0;
        return;
    }
    if (a->capacity != a->length) {
        EdgValue *items = realloc(a->items, a->length * sizeof(EdgValue));
        if (!items) { fprintf(stderr, "EDG: out of memory\\n"); exit(1); }
        a->items = items;
        a->capacity = a->length;
    }
}

static char *edg_num_to_str(double x) {
    char *s = malloc(64);
    if (!s) { fprintf(stderr, "EDG: out of memory\\n"); exit(1); }
    snprintf(s, 64, "%g", x);
    return s;
}
static char *edg_value_text(EdgValue v) {
    if (v.type == EDG_STRING) return strdup(v.as.string ? v.as.string : "");
    if (v.type == EDG_NUMBER) return edg_num_to_str(v.as.number);
    if (v.type == EDG_BOOL) return strdup(v.as.boolean ? "true" : "false");
    if (v.type == EDG_NOTHING) return strdup("nothing");
    return strdup("<object>");
}
static EdgValue edg_array_join(EdgValue v, EdgValue separator) {
    EdgArray *a = edg_as_array(v);
    if (separator.type != EDG_STRING) {
        fprintf(stderr, "EDG: join separator must be a string\\n"); exit(1);
    }
    const char *sep = separator.as.string ? separator.as.string : "";
    size_t total = 1;
    char **parts = a->length ? calloc(a->length, sizeof(char *)) : NULL;
    if (a->length && !parts) { fprintf(stderr, "EDG: out of memory\\n"); exit(1); }
    for (size_t i = 0; i < a->length; i++) {
        parts[i] = edg_value_text(a->items[i]);
        total += strlen(parts[i]);
        if (i) total += strlen(sep);
    }
    char *out = malloc(total);
    if (!out) { fprintf(stderr, "EDG: out of memory\\n"); exit(1); }
    out[0] = '\0';
    for (size_t i = 0; i < a->length; i++) {
        if (i) strcat(out, sep);
        strcat(out, parts[i]);
        free(parts[i]);
    }
    free(parts);
    return edg_string_owned(out);
}


static int edg_is_number(EdgValue v) { return v.type == EDG_NUMBER; }
static int edg_is_string(EdgValue v) { return v.type == EDG_STRING; }

static EdgValue edg_add(EdgValue a, EdgValue b) {
    if (edg_is_number(a) && edg_is_number(b))
        return edg_number(a.as.number + b.as.number);
    if (edg_is_string(a) && edg_is_string(b)) {
        size_t n = strlen(a.as.string) + strlen(b.as.string) + 1;
        char *s = malloc(n);
        if (!s) { fprintf(stderr, "EDG: out of memory\n"); exit(1); }
        strcpy(s, a.as.string); strcat(s, b.as.string);
        return edg_string_owned(s);
    }
    fprintf(stderr, "EDG: unsupported + operands\n");
    exit(1);
}

static EdgValue edg_numeric_bin(EdgValue a, EdgValue b, char op) {
    if (!edg_is_number(a) || !edg_is_number(b)) {
        fprintf(stderr, "EDG: arithmetic operands must be numbers\n");
        exit(1);
    }
    double x = a.as.number;
    double y = b.as.number;
    if (op == '-') return edg_number(x - y);
    if (op == '*') return edg_number(x * y);
    if (op == '/') {
        if (y == 0.0) {
            fprintf(stderr, "EDG: division by zero\n");
            exit(1);
        }
        return edg_number(x / y);
    }
    fprintf(stderr, "EDG: unsupported arithmetic operator\n");
    exit(1);
}
static EdgValue edg_sub(EdgValue a, EdgValue b) { return edg_numeric_bin(a, b, '-'); }
static EdgValue edg_mul(EdgValue a, EdgValue b) { return edg_numeric_bin(a, b, '*'); }
static EdgValue edg_div(EdgValue a, EdgValue b) { return edg_numeric_bin(a, b, '/'); }

static int edg_equal(EdgValue a, EdgValue b) {
    if (a.type != b.type) return 0;
    if (a.type == EDG_NUMBER) return a.as.number == b.as.number;
    if (a.type == EDG_BOOL) return a.as.boolean == b.as.boolean;
    if (a.type == EDG_STRING) return strcmp(a.as.string, b.as.string) == 0;
    return a.type == EDG_NOTHING;
}

static void edg_print_value(EdgValue v) {
    switch (v.type) {
        case EDG_STRING: printf("%s\n", v.as.string ? v.as.string : ""); break;
        case EDG_BOOL: printf("%s\n", v.as.boolean ? "true" : "false"); break;
        case EDG_NOTHING: printf("nothing\n"); break;
        case EDG_NUMBER: printf("%g\n", v.as.number); break;
        default: printf("<object>\n"); break;
    }
}

static int edg_truthy(EdgValue v) {
    if (v.type == EDG_NOTHING) return 0;
    if (v.type == EDG_BOOL) return v.as.boolean;
if (v.type == EDG_NUMBER) return v.as.number != 0.0;
    if (v.type == EDG_STRING) return v.as.string && v.as.string[0] != '\0';
    if (v.type == EDG_ARRAY) return edg_as_array(v)->length != 0;
    return 1;
}
'''
