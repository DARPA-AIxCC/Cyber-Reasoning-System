FROM ubuntu:20.04


RUN echo 'deb http://dk.archive.ubuntu.com/ubuntu/ trusty main' >> \
         /etc/apt/sources.list && \
    echo 'deb http://dk.archive.ubuntu.com/ubuntu/ trusty universe' >> \
         /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y \
    gcc-4.4 \
    g++-4.4 \
    unzip \
    sudo \
    nano \
    wget \
    curl \
    python2 \
    python3 \
    python3-pip && \
    curl https://bootstrap.pypa.io/pip/2.7/get-pip.py --output get-pip.py && \
    python2 get-pip.py && \
    ln -s /usr/bin/python2.7 /usr/bin/python

RUN DEBIAN_FRONTEND=noninteractive apt-get -y install tzdata

RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y \
    apt-utils \
    libc6-dev-i386 \
    g++-multilib \
    mono-complete \
    software-properties-common

ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH="/usr/local/cargo/bin:$PATH"

RUN curl https://sh.rustup.rs -sSf | bash -s -- -y


RUN rustup self update

# Add a new user ubuntu, pass: ubuntu
RUN groupadd ubuntu && \
    useradd -rm -d /home/ubuntu -s /bin/bash -g ubuntu -G sudo -u 1000 ubuntu -p "$(openssl passwd -1 ubuntu)"

# Use ubuntu as the default username
USER root

WORKDIR /home/ubuntu

# Set up environment variables
ENV WORKDIR="/home/ubuntu"
ENV PATH="${PATH}:${WORKDIR}:${WORKDIR}/peach-3.0.202-source/output/linux_x86_64_release/bin"

# Copy file from the host folder where Dockerfile is stored
COPY kernel_pit.xml $WORKDIR/kernel_pit.xml
COPY nginx_pit.xml $WORKDIR/nginx_pit.xml
COPY wscript_build $WORKDIR/wscript_build
COPY requirements.txt $WORKDIR/requirements.txt
COPY ART.py $WORKDIR/ART.py
COPY test_monitor $WORKDIR/test_monitor
COPY run.sh ${WORKDIR}/run.sh
COPY peach-3.0.202.patch ${WORKDIR}/peach-3.0.202.patch
COPY cfg_fuzzing $WORKDIR/cfg_fuzzing


# Install packages required by ART.py
RUN pip3 install -r $WORKDIR/requirements.txt

COPY kernel_pit.xml $WORKDIR/kernel_pit.xml
COPY server.py ${WORKDIR}/server.py
COPY gen_pit ${WORKDIR}/gen_pit
COPY gen_g4 ${WORKDIR}/gen_g4


RUN mkdir -p /home/ubuntu/shared/in
RUN mkdir -p /home/ubuntu/peach-cracker

COPY http_req.txt /home/ubuntu/shared/in/http.bin
COPY http_req.txt /home/ubuntu/shared/in/nginx.bin
COPY kernel_benign.bin /home/ubuntu/shared/in/kernel_benign.bin


# Install Peach generation-based fuzzer
RUN cd $WORKDIR && \
    wget https://storage.googleapis.com/fuzzbench-files/peach-3.0.202-source.zip && \
    unzip peach-3.0.202-source.zip && \
    cp wscript_build peach-3.0.202-source/Peach.Core.Analysis.Pin.BasicBlocks/ && \
    cd peach-3.0.202-source && \
    CC=gcc-4.4 CXX=g++-4.4 ./waf configure && \
    CC=gcc-4.4 CXX=g++-4.4 ./waf install


# Install Peach generation-based fuzzer
RUN cd $WORKDIR && \
    cp wscript_build peach-3.0.202-source/Peach.Core.Analysis.Pin.BasicBlocks/ && \
    patch -p1 < peach-3.0.202.patch && \
    cd peach-3.0.202-source && \
    CC=gcc-4.4 CXX=g++-4.4 ./waf configure --prefix=/home/ubuntu/peach-cracker --destdir=/home/ubuntu/peach-cracker && \
    CC=gcc-4.4 CXX=g++-4.4 ./waf install --prefix=/home/ubuntu/peach-cracker --destdir=/home/ubuntu/peach-cracker

CMD ["./run.sh"]