#include "edg_python.h"
#include <stdio.h>

#ifdef EDG_WITH_PYTHON
#include <Python.h>

static int g_initialized = 0;

int edg_python_init(void) {
    if (!Py_IsInitialized()) Py_Initialize();
    g_initialized = Py_IsInitialized() ? 1 : 0;
    return g_initialized ? 0 : 1;
}

int edg_python_run_file(const char *path) {
    FILE *file;
    int result;
    if (!path || edg_python_init() != 0) return 1;
    file = fopen(path, "r");
    if (!file) return 1;
    result = PyRun_SimpleFile(file, path);
    fclose(file);
    return result == 0 ? 0 : 1;
}

int edg_python_run_string(const char *source) {
    if (!source || edg_python_init() != 0) return 1;
    return PyRun_SimpleString(source) == 0 ? 0 : 1;
}

void edg_python_shutdown(void) {
    if (g_initialized && Py_IsInitialized()) Py_FinalizeEx();
    g_initialized = 0;
}

int edg_python_available(void) { return 1; }

#else

int edg_python_init(void) { return 1; }
int edg_python_run_file(const char *path) { (void)path; return 1; }
int edg_python_run_string(const char *source) { (void)source; return 1; }
void edg_python_shutdown(void) {}
int edg_python_available(void) { return 0; }

#endif