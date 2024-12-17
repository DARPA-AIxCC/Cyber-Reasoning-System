#!/bin/bash

# -net user,host=10.0.2.10,hostfwd=tcp:127.0.0.1:2222-:22 -net nic,model=e1000

# /LibAFL/fuzzers/qemu_systemmode/target/debug/qemu_systemmode \
/usr/bin/qemu-system-x86_64 \
  -L /LibAFL/fuzzers/qemu_systemmode/target/debug/qemu-libafl-bridge/pc-bios \
  -m 2G \
  -device i6300esb,id=watchdog0 \
  -machine q35 \
  -net none \
  -parallel none \
  -echr 1 \
  -chardev file,path=/proc/self/fd/2,id=dmesg \
  -device virtio-serial-pci \
  -device  virtconsole,chardev=dmesg \
  -chardev stdio,id=console,signal=off,mux=on \
  -serial chardev:console \
  -mon chardev=console \
  -vga none \
  -display none \
  -drive if=none,id=root-disk,file=/vng/bak.qcow2 \
  -device virtio-blk-pci,drive=root-disk,serial=myroot \
  -kernel src/arch/x86_64/boot/bzImage \
  -append 'nr_open=1048576 root=/dev/vda console=hvc0 earlyprintk=serial,ttyS0,115200 virtme_console=ttyS0 psmouse.proto=exps "vi rtme_stty_con=rows 26 cols 122 iutf8" TERM=xterm virtme_root_user=1 raid=noautodetect rw init=/vng/virtme/guest/bin/virtme-ng-init' \
  -monitor unix:monitor.sock,server,nowait
