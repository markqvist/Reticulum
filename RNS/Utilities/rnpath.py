#!/usr/bin/env python3

import RNS
import sys
import time
import argparse

from RNS._version import __version__


def program_setup(configdir, destination_hexhash, verbosity):
    try:
        dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH//8)*2
        if len(destination_hexhash) != dest_len:
            raise ValueError("Destination length is invalid, must be {hex} hexadecimal characters ({byte} bytes).".format(hex=dest_len, byte=dest_len//2))
        try:
            destination_hash = bytes.fromhex(destination_hexhash)
        except Exception as e:
            raise ValueError("Invalid destination entered. Check your input.")
    except Exception as e:
        print(str(e))
        exit()

    reticulum = RNS.Reticulum(configdir = configdir, loglevel = 3+verbosity)

    if not RNS.Transport.has_path(destination_hash):
        RNS.Transport.request_path(destination_hash)
        print("Path to "+RNS.prettyhexrep(destination_hash)+" requested  ", end=" ")
        sys.stdout.flush()

    i = 0
    syms = "⢄⢂⢁⡁⡈⡐⡠"
    while not RNS.Transport.has_path(destination_hash):
        time.sleep(0.1)
        print(("\b\b"+syms[i]+" "), end="")
        sys.stdout.flush()
        i = (i+1)%len(syms)

    hops = RNS.Transport.hops_to(destination_hash)
    next_hop = RNS.prettyhexrep(reticulum.get_next_hop(destination_hash))
    next_hop_interface = reticulum.get_next_hop_if_name(destination_hash)

    if hops != 1:
        ms = "s"
    else:
        ms = ""

    print("\rPath found, destination "+RNS.prettyhexrep(destination_hash)+" is "+str(hops)+" hop"+ms+" away via "+next_hop+" on "+next_hop_interface)
    

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Path Discovery Utility")

        parser.add_argument("--config",
            action="store",
            default=None,
            help="path to alternative Reticulum config directory",
            type=str
        )

        parser.add_argument(
            "--version",
            action="version",
            version="rnpath {version}".format(version=__version__)
        )

        parser.add_argument(
            "destination",
            nargs="?",
            default=None,
            help="hexadecimal hash of the destination",
            type=str
        )

        parser.add_argument('-v', '--verbose', action='count', default=0)
        
        args = parser.parse_args()

        if args.config:
            configarg = args.config
        else:
            configarg = None

        if not args.destination:
            print("")
            parser.print_help()
            print("")
        else:
            program_setup(configdir = configarg, destination_hexhash = args.destination, verbosity = args.verbose)

    except KeyboardInterrupt:
        print("")
        exit()

if __name__ == "__main__":
    main()