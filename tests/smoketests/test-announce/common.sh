#!/usr/bin/env bash

valid_version_string() {
    [[ "$1" =~ ([0-9]\.)+ ]] && return 0 || return 1
}

die() {
    # Takes an an optional error message as the sole argument.
    [[ -n "$1" ]] \
        && echo "$0 Error:" "$1" >&2 \
        || echo "$0 Unspecified error, aborting." >&2
    exit 1
}

