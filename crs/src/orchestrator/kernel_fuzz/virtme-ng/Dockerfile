FROM ubuntu:22.04

RUN \
  --mount=type=cache,sharing=locked,target=/var/cache/apt/,id=ubuntu:22.04/var/cache/apt/ \
  --mount=type=cache,sharing=locked,target=/var/lib/apt/lists/,id=ubuntu:22.04/var/lib/apt/lists/ \
  mv /etc/apt/apt.conf.d/docker-clean /etc/apt/apt.conf.d/docker-gzip-indexes / \
  && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends --no-install-suggests \
    binutils \
		file \
    kmod \
		python3-requests \
		qemu-system-x86 \
    udev \
  && mv /docker-clean /docker-gzip-indexes /etc/apt/apt.conf.d/

RUN \
  --mount=type=cache,sharing=locked,target=/var/cache/apt/,id=ubuntu:22.04/var/cache/apt/ \
  --mount=type=cache,sharing=locked,target=/var/lib/apt/lists/,id=ubuntu:22.04/var/lib/apt/lists/ \
  mv /etc/apt/apt.conf.d/docker-clean /etc/apt/apt.conf.d/docker-gzip-indexes / \
  && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends --no-install-suggests \
		qemu-utils \
    rsync \
    socat \
  && mv /docker-clean /docker-gzip-indexes /etc/apt/apt.conf.d/
