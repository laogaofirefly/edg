#include <stdio.h>
#include <stdlib.h>
#include "edg_value.h"

int main(void) {
    EdgValue values = edg_value_array(0);
    EdgValue text = edg_value_string("edg");
    EdgValue number = edg_value_number(42.0);
    EdgValue got = edg_value_nothing();
    if (values.type != EDG_VALUE_ARRAY || !edg_value_array_push(&values, &text) ||
        !edg_value_array_push(&values, &number) ||
        !edg_value_array_get(&values, 0, &got) ||
        !edg_value_equal(&got, &text) || edg_value_array_len(&values) != 2) {
        edg_value_free(&got); edg_value_free(&number); edg_value_free(&text); edg_value_free(&values);
        return 1;
    }
    char *joined = edg_value_array_join(&values, ",");
    if (!joined) { edg_value_free(&got); edg_value_free(&number); edg_value_free(&text); edg_value_free(&values); return 1; }
    printf("len=%zu text=%s joined=%s truthy=%d\n", edg_value_array_len(&values),
           edg_value_string_get(&got), joined, edg_value_truthy(&values));
    free(joined);
    edg_value_free(&got); edg_value_free(&number); edg_value_free(&text); edg_value_free(&values);
    return 0;
}