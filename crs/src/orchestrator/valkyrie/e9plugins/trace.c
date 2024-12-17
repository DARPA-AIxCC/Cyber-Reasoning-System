/*
 * TRACE instrumentation.
 */

#include "stdlib.c"


/*
 * Entry point.
 *
 * call entry(addr,instr,size,asm)@print
 */
void entry(const void *addr, const uint8_t *instr, size_t size,
    const char *_asm)
{
    static mutex_t mutex = MUTEX_INITIALIZER;
    if (mutex_lock(&mutex) < 0)
        return;

    clearerr_unlocked(stderr);
    fprintf_unlocked(stderr, "%.16lx", addr);
    fputs_unlocked("\n", stderr);
    fflush_unlocked(stderr);
    mutex_unlock(&mutex);
}

void init(void)
{
    setvbuf(stderr, NULL, _IOFBF, 0);
}
