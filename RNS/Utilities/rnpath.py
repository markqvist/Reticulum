#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2016-2022 Mark Qvist / unsigned.io
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import RNS
import sys
import time
import argparse

from RNS._version import __version__


def program_setup(configdir, table, drop, destination_hexhash, verbosity, timeout):
    if table:
        reticulum = RNS.Reticulum(configdir = configdir, loglevel = 3+verbosity)
        table = sorted(reticulum.get_path_table(), key=lambda e: (e["interface"], e["hops"]) )

        for path in table:
            exp_str = RNS.timestamp_str(path["expires"])
            if path["hops"] == 1:
                m_str = " "
            else:
                m_str = "s"
            print(RNS.prettyhexrep(path["hash"])+" is "+str(path["hops"])+" hop"+m_str+" away via "+RNS.prettyhexrep(path["via"])+" on "+path["interface"]+" expires "+RNS.timestamp_str(path["expires"]))

    elif drop:
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

        if reticulum.drop_path(destination_hash):
            print("Dropped path to "+RNS.prettyhexrep(destination_hash))
        else:
            print("Unable to drop path to "+RNS.prettyhexrep(destination_hash)+". Does it exist?")

    else:
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
        limit = time.time()+timeout
        while not RNS.Transport.has_path(destination_hash) and time.time()<limit:
            time.sleep(0.1)
            print(("\b\b"+syms[i]+" "), end="")
            sys.stdout.flush()
            i = (i+1)%len(syms)

        if RNS.Transport.has_path(destination_hash):
            hops = RNS.Transport.hops_to(destination_hash)
            next_hop = RNS.prettyhexrep(reticulum.get_next_hop(destination_hash))
            next_hop_interface = reticulum.get_next_hop_if_name(destination_hash)

            if hops != 1:
                ms = "s"
            else:
                ms = ""

            print("\rPath found, destination "+RNS.prettyhexrep(destination_hash)+" is "+str(hops)+" hop"+ms+" away via "+next_hop+" on "+next_hop_interface)
        else:
            print("\r                                                \rPath not found")
    

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
            "-t",
            "--table",
            action="store_true",
            help="show all known paths",
            default=False
        )

        parser.add_argument(
            "-d",
            "--drop",
            action="store_true",
            help="remove the path to a destination",
            default=False
        )

        parser.add_argument(
            "-w",
            action="store",
            metavar="seconds",
            type=float,
            help="timeout before giving up",
            default=15
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

        if not args.table and not args.destination:
            print("")
            parser.print_help()
            print("")
        else:
            program_setup(
                configdir = configarg,
                table = args.table,
                drop = args.drop,
                destination_hexhash = args.destination,
                verbosity = args.verbose,
                timeout = args.w,
            )

    except KeyboardInterrupt:
        print("")
        exit()

if __name__ == "__main__":
    main()