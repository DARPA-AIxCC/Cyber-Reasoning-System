# Basic POC for fuzzing the exemplar kernel setup

## Usage
1. Apply all cp patches to the public AIxCC cp repository
2. `./run.sh pull_source`
3. Apply all kernel patches to the kernel in src 
4. Copy the kernel-files to `src/test_harnesses`
5. Build and run (`./run.sh build` and `./pop.sh`)

From here you can fuzz the kernel with AFL++ or get a trace using KCOV.
By default the trace printing is commented out in the linux test harness.
To fuzz with AFL, you need to instrument the test harness by modifying `build.sh` or using e9AFL on your host machine to instrument the harness binary in `out`.


