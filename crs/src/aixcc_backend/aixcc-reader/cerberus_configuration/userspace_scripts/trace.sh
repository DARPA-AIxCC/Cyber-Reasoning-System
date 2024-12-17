#!/bin/bash
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
dir_name=$EXPERIMENT_DIR/darpa/<SUBJECT>/<ID>

HT_TIMEOUT="${HT_TIMEOUT:-30s}"

current_dir=$PWD
cd $dir_name/src
stamp=$(date +%s)

sed "s|<INSERT>|/out/trace_$stamp|" .env.ins.docker > .env.ins.${stamp}.docker

DOCKER_RUN_ENV_FILE=.env.ins.${stamp}.docker timeout -k 5s $HT_TIMEOUT ./run.sh run_pov $1 <HARNESS_ID>
RES=$?

CID=$(cat out/output/$(ls -t out/output | head -n 1)/docker.cid)

echo CID is $CID
docker stop $CID

if [[ $RES == 1 ]];
then exit 1;
fi

cp out/trace_$stamp $2
exit 0
