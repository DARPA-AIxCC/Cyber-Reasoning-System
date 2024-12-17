FROM ubuntu:22.04

RUN apt update
RUN apt install -y software-properties-common
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt update && DEBIAN_FRONTEND=noninteractive apt install -y python3.11 wget
RUN ln -sf /usr/bin/python3.11 /usr/bin/python3
RUN wget https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py && python3 /tmp/get-pip.py

RUN apt install -y openjdk-17-jdk git maven vim unzip wget

COPY . /opt/sym_llm
WORKDIR /opt/sym_llm
RUN ./build.sh
