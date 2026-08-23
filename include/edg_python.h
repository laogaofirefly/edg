#ifndef EDG_PYTHON_H
#define EDG_PYTHON_H

#ifdef __cplusplus
extern "C" {
#endif

/* Optional CPython embedding bridge. Returns non-zero on failure. */
int edg_python_init(void);
int edg_python_run_file(const char *path);
int edg_python_run_string(const char *source);
void edg_python_shutdown(void);
int edg_python_available(void);

#ifdef __cplusplus
}
#endif
#endif