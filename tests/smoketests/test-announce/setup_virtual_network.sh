#!/usr/bin/env bash

set -ex

# get path of this file
base_path="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"


# load config
source "$base_path"/network_config.env

# create network namespace
ip netns add h1
ip netns add h2

# create virtual network
ip -n h1 link add "$H1_DEV" type veth peer name "$H2_DEV" netns h2

# Setup loopback
ip netns exec h1 ip link set lo up
ip netns exec h2 ip link set lo up

# assign ip adresses
ip netns exec h1 ip addr add "$H1_IP/24" dev "$H1_DEV"
ip netns exec h2 ip addr add "$H2_IP/24" dev "$H2_DEV"

# set mac adresses
ip netns exec h1 ip link set dev "$H1_DEV" address "$H1_MAC"
ip netns exec h2 ip link set dev "$H2_DEV" address "$H2_MAC"

# activate interfaces
ip netns exec h1 ip link set "$H1_DEV" up
ip netns exec h2 ip link set "$H2_DEV" up

# set default routes
ip netns exec h1 ip route add default via "$H1_GW" dev "$H1_DEV"
ip netns exec h2 ip route add default via "$H2_GW" dev "$H2_DEV"
