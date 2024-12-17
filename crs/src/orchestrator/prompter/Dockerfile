FROM nvidia/cuda:12.4.1-devel-ubuntu20.04
LABEL maintainer="Martin Mirchev <mirchevmartin2203@gmail.com>"

RUN apt-get update && apt-get upgrade -y && apt-get autoremove -y

# install vulnoc experiment dependencies
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends  \
    automake \
    autopoint \
    bear \
    bison \
    ca-certificates \
    cmake \
    curl \
    flex \
    gettext \
    git \
    gperf \
    libass-dev \
    libfreetype6 \
    libfreetype6-dev \
    libjpeg-dev \
    libnuma-dev \
    libpciaccess-dev \
    libpython3-dev \
    libsdl1.2-dev  \
    libsqlite3-dev \
    libtool \
    libvdpau-dev \
    libx11-dev \
    libxcb-xfixes0-dev \
    libxcb1-dev \
    libxcb-shm0-dev \
    libxml2-dev \
    nasm \
    nano \
    openssl \
    pkg-config \
    psmisc \
    python3 \
    texinfo \
    xutils-dev \
    yasm \
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
    psmisc \
    libsqlite3-dev \
    gcc-multilib \
    g++-multilib \
    tk-dev \
    mercurial \
    tcl-dev \
    tix-dev \
    unzip \
    wget \
    clang \
    sudo \
    rsync


RUN bash -c 'useradd -m ubuntu -p $(openssl passwd -1 ubuntu)'
RUN adduser ubuntu sudo

WORKDIR /home/ubuntu
USER ubuntu

RUN git clone https://github.com/yyuu/pyenv.git .pyenv

ENV HOME  /home/ubuntu
ENV PYENV_ROOT $HOME/.pyenv
ENV PATH $PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH

RUN pyenv install 3.11.0
RUN pyenv global 3.11.0
RUN pyenv rehash

COPY --chown=ubuntu requirements.txt /home/ubuntu/requirements.txt
RUN pip install -r /home/ubuntu/requirements.txt
COPY --chown=ubuntu ./cache-huggingface /home/ubuntu/.cache/huggingface
COPY --chown=ubuntu . /home/ubuntu/prompter

WORKDIR /home/ubuntu/prompter
ENV CUDA_HOME=/usr/local/cuda

# Do whatever extra install things you need here...

ENTRYPOINT "bash"
