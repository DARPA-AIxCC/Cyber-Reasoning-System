#!/bin/bash
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
benchmark_name=$(echo $script_dir | rev | cut -d "/" -f 3 | rev)
project_name=$(echo $script_dir | rev | cut -d "/" -f 2 | rev)
bug_id=$(echo $script_dir | rev | cut -d "/" -f 1 | rev)
dir_name=$EXPERIMENT_DIR/$benchmark_name/$project_name/$bug_id


current_dir=$PWD
cd $dir_name/src

./run.sh run_tests
RES=$(cat out/output/$(ls -t out/output | head -n 1)/exitcode)
#echo "Res is -${RES}-"
if [ $RES -ne 0 ]; then
    echo "Failed functionality tests"
    exit $RES
fi

for pov in $(ls tests); do
    ./run.sh run_pov tests/$pov <ADD_HARNESS_NAME>
    RES=$(cat out/output/$(ls -t out/output | head -n 1)/exitcode)
    if [ $RES -ne 0 ]; then
        echo "Failed POV $pov"
        exit $RES
    fi
done

exit $RES