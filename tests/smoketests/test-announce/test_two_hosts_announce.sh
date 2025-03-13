#!/usr/bin/env bash

set -x

base_path="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

source "$base_path"/common.sh

############ GET RNS VERSION STR ############

# set version by command line argument
if $(valid_version_string "$1"); then
    RNS_VERSION_STR="$1"
# or by environment variable
elif $(valid_version_string "${RNS_VERSION}"); then
    RNS_VERSION_STR="$RNS_VERSION"
else
    die 'Please supply a valid version string. (eg. "0.9.1")'
fi

############## SETUP ####################


# setup venv for rns version string
bash "$base_path"/setup_python_venv.sh "$RNS_VERSION_STR"

# veth setup
bash "$base_path"/setup_virtual_network.sh

# setup rns config
bash "$base_path"/setup_rns_config.sh


H1_DIR="$base_path"/rns-config/h1
H2_DIR="$base_path"/rns-config/h2

[[ -d "$base_path"/venv/bin ]] && venv="$base_path"/venv/bin

EXEC_H1="ip netns exec h1"
EXEC_H2="ip netns exec h2"

################# TEST ####################

# generate "$venv"/rns ids
$EXEC_H1 "$venv"/rnid --config "$H1_DIR" -g "$H1_DIR"/id
$EXEC_H2 "$venv"/rnid --config "$H2_DIR" -g "$H2_DIR"/id

# start two "$venv"/rns daemons
$EXEC_H1 "$venv"/rnsd --config "$H1_DIR" &
$EXEC_H2 "$venv"/rnsd --config "$H2_DIR" &

sleep 1 # seconds

ANNOUNCE_REGEXP='(?<=Announcing destination )\<.*\>'

# broadcast announce from h1 and capture the destination hash
h1_hash=$($EXEC_H1 "$venv"/rnid --config "$H1_DIR" -i "$H1_DIR"/id -a test.h1 | grep -oP "$ANNOUNCE_REGEXP")

sleep 1 # seconds

H1_ANNOUNCE_RECV=1
# verify announce as seen from h2
if [[ $($EXEC_H2 "$venv"/rnpath --config "$H2_DIR" -t) == *"$h1_hash"* ]] && [[ -n "$h1_hash" ]]; then
    echo 'h1 announce sucessfully recieved'
    H1_ANNOUNCE_RECV=0
else
    echo 'h1 announce was not recieved successfully'
fi

# broadcast announce from h2 and capture the destination hash
h2_hash=$($EXEC_H2 "$venv"/rnid --config "$H2_DIR" -i "$H2_DIR"/id -a test.h2 | grep -oP "$ANNOUNCE_REGEXP")

sleep 1 # seconds

H2_ANNOUNCE_RECV=1
# verify announce as seen from h1
if [[ $($EXEC_H1 "$venv"/rnpath --config "$H1_DIR" -t) == *"$h2_hash"* ]] && [[ -n "$h2_hash" ]]; then
    echo 'h2 announce sucessfully recieved'
    H2_ANNOUNCE_RECV=0
else
    echo 'h2 announce was not recieved successfully'
fi


########## TEARDOWN ############

# stop rnsd instances
$EXEC_H1 pkill rnsd
$EXEC_H2 pkill rnsd

# veth teardown
bash "$base_path"/cleanup_virtual_network.sh

# directories teardown
bash "$base_path"/cleanup_directories.sh


########### EXIT BASED ON TEST OUTCOME #############

exit $([[ $H1_ANNOUNCE_RECV -eq 0 ]] && [[ $H2_ANNOUNCE_RECV -eq 0 ]])
