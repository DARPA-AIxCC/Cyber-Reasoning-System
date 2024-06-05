#!/bin/bash
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
dir_name=$EXPERIMENT_DIR/darpa/<SUBJECT>/<ID>

current_dir=$pwd
cd $dir_name/src
DOCKER_RUN_ENV_FILE=.env.ins.docker ./run.sh build

exit $?