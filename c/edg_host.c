#include <stdio.h>
#include <string.h>
#include "edg_python.h"

static void usage(const char *name) {
    fprintf(stderr, "用法: %s native <file.edg> | %s python <file.py> | %s eval <code>\n", name, name, name);
}

int main(int argc, char **argv) {
    int result;
    if (argc < 3) { usage(argv[0]); return 2; }
    if (strcmp(argv[1], "python") == 0) {
        result = edg_python_run_file(argv[2]);
        if (result != 0 && !edg_python_available())
            fprintf(stderr, "Python 嵌入未启用，请使用带 EDG_WITH_PYTHON 的构建。\n");
        edg_python_shutdown();
        return result;
    }
    if (strcmp(argv[1], "eval") == 0) {
        result = edg_python_run_string(argv[2]);
        edg_python_shutdown();
        return result;
    }
    fprintf(stderr, "native 模式暂由 edg.py 驱动: %s\n", argv[2]);
    return 0;
}