#!/bin/bash
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
dir_name=$EXPERIMENT_DIR/darpa/<SUBJECT>/<ID>

HT_TIMEOUT="${HT_TIMEOUT:-10m}"

current_dir=$PWD
cd $dir_name/src

timeout -k 10s $HT_TIMEOUT ./run.sh run_pov $1 <HARNESS_ID> | grep "KCOVTRACE>>>>" | cut -f 2 -d " " >> $2/trace_$(date +%s)
RES=$?

CID=$(cat out/output/$(ls -t out/output | head -n 1)/docker.cid)

echo CID is $CID
docker stop $CID

exit $RES
