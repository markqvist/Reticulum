#!/usr/bin/env python3

import RNS
import argparse

from RNS._version import __version__


def program_setup(configdir, verbosity = 0, quietness = 0):
    reticulum = RNS.Reticulum(configdir = configdir, loglevel = 3+verbosity-quietness)
    RNS.log("Started rnsd version {version}".format(version=__version__), RNS.LOG_NOTICE)
    while True:
        input()

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Network Stack Daemon")
        parser.add_argument("--config", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
        parser.add_argument('-v', '--verbose', action='count', default=0)
        parser.add_argument('-q', '--quiet', action='count', default=0)
        parser.add_argument("--version", action="version", version="rnsd {version}".format(version=__version__))
        
        args = parser.parse_args()

        if args.config:
            configarg = args.config
        else:
            configarg = None

        program_setup(configdir = configarg, verbosity=args.verbose, quietness=args.quiet)

    except KeyboardInterrupt:
        print("")
        exit()

if __name__ == "__main__":
    main()