/**
 * Call instrumentation for e9patch to print out addresses of
 * all instrumented instructions.
 *
 * Should be copied into the folder e9patch/example,
 * and compiled with ./e9compile.sh example/printaddr.c
 *
 **/

#include "stdlib.c"

FILE* log_fd = NULL;

void init(int argc, const char **argv, char **envp, void *dynp)
{
    environ = envp;

    const char *filename = getenv("TRACE_FILE");
    if (filename == NULL) {
        log_fd = stderr;
    } else {
        log_fd = fopen(filename, "a+");
    }
}

/**
 * Usage: call entry(addr)@printaddr
 **/
void print_addr(const void *addr) {
    fprintf(log_fd, "%p\n", addr);
    fflush(log_fd);
}

/**
 * Usage: call entry(addr)@printaddr
 **/
void print_line(const char* line) {
    fprintf(log_fd, "%s\n", line);
    fflush(log_fd);
}


void fini(){
    fflush(log_fd);
    if(log_fd != NULL){
        fclose(log_fd);
    }
}