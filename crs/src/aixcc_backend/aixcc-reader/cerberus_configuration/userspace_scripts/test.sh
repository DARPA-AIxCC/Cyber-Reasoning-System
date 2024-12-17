#!/bin/bash
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
dir_name=$EXPERIMENT_DIR/darpa/<SUBJECT>/<ID>

HT_TIMEOUT="${HT_TIMEOUT:-30s}"

current_dir=$PWD
cd $dir_name/src
stamp=$(date +%s)

sed "s|<INSERT>|$2|" .env.ins.docker > .env.ins.${stamp}.docker

DOCKER_RUN_ENV_FILE=.env.ins.${stamp}.docker timeout -k 10s $HT_TIMEOUT ./run.sh run_pov $1 <HARNESS_ID>
RES=$?

CID=$(cat out/output/$(ls -t out/output | head -n 1)/docker.cid)

echo CID is $CID
docker stop $CID

if [[ $RES != 0 ]];
then exit 1;
fi

latest_dir="out/output/$(ls -t out/output | head -n 1)"

grep -Eq "<SANITIZERS>" ${latest_dir}/stderr.log 
IN_STDERR=$?

grep -Eq "<SANITIZERS>" ${latest_dir}/stdout.log 
IN_STDOUT=$?

if [[ $IN_STDERR == 0 || $IN_STDOUT == 0 ]];
then 
    exit 2
else
    exit 0
fi
