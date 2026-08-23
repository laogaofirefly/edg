#ifndef EDG_VALUE_H
#define EDG_VALUE_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    EDG_VALUE_NOTHING = 0,
    EDG_VALUE_NUMBER,
    EDG_VALUE_BOOL,
    EDG_VALUE_STRING,
    EDG_VALUE_ARRAY
} EdgValueType;

typedef struct EdgValue {
    EdgValueType type;
    union {
        double number;
        int boolean;
        char *string;
        void *object;
    } as;
} EdgValue;

EdgValue edg_value_nothing(void);
EdgValue edg_value_number(double value);
EdgValue edg_value_bool(int value);
EdgValue edg_value_string(const char *value);
EdgValue edg_value_array(size_t length);
void edg_value_free(EdgValue *value);
int edg_value_clone(EdgValue *out, const EdgValue *value);
int edg_value_equal(const EdgValue *left, const EdgValue *right);
EdgValueType edg_value_type(const EdgValue *value);
double edg_value_number_get(const EdgValue *value);
int edg_value_bool_get(const EdgValue *value);
const char *edg_value_string_get(const EdgValue *value);
size_t edg_value_array_len(const EdgValue *value);
int edg_value_array_get(const EdgValue *value, size_t index, EdgValue *out);
int edg_value_array_set(EdgValue *value, size_t index, const EdgValue *item);
int edg_value_array_push(EdgValue *value, const EdgValue *item);
int edg_value_array_pop(EdgValue *value, EdgValue *out);
int edg_value_array_clear(EdgValue *value);
int edg_value_array_compact(EdgValue *value);
int edg_value_array_contains(const EdgValue *value, const EdgValue *item);
char *edg_value_to_string(const EdgValue *value);
int edg_value_truthy(const EdgValue *value);

#ifdef __cplusplus
}
#endif
#endif