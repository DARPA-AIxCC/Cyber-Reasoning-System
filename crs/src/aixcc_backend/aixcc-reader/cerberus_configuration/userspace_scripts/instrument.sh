#!/bin/bash
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
dir_name=$EXPERIMENT_DIR/darpa/<SUBJECT>/<ID>

current_dir=$PWD

# cd $dir_name/src

# DOCKER_RUN_ENV_FILE=.env.ins.docker ./run.sh build

# cd trace_instrumentation

# cd hooks

# CC=gcc CXX=g++ e9compile src_tracer.c

# cp src_tracer ../

# cd ../

# python3 instrument.py $dir_name/src/<HARNESS_BINARY>

# cp $dir_name/src/<HARNESS_BINARY>*.tracer $dir_name/src/<HARNESS_BINARY>