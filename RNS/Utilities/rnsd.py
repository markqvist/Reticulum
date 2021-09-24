#!/usr/bin/env python3

import RNS
import argparse

from RNS._version import __version__


def program_setup(configdir):
    reticulum = RNS.Reticulum(configdir = configdir)
    RNS.log("Started rnsd version {version}".format(version=__version__), RNS.LOG_INFO)
    while True:
        input()

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Network Stack Daemon")
        parser.add_argument("--config", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
        parser.add_argument("--version", action="version", version="rnsd {version}".format(version=__version__))
        
        args = parser.parse_args()

        if args.config:
            configarg = args.config
        else:
            configarg = None

        program_setup(configdir = configarg)

    except KeyboardInterrupt:
        print("")
        exit()

if __name__ == "__main__":
    main()