#!/bin/bash
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
dir_name=$EXPERIMENT_DIR/darpa/<SUBJECT>/<ID>

HT_TIMEOUT="${HT_TIMEOUT:-1m}"

current_dir=$PWD
cd $dir_name/src
stamp=$(date +%s)

timeout -k 10s $HT_TIMEOUT ./run.sh run_pov $1 <HARNESS_ID>
RES=$?

CID=$(cat out/output/$(ls -t out/output | head -n 1)/docker.cid)

echo CID is $CID
docker stop $CID

exit $RES
