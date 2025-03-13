#!/usr/bin/env bash

set -x

# get path of this file
base_path="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

[[ -d "$base_path"/rns-config/ ]] && rm -rf "$base_path"/rns-config/

[[ -d "$base_path"/venv/ ]] && rm -rf "$base_path"/venv/


