# Valkyrie
Compilation-Free patch verification for APR

## Build and Dependencies
We provide a ready-made container which includes all necessary envrionment set-up
to deploy and run our tool. Dependencies include:

* GDB
* AFL
* E9Patch
* E9AFL
* GCJ (For java native compilation)
* Docker


Build and run a container:

    docker build -t rshariffdeen/valkyrie .
    docker run --rm -ti rshariffdeen/valkyrie /bin/bash


# Running Example
This repository includes 3 examples: a java example, a C example and a real-world application

## Java Example
    cd tests/java-sum
    make
    valkyrie --binary=sum --test-oracle=oracle --test-id-list=1,2,3,4 --patch-mode=gdb --debug --patch-dir=patch-dir/ --only-validate

## C Example
    cd tests/c-sum
    make
    valkyrie --binary=sum --test-oracle=oracle --test-id-list=1,2,3,4 --patch-mode=gdb --debug --patch-dir=patch-dir/ --only-validate


## Real-World
    cd tests/libtiff
    valkyrie --binary=sum --test-oracle=oracle --test-id-list=1 --patch-mode=gdb --debug --patch-dir=patch-dir/ --only-validate



[comment]: <> (## BINARY REWRITE)

[comment]: <> (```)

[comment]: <> (cd /valkyrie/tests/sum)

[comment]: <> (valkyrie --binary=sum --test-oracle=oracle-e9 --test-id-list=1,2,3,4 --patch-dir=patch-dir --patch-mode=rewrite)

[comment]: <> (```)

[comment]: <> (## GDB SCRIPTING)

[comment]: <> (```)

[comment]: <> (cd /valkyrie/tests/sum)

[comment]: <> (valkyrie --binary=sum --test-oracle=oracle --test-id-list=1,2,3,4 --patch-dir=patch-dir --patch-mode=gdb)

[comment]: <> (```)

[comment]: <> (## Compiling)

[comment]: <> (```)

[comment]: <> (cd /valkyrie/tests/sum)

[comment]: <> (valkyrie --binary=sum --test-oracle=oracle --test-id-list=1,2,3,4 --patch-dir=patch-dir --patch-mode=compile```)
