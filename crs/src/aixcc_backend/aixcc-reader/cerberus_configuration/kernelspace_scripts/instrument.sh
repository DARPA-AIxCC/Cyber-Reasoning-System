#!/bin/bash
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
dir_name=$EXPERIMENT_DIR/darpa/<SUBJECT>/<ID>

cd $dir_name/src

cp trace_instrumentation/kernel-files/* $(dirname <HARNESS_PATH>) 

cd src/linux_kernel

git apply $dir_name/src/trace_instrumentation/kernel-patches/*  

cd ../..


DOCKER_RUN_ENV_FILE=.env.ins.docker ./run.sh build

exit $?