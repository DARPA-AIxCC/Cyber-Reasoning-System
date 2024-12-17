#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <string.h>
#include <fcntl.h>
#include <sys/shm.h>
#include <linux/types.h>
#include <stdbool.h>

struct kcov_remote_arg {
    __u32           trace_mode;
    __u32           area_size;
    __u32           num_handles;
    __aligned_u64   common_handle;
    __aligned_u64   handles[0];
};

#define KCOV_INIT_TRACE             _IOR('c', 1, unsigned long)
#define KCOV_ENABLE                 _IO('c', 100)
#define KCOV_DISABLE                _IO('c', 101)
#define KCOV_REMOTE_ENABLE          _IOW('c', 102, struct kcov_remote_arg)
#define COVER_SIZE                  (64<<10)

#define KCOV_SUBSYSTEM_COMMON       (0x00ull << 56)
#define KCOV_COMMON_ID              0x42

#define KCOV_SUBSYSTEM_MASK (0xffull << 56)
#define KCOV_INSTANCE_MASK  (0xffffffffull)

#define KCOV_TRACE_PC  0
#define KCOV_TRACE_CMP 1

#define KCOV_SUBSYSTEM_NET  (0x01ull << 56)

int fd;
unsigned long *cover, n, i;
uint8_t *afl_area_ptr;
int dmesg_fs = -1;
bool trace_active = false;

void kcov_setup() {
    /* A single fd descriptor allows coverage collection on a single
     * thread.
     */
    fd = open("/sys/kernel/debug/kcov", O_RDWR);
    if (fd == -1)
            perror("open"), exit(1);
    /* Setup trace mode and trace size. */
    if (ioctl(fd, KCOV_INIT_TRACE, COVER_SIZE))
            perror("ioctl"), exit(1);
    /* Mmap buffer shared between kernel- and user-space. */
    cover = (unsigned long*)mmap(NULL, COVER_SIZE * sizeof(unsigned long),
                                 PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if ((void*)cover == MAP_FAILED)
            perror("mmap"), exit(1);


  	const char *afl_shm_id_str = getenv("__AFL_SHM_ID");
  	if (afl_shm_id_str != NULL) {
  		int afl_shm_id = atoi(afl_shm_id_str);
  		// shm_id 0 is fine
  		afl_area_ptr = shmat(afl_shm_id, NULL, 0);
  	}
  
  	if (afl_area_ptr == NULL) {
  		fprintf(stderr, "[-] Running outside of AFL\n");
  		afl_area_ptr = calloc(1, 1 << 16);
  	}

    /* Read on dmesg /dev/kmsg for crashes. */
  	dmesg_fs = open("/dev/kmsg", O_RDONLY | O_NONBLOCK);
  	if (dmesg_fs < 0) {
  		perror("open(/dev/kmsg)"), exit(1);
  	}
  	lseek(dmesg_fs, 0, SEEK_END);
}

static inline __u64 kcov_remote_handle(__u64 subsys, __u64 inst)
{
    if (subsys & ~KCOV_SUBSYSTEM_MASK || inst & ~KCOV_INSTANCE_MASK)
            return 0;
    return subsys | inst;
}


void kcov_start_trace() {
  	fprintf(stderr, "[$] start trace\n");
    /* Enable LOCAL coverage collection on the current thread. 
        NOT currently used as UDP packet is received in soft IRQ
    */

    // if (!trace_active && ioctl(fd, KCOV_ENABLE, KCOV_TRACE_PC))
    //         perror("ioctl"), exit(1);

    struct kcov_remote_arg *arg;


    /* Enable coverage collection via common handle and from USB bus #1. */
    arg = calloc(1, sizeof(*arg) + sizeof(uint64_t)*4);
    if (!arg)
            perror("calloc"), exit(1);
    arg->trace_mode = KCOV_TRACE_PC;
    arg->area_size = COVER_SIZE;
    arg->num_handles = 4;
    arg->common_handle = kcov_remote_handle(KCOV_SUBSYSTEM_COMMON,
                                                    KCOV_COMMON_ID);
    arg->handles[0] = kcov_remote_handle(KCOV_SUBSYSTEM_NET,
                                            1);
    arg->handles[1] = kcov_remote_handle(KCOV_SUBSYSTEM_NET,
                                            2);
    arg->handles[2] = kcov_remote_handle(KCOV_SUBSYSTEM_NET,
                                            3);
    arg->handles[3] = kcov_remote_handle(KCOV_SUBSYSTEM_NET,
                                            4);

    // fprintf(stderr, "handle[0] is %llx\n", arg->handles[0]);
    if (ioctl(fd, KCOV_REMOTE_ENABLE, arg))
            perror("ioctl"), free(arg), exit(1);
    free(arg);
  
    /* Reset coverage from the tail of the ioctl() call. */
    __atomic_store_n(&cover[0], 0, __ATOMIC_RELAXED);
    trace_active = true;
}

void kcov_stop_trace() {
    usleep(100000); // 100ms to ensure that packet has been asyncronously processed
  	fprintf(stderr, "[x] stop trace\n");
    /* Disable coverage collection for the current thread. After this call
     * coverage can be enabled for a different thread.
     */
    if (trace_active && ioctl(fd, KCOV_DISABLE, 0))
         perror("ioctl"), exit(1);
    trace_active = false;
}

static inline uint64_t hash64to64(uintptr_t x)
{
    x ^= x >> 30;
    x *= 0xbf58476d1ce4e5b9U;
    x ^= x >> 27;
    x *= 0x94d049bb133111ebU;
    x ^= x >> 31;
    return x;
}

static inline uint64_t hash64_combine(uintptr_t lhs,  uintptr_t rhs)
{
    lhs ^= rhs + 0x9e3779b9 + (lhs << 6) + (lhs >> 2);
    return lhs;
}


void kcov_update_afl() {
                /* Read recorded %rip */
                int i;
                uint64_t afl_prev_hash = 0;
    		n = __atomic_load_n(&cover[0], __ATOMIC_RELAXED);
                for (i = 0; i < n; i++) {
                        uint64_t current_loc = cover[i + 1];
                        uint64_t hash = hash64to64((uintptr_t) current_loc);
                        uint64_t mixed = hash64_combine(hash, afl_prev_hash);
      			// fprintf(stderr, "%p --> %p + %p = %p \% 65536 = %p\n", current_loc, hash, afl_prev_hash, mixed, mixed % 65536);
                        afl_prev_hash = hash;

                        uint8_t *s = &afl_area_ptr[mixed % 65536];
                        int r = __builtin_add_overflow(*s, 1, s);
                        if (r) {
                                /* Boxing. AFL is fine with overflows,
                                 * but we can be better. Drop down to
                                 * 128 on overflow. */
                                *s = 128;
                        }
                }
}

void abort_on_kernel_panic() {

  /* Check dmesg if there was something interesting */
	int crashed = 0;
	while (1) {
			// /dev/kmsg gives us one line per read
			char buf[8192];
			int r = read(dmesg_fs, buf, sizeof(buf) - 1);
			if (r <= 0) {
				break;
			}

			buf[r] = '\x00';
			if (strstr(buf, "Call Trace") != NULL ||
			    strstr(buf, "RIP:") != NULL ||
			    strstr(buf, "Code:") != NULL) {
				crashed += 1;
			}
	}
  if (crashed) {
  	fprintf(stderr, "[!] BUG detected\n");
  	// forksrv_status(forksrv, 139);
    abort();
  } else {
  	fprintf(stderr, "[*] No bug detected\n");
  	// forksrv_status(forksrv, 0);
  }
  
}

void kcov_print_trace() {
    /* Read number of PCs collected. */
    n = __atomic_load_n(&cover[0], __ATOMIC_RELAXED);
    for (i = 0; i < n; i++)
            printf("0x%lx\n", cover[i + 1]);
  	fprintf(stderr, "[@] done printing trace\n");
}

void kcov_teardown() {
    /* Free resources. */
    if (munmap(cover, COVER_SIZE * sizeof(unsigned long)))
            perror("munmap"), exit(1);
    if (close(fd))
            perror("close"), exit(1);
}

