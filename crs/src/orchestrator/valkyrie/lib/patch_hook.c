
#define LIBDL
#include "stdlib.c"

void *external_patch = NULL;

void entry(const char *expr, const void *base, const void *addr, void *state)
{
    dlcall(external_patch, expr, base, addr, state);
}

void init(int argc, char **argv, char **envp, void *dynamic)
{
    if (dlinit(dynamic) != 0)
    {
        fprintf(stderr, "dlinit() failed: %s\n", strerror(errno));
        abort();
    }

    void *handle = dlopen("./libpatch.so", RTLD_NOW);
    if (handle == NULL)
    {
        fprintf(stderr, "dlopen(\"./libpatch.so\") failed\n");
        abort();
    }

    external_patch = dlsym(handle, "patch");
    if (external_patch == NULL)
    {
        fprintf(stderr, "dlsym(\"patch\") failed\n");
        abort();
    }
}

