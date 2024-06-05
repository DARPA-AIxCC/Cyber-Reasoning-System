#!/bin/bash
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
dir_name=$EXPERIMENT_DIR/darpa/<SUBJECT>/<ID>

HT_TIMEOUT="${HT_TIMEOUT:-30s}"
NO_FUNC="${NO_FUNC:-0}"
NO_BENIGN="${NO_BENIGN:-0}"

current_dir=$PWD
cd $dir_name/src

if [[ $NO_FUNC -eq 0 ]]; then
    timeout -k 10s $HT_TIMEOUT ./run.sh run_tests
    EXEC=$?
    RES=$(cat out/output/$(ls -t out/output | head -n 1)/exitcode)
    CID=$(cat out/output/$(ls -t out/output | head -n 1)/docker.cid)

    echo CID is $CID
    docker stop $CID

    #echo "Res is -${RES}-"
    if [[ $EXEC != 0 ||  $RES != 0 ]]; then
        echo "Failed functionality tests"
        exit $RES
    fi
fi

for pov in $(ls crashing_tests); do
    ./test.sh tests/$pov
    RES=$?
    if [[ $RES -ne 0 ]] ; then
        echo "Failed POV $pov"
        exit $RES
    fi
done

if [[ $NO_BENIGN -eq 0 ]]; then
    for pov in $(ls benign_tests | shuf -n 30); do
        ./test.sh tests/$pov
        RES=$?
        if [[ $RES -ne 0 ]] ; then
            echo "Failed BENIGN $pov"
            exit $RES
        fi
    done
fi

exit $RES
