#!/bin/bash

if [ "$#" -ne 2 ]; then
    echo "copy-in <disk image> <file/dir>"
    echo "WARNING: potentially very destructive script; please be careful with proper usage"
    exit 1
fi

# Run as SUDO from HOST 
modprobe nbd max_part=8
qemu-nbd --connect=/dev/nbd0 $1
mkdir /mnt/somepoint
mount /dev/nbd0 /mnt/somepoint/
cp -r $2 /mnt/somepoint
umount /mnt/somepoint/
qemu-nbd --disconnect /dev/nbd0
rmmod nbd
