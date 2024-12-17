#!/bin/bash

set -e
set -v

# Run this in kernel source directory; PATCHES_DIR should be set to this directory
if [[ -z "${PATCHES_DIR}" ]]; then
	echo "Set the PATCHES_DIR environment variable to the directory with all the patches"
	echo "Run this script from the root of the kernel source directory"
	echo "e.g. PATCHES_DIR=../LibAFL-kernel/kernel-patches/src \$PATCHES_DIR/apply.sh"
	exit 1
fi

git -c user.name='VirtFuzz' -c user.email='shuster@seemoo.tu-darmstadt.de' am -3 --no-gpg-sign < $PATCHES_DIR/driver.diff

if ! grep "ivshmem" drivers/staging/Kconfig; then
    echo "Manually amending commit to include ivshmem device in drivers/staging/Kconfig"
    sed -i 's/endif # STAGING/source "drivers\/staging\/ivshmem\/Kconfig"\nendif # STAGING/g' drivers/staging/Kconfig
    git add drivers/staging/Kconfig
    git -c user.name='VirtFuzz' -c user.email='shuster@seemoo.tu-darmstadt.de' commit --no-gpg-sign --amend -m "$(git log --format=%B -n1)" -m "Add ivshmem to Kconfig"
fi

if ! grep "CONFIG_IVSHMEM" drivers/staging/Makefile; then
    echo "Manually amending commit to include ivshmem device in drivers/staging/Makefile"
    echo 'obj-$(CONFIG_IVSHMEM)	+= ivshmem/' >> drivers/staging/Makefile;
    git add drivers/staging/Makefile
    git -c user.name='VirtFuzz' -c user.email='shuster@seemoo.tu-darmstadt.de' commit --no-gpg-sign --amend -m "$(git log --format=%B -n1)" -m "Add ivshmem to Makefile"
fi

# if ! git log -- kernel/kcov.c | grep "kcov: replace local_irq_save() with a local_lock_t"; then
	# git -c user.name='VirtFuzz' -c user.email='shuster@seemoo.tu-darmstadt.de'  am -3 --no-gpg-sign < $PATCHES_DIR/kcov-backports/0001-kcov-allocate-per-CPU-memory-on-the-relevant-node.patch
	# git -c user.name='VirtFuzz' -c user.email='shuster@seemoo.tu-darmstadt.de'  am -3 --no-gpg-sign < $PATCHES_DIR/kcov-backports/0002-kcov-avoid-enable-disable-interrupts-if-in_task.patch
	# git -c user.name='VirtFuzz' -c user.email='shuster@seemoo.tu-darmstadt.de'  am -3 --no-gpg-sign < $PATCHES_DIR/kcov-backports/0003-kcov-replace-local_irq_save-with-a-local_lock_t.patch
# fi


git -c user.name='VirtFuzz' -c user.email='shuster@seemoo.tu-darmstadt.de' am -3 --no-gpg-sign < $PATCHES_DIR/cover.diff

# if git log -- include/linux/kcov.h | grep "kcov: add prototypes for helper functions"; then
	# git -c user.name='VirtFuzz' -c user.email='shuster@seemoo.tu-darmstadt.de'  am -3 --no-gpg-sign < $PATCHES_DIR/0001-Add-function-definitions-in-header.patch
# fi

git apply $PATCHES_DIR/kcov.h.diff
git apply $PATCHES_DIR/config.diff

echo "Applied the base patches!"

git apply $PATCHES_DIR/udp.diff

echo "Applied the hooks for starting/stopping KCOV in IRQs"

