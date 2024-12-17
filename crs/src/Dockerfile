# This is just a sample Dockerfile
# Competitors: You MUST implement your own Dockerfile here so that your container/s can be built
# and published to your CRS repo

FROM ubuntu:22.04

WORKDIR /app

# Install python 3.11 provider
RUN apt update
RUN DEBIAN_FRONTEND=noninteractive apt install -y software-properties-common
RUN add-apt-repository ppa:deadsnakes/ppa

# global environment variables
ENV LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    TZ=America/New_York \
    USER=root \
    WORK=/root/work \
    CRS_HOME=/root/crs \
    CRS_SRC=/root/crs/src \
    CRS_LIB=/root/crs/src/scripts \
    CRS_TEST=/root/crs/test


# Install all required packages, preferably keep the order sorted
# We target Java 17, Python 3.11, GCC 11, Rust
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get -y install \
        7zip \
        autoconf \
        automake \
        autotools-dev \
        autopoint \
        apt-transport-https \
        bash \
        binutils \
        build-essential \
        ca-certificates \
        clang-14 \
        cmake \
        curl \
        file \
        gnupg2 \
        g++ \
        gcc \
        gcc-11-plugin-dev \
        gcc-multilib \
        gdb \
        git \
        git-lfs \
        g++-multilib \
        jq \
        libcap2 \
        libc6-dev-i386 \
        libtool \
        libdw-dev \
        llvm-14 \
        ltrace \
        markdown \
        maven \
        nano \
        nasm \
        nodejs \
        npm \
        openjdk-17-jdk \
        openssl \
        patch \
        perl-base \
        psmisc \
        python3 \
        python3.11 \
        python3.11-dev \
        python3-dev \
        python3-setuptools \
        python3-wheel \
        rsync \
        tar \
        tzdata \
        unzip \
        vim \
        wget \
        xxd \
        xz-utils \
        zip \
        zstd \
    && apt-get clean \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*
    

RUN npm install -g composerize

ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH="/usr/local/cargo/bin:$PATH"

RUN curl https://sh.rustup.rs -sSf | bash -s -- -y


RUN rustup self update

RUN ln -sf /usr/bin/python3.11 /usr/bin/python3
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Install YQ
ARG YQ_VERSION=4.43.1
ARG YQ_BINARY=yq_linux_amd64
RUN wget -q https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/${YQ_BINARY} -O /usr/bin/yq && \
    chmod +x /usr/bin/yq

# Install Docker for CP repo build and test
# hadolint ignore=DL3008,DL4001,DL4006,SC1091
RUN set -eux; \
    install -m 0755 -d /etc/apt/keyrings; \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc; \
    chmod a+r /etc/apt/keyrings/docker.asc; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null; \
    DEBIAN_FRONTEND=noninteractive apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        containerd.io \
        docker-ce \
        docker-ce-cli \
        docker-buildx-plugin; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*

# Build e9patch
WORKDIR /app
RUN git clone https://github.com/GJDuck/e9patch.git && \
    cd /app/e9patch && \
    ./build.sh && ./install.sh && apt install ./*.deb


RUN set -eux;  \ 
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" ; \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl.sha256" ; \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Finish building e9patch

# Build AFL++
# WORKDIR /app
# RUN git clone https://github.com/Marti2203/AFLplusplus.git && \
#     cd /app/AFLplusplus && \
#     STATIC=1 make && STATIC=1 make install && \
#     rm -rf /app/AFLplusplus
# Finish building AFL++

# Remove packages, past this point no installatons
RUN rm -rf /var/lib/{apt,dpkg,cache,log}

# Copy your source code
COPY crs/src/requirements.txt .
RUN pip install -r requirements.txt

RUN mkdir /app/orchestrator

COPY crs/src/orchestrator/acr /app/orchestrator/acr
COPY crs/src/orchestrator/app /app/orchestrator/app
COPY crs/src/orchestrator/chopper /app/orchestrator/chopper
COPY crs/src/orchestrator/config /app/orchestrator/config
COPY crs/src/orchestrator/dd_repair /app/orchestrator/dd_repair
COPY crs/src/orchestrator/fake-docker /app/orchestrator/fake-docker
COPY crs/src/orchestrator/hermes /app/orchestrator/hermes
COPY crs/src/orchestrator/java-sbfl /app/orchestrator/java-sbfl
COPY crs/src/orchestrator/klee /app/orchestrator/klee
COPY crs/src/orchestrator/kernel_fuzz /app/orchestrator/kernel_fuzz
COPY crs/src/orchestrator/libfuzzer_fuzz /app/orchestrator/libfuzzer_fuzz
COPY crs/src/orchestrator/llm_symbolic /app/orchestrator/llm_symbolic
COPY crs/src/orchestrator/dumb_fuzz /app/orchestrator/dumb_fuzz
COPY crs/src/orchestrator/normal_fuzz /app/orchestrator/normal_fuzz
COPY crs/src/orchestrator/normal_jfuzz /app/orchestrator/normal_jfuzz
COPY crs/src/orchestrator/profiles /app/orchestrator/profiles
COPY crs/src/orchestrator/sanitize_parser /app/orchestrator/sanitize_parser
COPY crs/src/orchestrator/sbfl_local /app/orchestrator/sbfl_local
COPY crs/src/orchestrator/sbfl_neo_local /app/orchestrator/sbfl_neo_local
COPY crs/src/orchestrator/valkyrie /app/orchestrator/valkyrie
COPY crs/src/orchestrator/main.py /app/orchestrator/main.py
COPY crs/src/orchestrator/server.py /app/orchestrator/server.py


# Build neo sbfl

# Finish building neo sbfl

WORKDIR /app/orchestrator/sbfl_neo_local/

RUN bash ./build.sh

WORKDIR /app/

# Build call-graph gen

WORKDIR /app/orchestrator/llm_symbolic/call-graph-generator

RUN mvn package

WORKDIR /app/

# Finish building call-graph-gen

# Build kernel_fuzz

WORKDIR /app/orchestrator/kernel_fuzz

RUN cargo build --release
RUN cd virtio-serial-guest && cargo build --release
RUN cd cli-grabber && cargo build --release
RUN cd virtme-ng && make

WORKDIR /app/

# Finish building kernel_fuzz

# Build jacoco

WORKDIR /app/orchestrator/java-sbfl

RUN (test -f jacoco-0.8.12.zip || wget https://github.com/jacoco/jacoco/releases/download/v0.8.12/jacoco-0.8.12.zip) && \
    unzip -o jacoco-0.8.12.zip && \
    rm jacoco-0.8.12.zip

WORKDIR /app

# Finish building jacoco


# Build Joern
WORKDIR /app/orchestrator/llm_symbolic

RUN (test -f joern-cli.zip || wget https://github.com/joernio/joern/releases/download/v2.0.396/joern-cli.zip) && \
    unzip -o joern-cli.zip && \
    rm joern-cli.zip

WORKDIR /app

# Finish building joern


# Build KLEE
WORKDIR /app/orchestrator/klee

RUN bash ./build.sh

WORKDIR /app

# Finish building KLEE


COPY crs/src/run.sh .

RUN git config --global user.email healingtouch@ignore.com
RUN git config --global user.name CRS_Healing_Touch

# Run the command to start your CRS, this is just a placeholder
CMD ["./run.sh"]
