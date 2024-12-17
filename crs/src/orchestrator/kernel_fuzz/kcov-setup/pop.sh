#!/bin/bash
set -e
# --qemu-opts -append nokaslr 

CMD="virtme-run --verbose --show-boot-console --kimg  /src/arch/x86/boot/bzImage --memory 2G --mods=auto --rwdir=/out --disable-microvm"
docker run -it -v $(pwd)/src/:/src -v $(pwd)/out/:/out exemplar-cp-linux sh -c "$CMD"
