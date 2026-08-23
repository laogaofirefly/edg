#include "edg_value.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

typedef struct {
    size_t length;
    size_t capacity;
    EdgValue *items;
} EdgArray;

/* allocation is performed directly at each ownership boundary */
static char *edg_strdup(const char *s) {
    size_t n = s ? strlen(s) : 0;
    char *out = malloc(n + 1);
    if (!out) return NULL;
    if (n) memcpy(out, s, n);
    out[n] = '\0';
    return out;
}

EdgValue edg_value_nothing(void) { EdgValue v = {EDG_VALUE_NOTHING, {0}}; return v; }
EdgValue edg_value_number(double x) { EdgValue v = {EDG_VALUE_NUMBER, {0}}; v.as.number = x; return v; }
EdgValue edg_value_bool(int x) { EdgValue v = {EDG_VALUE_BOOL, {0}}; v.as.boolean = !!x; return v; }
EdgValue edg_value_string(const char *s) {
    EdgValue v = {EDG_VALUE_STRING, {0}};
    v.as.string = edg_strdup(s);
    if (!v.as.string) return edg_value_nothing();
    return v;
}
EdgValue edg_value_array(size_t length) {
    EdgValue v = {EDG_VALUE_ARRAY, {0}};
    EdgArray *a = calloc(1, sizeof(*a));
    if (!a) return edg_value_nothing();
    a->length = length; a->capacity = length;
    a->items = length ? calloc(length, sizeof(*a->items)) : NULL;
    if (length && !a->items) { free(a); return edg_value_nothing(); }
    for (size_t i = 0; i < length; ++i) a->items[i] = edg_value_nothing();
    v.as.object = a; return v;
}

void edg_value_free(EdgValue *v) {
    if (!v) return;
    if (v->type == EDG_VALUE_STRING) free(v->as.string);
    else if (v->type == EDG_VALUE_ARRAY && v->as.object) {
        EdgArray *a = v->as.object;
        for (size_t i = 0; i < a->length; ++i) edg_value_free(&a->items[i]);
        free(a->items); free(a);
    }
    *v = edg_value_nothing();
}

int edg_value_clone(EdgValue *out, const EdgValue *v) {
    if (!out || !v) return 0;
    *out = edg_value_nothing();
    if (v->type == EDG_VALUE_STRING) { *out = edg_value_string(v->as.string); return out->type == EDG_VALUE_STRING; }
    if (v->type == EDG_VALUE_ARRAY) {
        EdgArray *src = v->as.object; if (!src) return 0;
        *out = edg_value_array(src->length); if (out->type != EDG_VALUE_ARRAY) return 0;
        EdgArray *dst = out->as.object;
        for (size_t i = 0; i < src->length; ++i) if (!edg_value_clone(&dst->items[i], &src->items[i])) { edg_value_free(out); return 0; }
        return 1;
    }
    *out = *v; return 1;
}

EdgValueType edg_value_type(const EdgValue *v) { return v ? v->type : EDG_VALUE_NOTHING; }
double edg_value_number_get(const EdgValue *v) { return v && v->type == EDG_VALUE_NUMBER ? v->as.number : 0.0; }
int edg_value_bool_get(const EdgValue *v) { return v && v->type == EDG_VALUE_BOOL ? v->as.boolean : 0; }
const char *edg_value_string_get(const EdgValue *v) { return v && v->type == EDG_VALUE_STRING ? v->as.string : NULL; }
size_t edg_value_array_len(const EdgValue *v) { EdgArray *a = v && v->type == EDG_VALUE_ARRAY ? v->as.object : NULL; return a ? a->length : 0; }

int edg_value_equal(const EdgValue *a, const EdgValue *b) {
    if (!a || !b || a->type != b->type) return 0;
    if (a->type == EDG_VALUE_NOTHING) return 1;
    if (a->type == EDG_VALUE_NUMBER) return a->as.number == b->as.number;
    if (a->type == EDG_VALUE_BOOL) return a->as.boolean == b->as.boolean;
    if (a->type == EDG_VALUE_STRING) return strcmp(a->as.string, b->as.string) == 0;
    if (a->type == EDG_VALUE_ARRAY) {
        EdgArray *x = a->as.object, *y = b->as.object;
        if (!x || !y || x->length != y->length) return x == y;
        for (size_t i = 0; i < x->length; ++i) if (!edg_value_equal(&x->items[i], &y->items[i])) return 0;
        return 1;
    }
    return 0;
}

int edg_value_array_get(const EdgValue *v, size_t i, EdgValue *out) {
    EdgArray *a = v && v->type == EDG_VALUE_ARRAY ? v->as.object : NULL;
    return a && i < a->length && edg_value_clone(out, &a->items[i]);
}
int edg_value_array_set(EdgValue *v, size_t i, const EdgValue *item) {
    EdgArray *a = v && v->type == EDG_VALUE_ARRAY ? v->as.object : NULL; EdgValue copy;
    if (!a || i >= a->length || !edg_value_clone(&copy, item)) return 0;
    edg_value_free(&a->items[i]); a->items[i] = copy; return 1;
}
int edg_value_array_push(EdgValue *v, const EdgValue *item) {
    EdgArray *a = v && v->type == EDG_VALUE_ARRAY ? v->as.object : NULL; EdgValue copy;
    if (!a || !edg_value_clone(&copy, item)) return 0;
    if (a->length == a->capacity) { size_t n = a->capacity ? a->capacity * 2 : 4; EdgValue *p = realloc(a->items, n * sizeof(*p)); if (!p) { edg_value_free(&copy); return 0; } a->items = p; a->capacity = n; }
    a->items[a->length++] = copy; return 1;
}
int edg_value_array_pop(EdgValue *v, EdgValue *out) {
    EdgArray *a = v && v->type == EDG_VALUE_ARRAY ? v->as.object : NULL;
    if (!a || !a->length || !out) return 0;
    *out = a->items[--a->length]; a->items[a->length] = edg_value_nothing(); return 1;
}
int edg_value_array_clear(EdgValue *v) {
    EdgArray *a = v && v->type == EDG_VALUE_ARRAY ? v->as.object : NULL;
    if (!a) return 0;
    for (size_t i = 0; i < a->length; ++i) edg_value_free(&a->items[i]);
    a->length = 0; return 1;
}
int edg_value_array_compact(EdgValue *v) {
    EdgArray *a = v && v->type == EDG_VALUE_ARRAY ? v->as.object : NULL;
    if (!a) return 0;
    if (a->length == 0) { free(a->items); a->items = NULL; a->capacity = 0; return 1; }
    if (a->capacity > a->length) {
        EdgValue *p = realloc(a->items, a->length * sizeof(*p));
        if (p) { a->items = p; a->capacity = a->length; }
    }
    return 1;
}
int edg_value_array_contains(const EdgValue *v, const EdgValue *item) {
    EdgArray *a = v && v->type == EDG_VALUE_ARRAY ? v->as.object : NULL;
    if (!a || !item) return 0;
    for (size_t i = 0; i < a->length; ++i) if (edg_value_equal(&a->items[i], item)) return 1;
    return 0;
}
char *edg_value_to_string(const EdgValue *v) {
    char buffer[64];
    if (!v) return edg_strdup("");
    if (v->type == EDG_VALUE_STRING) return edg_strdup(v->as.string);
    if (v->type == EDG_VALUE_BOOL) return edg_strdup(v->as.boolean ? "true" : "false");
    if (v->type == EDG_VALUE_NOTHING) return edg_strdup("nothing");
    if (v->type == EDG_VALUE_NUMBER) { snprintf(buffer, sizeof(buffer), "%g", v->as.number); return edg_strdup(buffer); }
    if (v->type == EDG_VALUE_ARRAY) return edg_strdup("[array]");
    return edg_strdup("[value]");
}
char *edg_value_array_join(const EdgValue *v, const char *separator) {
    EdgArray *a = v && v->type == EDG_VALUE_ARRAY ? v->as.object : NULL;
    const char *sep = separator ? separator : "";
    size_t total = 1, sep_len = strlen(sep);
    if (!a) return edg_strdup("");
    for (size_t i = 0; i < a->length; ++i) {
        char *part = edg_value_to_string(&a->items[i]);
        if (!part) return NULL;
        total += strlen(part); if (i) total += sep_len; free(part);
    }
    char *out = malloc(total); if (!out) return NULL; out[0] = '\0';
    for (size_t i = 0; i < a->length; ++i) {
        char *part = edg_value_to_string(&a->items[i]);
        if (i) strcat(out, sep);
        strcat(out, part);
        free(part);
    }
    return out;
}
int edg_value_truthy(const EdgValue *v) {
    if (!v || v->type == EDG_VALUE_NOTHING) return 0;
    if (v->type == EDG_VALUE_BOOL) return v->as.boolean;
    if (v->type == EDG_VALUE_NUMBER) return v->as.number != 0.0;
    if (v->type == EDG_VALUE_STRING) return v->as.string && v->as.string[0];
    if (v->type == EDG_VALUE_ARRAY) return edg_value_array_len(v) != 0;
    return 1;
}
