#!/bin/bash
#
# Copyright (C) National University of Singapore
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

if [ -t 1 ]
then
    RED="\033[31m"
    GREEN="\033[32m"
    YELLOW="\033[33m"
    BOLD="\033[1m"
    OFF="\033[0m"
else
    RED=
    GREEN=
    YELLOW=
    BOLD=
    OFF=
fi

set -e

VERSION=b922de2bb4a3778380fe8e7540cdc8e3550674c1

# STEP (1): install e9patch if necessary:
if [ "`readlink e9patch`" != "e9patch-$VERSION/e9patch" ]
then
    if [ ! -f e9patch-$VERSION.zip ]
    then
        echo -e "${GREEN}$0${OFF}: downloading e9patch-$VERSION.zip..."
        wget -O e9patch-$VERSION.zip \
            https://github.com/GJDuck/e9patch/archive/$VERSION.zip
    fi

    echo -e "${GREEN}$0${OFF}: extracting e9patch-$VERSION.zip..."
    unzip e9patch-$VERSION.zip

    echo -e "${GREEN}$0${OFF}: building e9patch..."
    cd e9patch-$VERSION
    ./build.sh
    cd ..
    ln -f -s e9patch-$VERSION/e9patch
    ln -f -s e9patch-$VERSION/e9tool
    ln -f -s e9patch-$VERSION/e9compile.sh
    ln -f -s e9patch-$VERSION/examples/stdlib.c
    ln -f -s e9patch-$VERSION/src/e9tool/e9plugin.h
    ln -f -s e9patch-$VERSION/src/e9tool/e9tool.h
    echo -e "${GREEN}$0${OFF}: e9patch has been built..."
else
    echo -e "${GREEN}$0${OFF}: using existing e9patch..."
fi

# STEP (2): build the instrumentation
echo -e "${GREEN}$0${OFF}: building SBFL insrumentation..."
NO_SIMD_CHECK=1 ./e9compile.sh sbfl.c

