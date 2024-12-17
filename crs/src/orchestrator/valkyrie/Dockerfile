FROM ubuntu:20.04
MAINTAINER Ridwan Shariffdeen <ridwan@comp.nus.edu.sg>
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get upgrade -y && apt-get autoremove -y
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends  \
    autopoint \
    automake \
    bison \
    flex \
    gettext \
    gperf \
    libass-dev \
    libfreetype6 \
    libfreetype6-dev \
    libjpeg-dev \
    libtool \
    libxml2-dev \
    liblzma-dev \
    nasm \
    pkg-config \
    texinfo \
    yasm \
    xutils-dev \
    libpciaccess-dev \
    libpython3-dev \
    libx11-dev \
    libxcb-xfixes0-dev \
    libxcb1-dev \
    libxcb-shm0-dev \
    libsdl1.2-dev  \
    libsqlite3-dev \
    libvdpau-dev \
    libnuma-dev \
    shc \
    m4 \
    libglib2.0-dev \
    libldap-dev \
    libbz2-dev \
    libssl-dev \
    libsqlite3-dev \
    libxml2-dev \
    libgdbm-dev \
    subversion \
    libc6-dev-i386 \
    mercurial \
    libncurses-dev \
    libsqlite-dev \
    libgdbm-dev \
    libssl-dev \
    libreadline-gplv2-dev \
    libbz2-dev \
    openjdk-11-jdk \
    openjdk-11-jdk-headless \
    psmisc \
    libsqlite3-dev \
    gcc-multilib \
    g++-multilib \
    tk-dev \
    mercurial \
    tcl-dev \
    tix-dev \
    software-properties-common \
    git \
    gdb \
    maven \
    nano \
    patch  \
    patchutils \
    vim

## Install PyPy JITC
RUN add-apt-repository -y ppa:pypy/ppa
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y  --no-install-recommends --force-yes \
    gfortran \
    pypy3 \
    pypy3-dev \
    python3-pip \
    python3-setuptools \
    wget \
    unzip

RUN pypy3 -m easy_install setuptools pytest pytest-timeout
RUN pip3 install nuitka

#RUN git clone https://github.com/GJDuck/e9patch.git /e9patch; cd /e9patch; bash build.sh
#RUN ln -s /e9patch/e9tool /usr/local/bin/e9tool
#RUN ln -s /e9patch/e9patch /usr/local/bin/e9patch
#RUN git clone https://github.com/GJDuck/e9afl.git /e9afl; cd /e9afl; bash build.sh
#RUN ln -s /e9afl/e9afl /usr/local/bin/e9afl
#RUN mkdir /valkyrie
#COPY lib /valkyrie/lib
#COPY tests /valkyrie/tests
ADD . /opt/valkyrie
ENV PATH="${PATH}:/opt/valkyrie/bin"
WORKDIR /opt/valkyrie/
RUN python3 -m nuitka Valkyrie.py

# RUN git clone https://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:x-oauth-basic@github.com/rshariffdeen/valkyrie.git /valkyrie
#ENV E9HOME="/e9patch"
#RUN cd /valkyrie/e9plugins; /e9patch/e9compile.sh coverage.c -I /e9patch/examples/ -I /e9patch/src/e9patch/  -DNO_GLIBC=1
#RUN cd /valkyrie/e9plugins; /e9patch/e9compile.sh trace.c -I /e9patch/examples/ -I /e9patch/src/e9patch/  -DNO_GLIBC=1
#RUN cd /valkyrie/lib; /e9patch/e9compile.sh patch_hook.c -I /e9patch/examples/
