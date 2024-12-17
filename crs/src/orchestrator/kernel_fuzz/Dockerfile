FROM ubuntu:22.04

RUN apt-get update -y

RUN apt-get install curl build-essential zstd git -y

# Get Rust
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"


COPY Cargo.toml Cargo.toml
COPY challenge-001-cp-files challenge-001-cp-files
COPY kcovreader kcovreader
COPY src src
COPY virtio-serial-guest virtio-serial-guest
COPY virtme-ng virtme-ng
COPY cli-grabber cli-grabber

COPY .git .git
COPY .gitmodules .gitmodules
COPY .gitattributes .gitattributes

RUN git submodule update --init --recursive

RUN cargo build --release
RUN cd virtio-serial-guest; cargo build --release
RUN cd cli-grabber; cargo build --release
RUN cd virtme-ng; make

