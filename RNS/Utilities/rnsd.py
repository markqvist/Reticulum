#!/usr/bin/env python3

import RNS
import argparse
import time

from RNS._version import __version__


def program_setup(configdir, verbosity = 0, quietness = 0, service = False):
    targetloglevel = 3+verbosity-quietness

    if service:
        RNS.logdest = RNS.LOG_FILE
        RNS.logfile = RNS.Reticulum.configdir+"/logfile"
        targetloglevel = None

    reticulum = RNS.Reticulum(configdir=configdir, loglevel=targetloglevel)
    RNS.log("Started rnsd version {version}".format(version=__version__), RNS.LOG_NOTICE)
    while True:
        time.sleep(1)

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Network Stack Daemon")
        parser.add_argument("--config", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
        parser.add_argument('-v', '--verbose', action='count', default=0)
        parser.add_argument('-q', '--quiet', action='count', default=0)
        parser.add_argument('-s', '--service', action='store_true', default=False, help="rnsd is running as a service and should log to file")
        parser.add_argument("--version", action="version", version="rnsd {version}".format(version=__version__))
        
        args = parser.parse_args()

        if args.config:
            configarg = args.config
        else:
            configarg = None

        program_setup(configdir = configarg, verbosity=args.verbose, quietness=args.quiet, service=args.service)

    except KeyboardInterrupt:
        print("")
        exit()

if __name__ == "__main__":
    main()