#!/usr/bin/env bash

set -e

base_path="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

source "$base_path"/common.sh

# set version by command line argument
if [[ $(valid_version_string "$1") -eq 0 ]]; then
    RNS_VERSION_STR="$1"
# or by environment variable
elif [[ $(valid_version_string "$RNS_VERSION") -eq 0 ]]; then
    RNS_VERSION_STR="$RNS_VERSION"
else
    die 'Please supply a valid version string.'
fi


if [[ -d "$base_path"/venv ]]; then
    echo "Found ./venv, assuming a python virtual env."
else
    echo "Did not find virtual env, creating..."
    python3 -m venv "$base_path"/venv
fi

source "$base_path"/venv/bin/activate

pip install -v "rns==${RNS_VERSION_STR}"
