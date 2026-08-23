/* Transitional native CLI: keeps the Python compiler embeddable while exposing
 * a stable C entry point. The generated program itself remains Python-free. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <process.h>
#else
#include <unistd.h>
#include <sys/wait.h>
#endif

int main(int argc, char **argv) {
    char **args;
    int i, status;
    if (argc < 2) {
        fprintf(stderr, "用法: edgc <run|check|native|emit-c> ...\n");
        return 2;
    }
    args = calloc((size_t)argc + 2, sizeof(*args));
    if (!args) return 1;
    args[0] = "python3";
    args[1] = "edg.py";
    for (i = 1; i < argc; ++i) args[i + 1] = argv[i];
    args[argc + 1] = NULL;
#if defined(_WIN32)
    status = _spawnvp(_P_WAIT, args[0], (const char * const *)args);
    free(args);
    return status < 0 ? 127 : status;
#else
    {
        pid_t pid = fork();
        if (pid < 0) { free(args); return 127; }
        if (pid == 0) { execvp(args[0], args); _exit(127); }
        free(args);
        if (waitpid(pid, &status, 0) < 0) return 127;
    }
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    return 128;
#endif
}