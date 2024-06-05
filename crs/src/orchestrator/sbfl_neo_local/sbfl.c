/*
 *
 *  ____  ____  _____ _     
 * / ___|| __ )|  ___| |    
 * \___ \|  _ \| |_  | |    
 *  ___) | |_) |  _| | |___ 
 * |____/|____/|_|   |_____|
 *
 * Gregory J. Duck
 */

#include "stdlib.c"

#define option_tty  true

#define RED         (option_tty? "\33[31m": "")
#define GREEN       (option_tty? "\33[32m": "")
#define YELLOW      (option_tty? "\33[33m": "")
#define OFF         (option_tty? "\33[0m" : "")

#define EXIT_ERROR  66
#define EXIT_CRASH  67

#define PATH_MAX    4096

/*
 * Error reporting.
 */
#define error(msg, ...)                                     	\
    do {                                                    	\
        fprintf(stderr, "%serror%s: " msg "\n", RED, OFF,   	\
            ##__VA_ARGS__);                                 	\
        exit(EXIT_ERROR);                                      	\
    } while (false)
#define warning(msg, ...)                                     	\
    do {                                                    	\
        fprintf(stderr, "%swarning%s: " msg "\n", YELLOW, OFF,	\
            ##__VA_ARGS__);                                 	\
    } while (false)

struct ENTRY
{
    struct
    {
        const char *file;       // LINE filename
        unsigned line;          // LINE numner
    } LINE;
    struct
    {
        uint32_t exec;          // Executed count.
        uint32_t nexe;          // Not executed count.
    } pass;
    struct
    {
        uint32_t exec;          // Executed count.
        uint32_t nexe;          // Not executed count.
    } fail;

    size_t timestamp;           // When executed?
};
typedef struct ENTRY ENTRY;

struct LOC
{
    const char *file;
    size_t len;
    unsigned line;
};
typedef struct LOC LOC;

typedef int (*compare_t)(const void *, const void *);

struct GLOBAL
{
    mutex_t lock;               // Global lock
    struct malloc_pool_s *pool; // Malloc pool
    const char *progname;       // This program's name
    const char *filename;       // Global profile file
    void *INFO;                 // Global profile info
    uint32_t pass;              // Number passed?
    uint32_t fail;              // Number failed?
    bool failed;                // Did we fail?
    bool disabled;              // Disabled?
    bool output;                // Did we already write output?
    size_t timestamp;           // Timestamp
    LOC start;                  // Start location
    LOC crash;                  // Artificial crash location
};
typedef struct GLOBAL GLOBAL;

// Global shared state:
#define S           ((GLOBAL *)0x213000)

void fini(void);

static int compare(const void *a, const void *b)
{
    const ENTRY *A = (const ENTRY *)a, *B = (const ENTRY *)b;
    int cmp = 0;
    if (cmp == 0 && A->LINE.line < B->LINE.line) cmp = -1;
    if (cmp == 0 && A->LINE.line > B->LINE.line) cmp = 1;
    if (cmp == 0) cmp = strcmp(A->LINE.file, B->LINE.file);
    return cmp;
}

static bool match(const LOC *loc, const char *file, unsigned line)
{
    if (loc->line != line || loc->file == NULL)
        return false;
    size_t len = strlen(file);
    if (len >= loc->len && strcmp(file + (len - loc->len), loc->file) == 0)
        return true;
    else
        return false;
}

void hit(const char *file, unsigned line, void *addr)
{
    if (line == 0)
        return;
    if (S->disabled)
    {
        if (!match(&S->start, file, line))
            return;
        S->disabled = false;
    }

    ENTRY key_0, *key = &key_0;
    key_0.LINE.file = file;
    key_0.LINE.line = line;
    if (mutex_lock(&S->lock) < 0)
        return;

    void *node = pool_tfind(S->pool, key, &S->INFO, compare);
    if (node == NULL)
    {
        key = (ENTRY *)malloc(sizeof(ENTRY));
        if (key == NULL)
            error("failed to allocated %zu bytes for entry: %s",
                sizeof(ENTRY), strerror(errno));
        memset(key, 0x0, sizeof(*key));
        key->LINE.file = file;
        key->LINE.line = line;
        key->pass.nexe = S->pass;
        key->fail.nexe = S->fail;
        node = pool_tsearch(S->pool, key, &S->INFO, compare);
    }
    ENTRY *entry = *(ENTRY **)node;
    S->timestamp++;
    bool first = (entry->timestamp == 0);
    entry->timestamp = S->timestamp;

    if (first && match(&S->crash, file, line))
    {
        // Artificial "crash":
        S->failed = true;
        fini();
        exit(EXIT_CRASH);
    }

    mutex_unlock(&S->lock);
}

static const char *get_str(const char *s)
{
    static void *CACHE = NULL;
    void *node = pool_tfind(S->pool, s, &CACHE, (compare_t)strcmp);
    if (node == NULL)
    {
        s = strdup(s);
        if (s == NULL)
            error("failed to duplicate string: %s", strerror(errno));
        node = pool_tsearch(S->pool, s, &CACHE, (compare_t)strcmp);
    }
    s = *(const char **)node;
    return s;
}


static void parse(const char *filename, FILE *stream)
{
    char prog[PATH_MAX+1];
    if (fscanf(stream, " PASS=%u FAIL=%u PROG=%4096s", &S->pass, &S->fail, prog) != 3)
    {
        warning("failed to parse \"%s\", missing file header; resetting",
            filename);
        S->pass = S->fail = 0;
        return;
    }
    if (strcmp(prog, S->progname) != 0)
    {
        warning("file \"%s\" is for a different program (%s); resetting",
            filename, prog);
        S->pass = S->fail = 0;
        return;
    }
    uint32_t pexec, pnexe, fexec, fnexe;
    char path[PATH_MAX+1], score[32+1];
    unsigned line;
    unsigned count = 0;
    while (true)
    {
        char c;
        while (isspace(c = getc(stream)))
            ;
        if (c == EOF)
            break;
        path[0] = c;
        unsigned i;
        for (i = 1; (c = getc(stream)) != ':' && c != EOF &&
                i < sizeof(path)-1; i++)
            path[i] = c;
        if (c == EOF)
            break;
        path[i] = '\0';
        if (fscanf(stream, "%u: PX=%u PN=%u FX=%u FN=%u score=%32s",
                &line, &pexec, &pnexe, &fexec, &fnexe, score) != 6)
            break;
        ENTRY key_0, *key = &key_0;
        key_0.LINE.file = path;
        key_0.LINE.line = line;
        void *node = pool_tfind(S->pool, &key, &S->INFO, compare);
        if (node != NULL)
            error("duplicate node detected for line %s:%u", path, line);
        ENTRY *entry = (ENTRY *)malloc(sizeof(ENTRY));
        if (entry == NULL)
            error("failed to allocated %zu bytes for entry: %s",
                sizeof(ENTRY), strerror(errno));
        entry->LINE.file = get_str(path);
        entry->LINE.line = line;
        entry->pass.exec = pexec;
        entry->pass.nexe = pnexe;
        entry->fail.exec = fexec;
        entry->fail.nexe = fnexe;
        entry->timestamp = 0;
        (void)pool_tsearch(S->pool, entry, &S->INFO, compare);
        count++;
        fprintf(stream, "%s:%d: PX=%u PN=%u FX=%u FN=%u\n",
            entry->LINE.file, entry->LINE.line,
            entry->pass.exec, entry->pass.nexe,
            entry->fail.exec, entry->fail.nexe);
    }
    fprintf(stderr, "%sSBFL%s: read %zu entries from \"%s\"...\n",
        GREEN, OFF, count, filename);
}

static void parse_loc(const char *str, LOC *loc)
{
    char buf[BUFSIZ];
    int colon = -1;
    for (int i = 0; i < sizeof(buf)-1 && str[i] != '\0'; i++)
    {
        buf[i] = str[i];
        colon = (str[i] == ':'? i: colon);
    }
    if (colon <= 0 || str[colon+1] == '\0')
        error("failed to parse location \"%s\"; missing `:'", loc);
    int val = atoi(str+colon+1);
    if (val <= 0)
        error("failed to parse location \"%s\"; inlocid line", loc);
    loc->line = (unsigned)val;
    buf[colon] = '\0';
    loc->file = strdup(buf);
    if (loc->file == NULL)
        error("failed to duplicat filename: %s", strerror(errno));
    loc->len = strlen(loc->file);
}

static void handler(int sig);

#include <stddef.h>
#include <linux/prctl.h>
#include <linux/seccomp.h>
#include <linux/filter.h>

void init(int argc, char **argv, char **envp)
{
    size_t size = MA_PAGE_SIZE;
    void *ptr = mmap((void *)S, size, PROT_READ | PROT_WRITE,
        MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (ptr == MAP_FAILED)
    	error("failed to map common area: %s", strerror(errno));
	if (ptr != (void *)S)
    {
        fprintf(stderr, "%sSBFL%s: skip init\n", GREEN, OFF);
        // Already initialized by another binary:
        (void)munmap(ptr, size);
        return;
    }
    fprintf(stderr, "%sSBFL%s: init\n", GREEN, OFF);
    S->pool = &malloc_pool;

    char path[PATH_MAX+1] = {0};
    if (readlink("/proc/self/exe", path, sizeof(path)-1) < 0)
        error("failed to read program name: %s", strerror(errno));
    size_t len = strlen(path);
    char *progname = (char *)pool_malloc(S->pool, len+1);
    if (progname == NULL)
        error("failed to duplicate program name: %s", strerror(errno));
    memcpy(progname, path, len+1);
    S->progname = progname;

    environ = envp;
    S->filename = "SBFL.prof";
    const char *val = getenv("SBFL_FILE");
    S->filename = (val != NULL? val: S->filename);
    
    FILE *stream = fopen(S->filename, "r");
    if (stream != NULL)
    {
        parse(S->filename, stream);
        fclose(stream);
    }

    val = getenv("SBFL_CRASH");
    if (val != NULL)
        parse_loc(val, &S->crash);

    val = getenv("SBFL_START");
    if (val != NULL)
    {
        S->disabled = true;
        parse_loc(val, &S->start);
    }

    // Make sure crashes call fini()
    signal(SIGSEGV, handler);
    signal(SIGBUS,  handler);
    signal(SIGFPE,  handler);
    signal(SIGILL,  handler);
    signal(SIGABRT, handler);

#if 0
    // Block any attempt by the program to install other handlers:
    struct sock_filter filter[] =
    {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_rt_sigaction, 0, 4),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[2])),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, 0x0, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | 0),       // "succeed"
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | ENOSYS),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
    };
    struct sock_fprog fprog =
    {
        (unsigned short)(sizeof(filter) / sizeof(filter[0])),
        filter
    };
    if (syscall(SYS_seccomp, SECCOMP_SET_MODE_FILTER, /*flags=*/0x0, &fprog)
            < 0)
        warning("failed to set seccomp filter: %s", strerror(errno));
#endif
}

#define RADIX   1000000
static uint64_t score(uint32_t px, uint32_t pn, uint32_t fx, uint32_t fn)
{
    size_t d = (fx + fn) * (fx + px);
    d = (d == 0? 1: d);
    size_t s;
    const double R = RADIX;
    asm volatile
    (
        "cvtsi2sd %1, %%xmm0\n"
        "sqrtsd %%xmm0, %%xmm0\n"
        "cvtsi2sd %2, %%xmm1\n"
        "divsd %%xmm0, %%xmm1\n"
        "mulsd %3, %%xmm1\n"
        "cvttsd2si %%xmm1, %0" 
        : "=r"(s) : "r"(d), "r"((size_t)fx), "m"(R) 
    );
    return s;
}

static int trace_compare(const void *a, const void *b)
{
    const ENTRY *A = *(ENTRY **)a;
    const ENTRY *B = *(ENTRY **)b;
    if (A->timestamp < B->timestamp) return -1;
    if (A->timestamp > B->timestamp) return 1;
    return 0;
}

void fini(void)
{
    if (S->output)
        return;
    S->output = true;

    FILE *stream = fopen(S->filename, "w");
    if (stream == NULL)
        error("failed to open file \"%s\" for writing: %s",
            S->filename, strerror(errno));
    S->pass += (S->failed? 0: 1);
    S->fail += (S->failed? 1: 0);
    fprintf(stream, "PASS=%u\nFAIL=%u\nPROG=%s\n", S->pass, S->fail, S->progname);
    size_t count = 0, hit = 0, i = 0;
    for (void *n = tmin(&S->INFO); n != NULL; n = tnext(n))
    {
        ENTRY *entry = *(ENTRY **)n;
        count++;
        if (entry->timestamp > 0)
        {
            hit++;
            entry->pass.exec += (S->failed? 0: 1);
            entry->fail.exec += (S->failed? 1: 0);
        }
        else
        {
            entry->pass.nexe += (S->failed? 0: 1);
            entry->fail.nexe += (S->failed? 1: 0);
        }
        uint64_t s = score(
            entry->pass.exec, entry->pass.nexe,
            entry->fail.exec, entry->fail.nexe);
        fprintf(stream, "%s:%d: PX=%u PN=%u FX=%u FN=%u score=%zu.%.6zu\n",
            entry->LINE.file, entry->LINE.line,
            entry->pass.exec, entry->pass.nexe,
            entry->fail.exec, entry->fail.nexe,
            s / RADIX, s % RADIX);
    }
    fclose(stream);
    fprintf(stderr, "%sSBFL%s: write %zu entries to \"%s\"...\n",
        GREEN, OFF, count, S->filename);

    if (!S->failed || hit == 0)
        return;

    ENTRY **trace = (ENTRY **)malloc(hit * sizeof(ENTRY *));
    if (trace == NULL)
        error("failed to allocate memory for trace: %s", strerror(errno));
    for (void *n = tmin(&S->INFO); n != NULL; n = tnext(n))
    {
        ENTRY *entry = *(ENTRY **)n;
        if (entry->timestamp == 0)
            continue;
        trace[i++] = entry;
    }
    qsort(trace, hit, sizeof(ENTRY *), trace_compare);

    const char *filename = "SBFL.trace";
    stream = fopen(filename, "w");
    if (stream == NULL)
        error("fail to open \"%s\" for writing: %s", filename,
            strerror(errno));
    for (size_t i = 0; i < hit; i++)
    {
        ENTRY *entry = trace[i];
        uint64_t s = score(
            entry->pass.exec, entry->pass.nexe,
            entry->fail.exec, entry->fail.nexe);
        fprintf(stream, "%s:%u timestamp=%zu score=%zu.%.6zu\n",
            entry->LINE.file, entry->LINE.line,
            entry->timestamp,
            s / RADIX, s % RADIX);
    }
    fclose(stream);
    fprintf(stderr, "%sSBFL%s: write %zu entries to \"%s\"...\n",
        GREEN, OFF, hit, filename);
}

void quit(int code)
{
    // Make sure _exit() and _Exit() call fini()
    fini();
    exit(code);
    abort();
}

static void handler(int sig)
{
    fprintf(stderr, "%s%s%s\n", RED, strsignal(sig), OFF);
    S->failed = true;
    fini();
    exit(EXIT_CRASH);
}

