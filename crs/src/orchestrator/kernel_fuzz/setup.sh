#!/bin/sh
set -e
DEBIAN_FRONTEND=noninteractive apt install -y build-essential git python3 python3-pip libdwarf-dev elfutils libelf-dev libdw-dev markdown fakeroot git build-essential xxd gdb libasan4 make automake autopoint

#git clone https://github.com/aixcc-public/challenge-001-exemplar.git

which e9patch
res=$?

if [[ res == 1 ]];
then
    git clone https://github.com/GJDuck/e9afl.git
    cd e9afl; 
    ./build.sh; 
    ./install.sh;
    apt install -y ./e9patch_*.deb
fi