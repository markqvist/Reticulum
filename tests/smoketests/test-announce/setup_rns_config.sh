#!/usr/bin/env bash

set -x

# get path of this file
base_path="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

mkdir -p "$base_path"/rns-config/h{1,2}

cp "$base_path"/rns.config "$base_path"/rns-config/h1/config
cp "$base_path"/rns.config "$base_path"/rns-config/h2/config
