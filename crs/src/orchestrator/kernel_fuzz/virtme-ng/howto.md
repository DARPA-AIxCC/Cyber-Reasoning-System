I built the vng project on the host, as I did not (yet?) include the build tools in the container setup
```sh
$ git submodule update --init --recursive
$ make
```

I then downloaded a linux source tree to the linux subfolder and built it using `vng` (note: this automatically enables ext4)
```sh
$ git clone git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git --branch v6.9 --depth 1
$ cd linux
$ ../vng --build
$ ../vng -- uname -a
# Linux virtme-ng 6.9.0-virtme #1 SMP PREEMPT_DYNAMIC Thu Jun  6 01:26:58 BST 2024 x86_64 GNU/Linux
$ cd ..
```

Prepare a docker image to work in a "realistic" environment, and start it with the vng sources mounted to `/vng`
```sh
$ docker build . -t vng
$ docker run --rm -it --device /dev/kvm --tmpfs /dev/shm:exec -v "$(pwd)":/vng vng
$ cd /vng/linux
```

Let's prepare a new root file system in `/vng/linux`
```sh
$ qemu-img create -f qcow2 root.qcow2 200G
$ mkdir mnt
$ ../virtme-run --verbose --show-boot-console --kimg arch/x86_64/boot/bzImage --memory 2G --mods=auto --blk-disk newroot=root.qcow2 --script-sh "mkfs.ext4 /dev/vda && mount /dev/vda '$(pwd)/mnt' && rsync -v -a --one-file-system --exclude '$(pwd)/mnt' --exclude '$(pwd)/root.qcow2' / '$(pwd)/mnt'/"
$ rmdir mnt
```

OPTIONAL: For development, I like to create a snapshot of the root file system that we can very quickly rebuild if we want to change something (requires the `--rw` parameter to `virtme-run` to be set, so it is probably not necessary for the final system)
```sh
qemu-img create -f qcow2 temp.qcow2 -b root.qcow2 -F qcow2
```

To start a vm, run the following command (still in the `/vng/linux` directory)
```sh
$ ../virtme-run --verbose --show-boot-console --kimg arch/x86_64/boot/bzImage --memory 2G --mods=auto --root-disk myroot=temp.qcow2 -q=-monitor -q=unix:monitor.sock,server,nowait
```

This command is equivalent to directly calling:
```sh
$ /usr/bin/qemu-system-x86_64 -m 2G -machine accel=kvm:tcg -device i6300esb,id=watchdog0 -cpu host -parallel none -net none -echr 1 -chardev file,path=/proc/self/fd/2,id=dmesg -device virtio-serial-pci -device virtconsole,chardev=dmesg -chardev stdio,id=console,signal=off,mux=on -serial chardev:console -mon chardev=console -vga none -display none -drive if=none,id=root-disk,file=temp.qcow2 -device virtio-blk-pci,drive=root-disk,serial=myroot -kernel arch/x86_64/boot/bzImage -append 'nr_open=1073741816 root=/dev/vda console=hvc0 earlyprintk=serial,ttyS0,115200 virtme_console=ttyS0 psmouse.proto=exps "virtme_stty_con=rows 25 cols 238 iutf8" TERM=xterm virtme_root_user=1 raid=noautodetect ro init=/vng/virtme/guest/bin/virtme-ng-init' -monitor unix:monitor.sock,server,nowait
```

This not only starts the vm, it also creates a unix domain socket at `monitor.sock`, which we can interact with using, e.g., `socat`. Since the vng folder is mounted from the host, we can even use `socat` on the host, but due to permission mismatches (the docker container runs as uid 0), we need to `sudo` it:
```sh
socat -,echo=0,icanon=0 unix-connect:monitor.sock
# you can now "savevm myname", "loadvm myname" and "delvm myname"
```

To run a command `echo moo`, you can use:
```sh
$ ../virtme-run --verbose --show-boot-console --kimg arch/x86_64/boot/bzImage --memory 2G --mods=auto --root-disk myroot=temp.qcow2 -q=-monitor -q=unix:monitor.sock,server,nowait
```

Which is equivalent to directly calling:
```sh
$ /usr/bin/qemu-system-x86_64 -m 2G -machine accel=kvm:tcg -device i6300esb,id=watchdog0 -cpu host -parallel none -net none -drive if=none,id=root-disk,file=temp.qcow2 -device virtio-blk-pci,drive=root-disk,serial=myroot -vga none -display none -serial chardev:console -chardev file,id=console,path=/proc/self/fd/2 -chardev stdio,id=stdin,signal=on,mux=off -device virtio-serial-pci -device virtserialport,name=virtme.stdin,chardev=stdin -chardev file,id=stdout,path=/proc/self/fd/1 -device virtio-serial-pci -device virtserialport,name=virtme.stdout,chardev=stdout -chardev file,id=stderr,path=/proc/self/fd/2 -device virtio-serial-pci -device virtserialport,name=virtme.stderr,chardev=stderr -chardev file,id=dev_stdout,path=/proc/self/fd/1 -device virtio-serial-pci -device virtserialport,name=virtme.dev_stdout,chardev=dev_stdout -chardev file,id=dev_stderr,path=/proc/self/fd/2 -device virtio-serial-pci -device virtserialport,name=virtme.dev_stderr,chardev=dev_stderr -chardev file,id=ret,path=/tmp/virtme_ret38nwktc2 -device virtio-serial-pci -device virtserialport,name=virtme.ret,chardev=ret -no-reboot -kernel arch/x86_64/boot/bzImage -append 'nr_open=1073741816 root=/dev/vda console=ttyS0 earlyprintk=serial,ttyS0,115200 panic=-1 virtme.exec=`ZWNobyBtb28=` virtme_root_user=1 raid=noautodetect ro init=/vng/virtme/guest/bin/virtme-ng-init' -monitor unix:monitor.sock,server,nowait
```

## Init Path
As virtme-ng is intended to expose the host fs to the guest, it just locates the init binary on the host and forwards the path to the guest vm. If the root filesystem is not built in the way described in this document (e.g., because it was built in a different docker image), then it may be necessary to fix that path. The `--init-path` command tells virtme-ng where to find the init process.

For filesystems built exactly as described here, the (rust) init binary can be located in the resulting root filesystem by calling virtme-ng with `--init-path /vng/virtme/guest/bin/virtme-ng-init`. When calling qemu directly, the kernel command line should include `init=/vng/virtme/guest/bin/virtme-ng-init` (or whatever other path is appropriate for the target fs).