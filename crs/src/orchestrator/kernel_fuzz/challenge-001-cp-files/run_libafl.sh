# QEMU
/usr/bin/qemu-system-x86_64 \
  -m 2G \
  -machine accel=kvm:tcg \
  -device i6300esb,id=watchdog0 \
  -cpu host \
  -parallel none \
  -net none \
  -echr 1 \
  -chardev file,path=/proc/self/fd/2,id=dmesg \
  -device virtio-serial-pci \
  -device virtconsole,chardev=dmesg \
  -chardev stdio,id=console,signal=off,mux=on \
  -serial chardev:console \
  -mon chardev=console \
  -vga none \
  -display none \
  -drive if=none,id=root-disk,file=/challenge-001-linux-cp/src/root.qcow2 \
  -device virtio-blk-pci,drive=root-disk,serial=myroot \
  -kernel /challenge-001-linux-cp/src/linux_kernel/arch/x86/boot/bzImage \
  -append 'nr_open=1048576 root=/dev/vda virtme_link_mods=/challenge-001-linux-cp/src/linux_kernel/.virtme_mods/lib/modules/0.0.0 console=hvc0 earlyprintk=serial,ttyS0,115200 virtme_console=ttyS0 psmouse.proto=exps "virtme_stty_con=rows 48 cols 180 iutf8" TERM=xterm virtme_root_user=1 raid=noautodetect ro init=/vng/virtme/guest/bin/virtme-ng-init' \
  -monitor unix:monitor.sock,server,nowait




# LibAFL
/challenge-001-linux-cp/LibAFL-kernel/fuzzers/qemu_systemmode/target/debug/qemu_systemmode\
  -L /challenge-001-linux-cp/LibAFL-kernel/fuzzers/qemu_systemmode/target/debug/qemu-libafl-bridge/pc-bios \
  -m 2G \
  -device i6300esb,id=watchdog0 \
  -machine q35\
  -parallel none \
  -net none \
  -echr 1 \
  -chardev file,path=/proc/self/fd/2,id=dmesg \
  -device virtio-serial-pci \
  -device virtconsole,chardev=dmesg \
  -chardev stdio,id=console,signal=off,mux=on \
  -serial chardev:console \
  -mon chardev=console \
  -vga none \
  -display none \
  -drive if=none,id=root-disk,file=/challenge-001-linux-cp/src/root.qcow2 \
  -device virtio-blk-pci,drive=root-disk,serial=myroot \
  -kernel /challenge-001-linux-cp/src/linux_kernel/arch/x86/boot/bzImage \
  -append 'nr_open=1048576 root=/dev/vda virtme_link_mods=/challenge-001-linux-cp/src/linux_kernel/.virtme_mods/lib/modules/0.0.0 console=hvc0 earlyprintk=serial,ttyS0,115200 virtme_console=ttyS0 psmouse.proto=exps "virtme_stty_con=rows 48 cols 180 iutf8" TERM=xterm virtme_root_user=1 raid=noautodetect ro init=/vng/virtme/guest/bin/virtme-ng-init' \
  -monitor unix:monitor.sock,server,nowait
