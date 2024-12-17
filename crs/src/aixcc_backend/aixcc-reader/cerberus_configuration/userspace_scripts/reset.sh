#!/bin/bash
script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
dir_name=$EXPERIMENT_DIR/darpa/<SUBJECT>/<ID>



cd $dir_name/src/src
for x in * ; do
    if [[ -d $x && -d $x/.git  ]]; then
        cd $x
        echo "Checking out $PWD"
        git checkout .
        cd ..
    else
        if [[ -d $x ]]; then
            for y in $x/*; do
                if [[ -d $y && -d $y/.git  ]]; then
                    cd $y
                    echo "Checking out $PWD"
                    git checkout .
                    cd ..
                fi
            done
        fi
    fi
done