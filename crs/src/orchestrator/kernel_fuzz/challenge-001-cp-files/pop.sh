#!/bin/bash
set -e
# --qemu-opts -append nokaslr 

# timeout 30s qemu-system-x86_64 -kernel /src/arch/x86/boot/bzImage -drive "if=none,id=root-disk,file=/LibAFL/2024-06-06-aixcc-kernelfuzz-rootfs.qcow2" -device virtio-blk-pci,drive=root-disk -nographic -serial mon:stdio
# ./target/debug/qemu_systemmode -L target/debug/qemu-libafl-bridge/pc-bios/ 
CMD="virtme-run --verbose --show-boot-console --kimg  /src/arch/x86/boot/bzImage --memory 2G --mods=auto --rwdir=/out --disable-microvm"
CMD="/bin/bash"

## Inside docker to create qcow2 disk image
# qemu-img create -f qcow2 root.qcow2 200G
# /vng/virtme-run --verbose --show-boot-console --kimg /src/arch/x86_64/boot/bzImage --memory 2G --mods=auto --blk-disk newroot=root.qcow2 --script-sh "mkfs.ext4 /dev/vda && mount /dev/vda '$(pwd)/mnt' && rsync -v -a --one-file-system --exclude '$(pwd)/mnt' --exclude '$(pwd)/root.qcow2' / '$(pwd)/mnt'/"

## To run VM using virtme + qcow2 image
# /vng/virtme-run --verbose --show-boot-console --kimg src/arch/x86_64/boot/bzImage --memory 2G --mods=auto --root-disk myroot=/vng/root.qcow2 -q=-monitor -q=unix:monitor.sock,server,nowait 
## can append to get qemu commands
# --dry-run --show-command


docker run -it -v $(pwd)/virtme-ng:/vng -v  $(pwd)/LibAFL:/LibAFL -v $(pwd)/src/:/src -v $(pwd)/out/:/out exemplar-cp-linux:base sh -c "$CMD"



# docker run -it -v $(pwd)/virtme-ng:/vng -v $(pwd)/src/:/src -v $(pwd)/out/:/out exemplar-cp-linux:base sh -c "$CMD"


