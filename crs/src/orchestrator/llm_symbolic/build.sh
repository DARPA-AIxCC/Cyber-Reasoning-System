#!/usr/bin/env bash
set -euo pipefail

pushd() {
    command pushd "$@" > /dev/null
}

popd() {
    command popd "$@" > /dev/null
}

# Call graph generator
pushd call-graph-generator
mvn package
popd

# Python packages
python3 -m pip install -r requirements.txt

# Joern
if [ ! -f joern-cli/joern-parse ] || [ ! -f joern-cli/joern-export ]; then
    if [ ! -f joern-cli.zip ]; then
        wget https://github.com/joernio/joern/releases/download/v2.0.396/joern-cli.zip
    fi
    unzip joern-cli.zip
fi
