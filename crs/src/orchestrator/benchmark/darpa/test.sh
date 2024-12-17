#!/bin/bash
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
benchmark_name=$(echo $script_dir | rev | cut -d "/" -f 3 | rev)
project_name=$(echo $script_dir | rev | cut -d "/" -f 2 | rev)
bug_id=$(echo $script_dir | rev | cut -d "/" -f 1 | rev)
dir_name=$EXPERIMENT_DIR/$benchmark_name/$project_name/$bug_id


current_dir=$PWD
cd $dir_name/src

./run.sh run_pov $1 <ADD_HARNESS_NAME>
RES=$?

exit $RES