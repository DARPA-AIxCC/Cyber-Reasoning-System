#!/bin/bash
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
dir_name=$EXPERIMENT_DIR/darpa/<SUBJECT>/<ID>

current_dir=$PWD
echo "Making $dir_name"

if [ -n "$AIXCC_CRS_SCRATCH_SPACE" ] ;
then
        if  [[ "$current_dir" =~ ${AIXCC_CRS_SCRATCH_SPACE}/benchmark/.*  ]] ;
        then
                echo "Sleep for some time to block races"
                sleep $((1 + $RANDOM % 10))

                if [ ! -f $current_dir/.build_default -a ! -f $current_dir/.build_lock  ]; 
                then
                    echo "WILL BUILD"
                    touch $current_dir/.build_lock
                    DOCKER_RUN_ENV_FILE=.env.ins.docker ./run.sh build
                    touch $current_dir/.build_default
                    rm $current_dir/.build_lock
                fi

                until [ -f $current_dir/.build_default ]; 
                do
                    sleep 10;
                done
        fi
fi


mkdir -p $dir_name/src
rsync -azS $current_dir/. $dir_name/src
echo "Complete!"