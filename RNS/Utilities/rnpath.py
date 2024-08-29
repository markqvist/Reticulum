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
import os
import sys
import time
import argparse

from RNS._version import __version__

remote_link = None
def connect_remote(destination_hash, auth_identity, timeout, no_output = False):
    global remote_link, reticulum
    if not RNS.Transport.has_path(destination_hash):
        if not no_output:
            print("Path to "+RNS.prettyhexrep(destination_hash)+" requested", end=" ")
            sys.stdout.flush()
        RNS.Transport.request_path(destination_hash)
        pr_time = time.time()
        while not RNS.Transport.has_path(destination_hash):
            time.sleep(0.1)
            if time.time() - pr_time > timeout:
                if not no_output:
                    print("\r                                                          \r", end="")
                    print("Path request timed out")
                    exit(12)

    remote_identity = RNS.Identity.recall(destination_hash)

    def remote_link_closed(link):
        if link.teardown_reason == RNS.Link.TIMEOUT:
            if not no_output:
                print("\r                                                          \r", end="")
                print("The link timed out, exiting now")
        elif link.teardown_reason == RNS.Link.DESTINATION_CLOSED:
            if not no_output:
                print("\r                                                          \r", end="")
                print("The link was closed by the server, exiting now")
        else:
            if not no_output:
                print("\r                                                          \r", end="")
                print("Link closed unexpectedly, exiting now")
        exit(10)

    def remote_link_established(link):
        global remote_link
        link.identify(auth_identity)
        remote_link = link

    if not no_output:
        print("\r                                                          \r", end="")
        print("Establishing link with remote transport instance...", end=" ")
        sys.stdout.flush()

    remote_destination = RNS.Destination(remote_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "rnstransport", "remote", "management")
    link = RNS.Link(remote_destination)
    link.set_link_established_callback(remote_link_established)
    link.set_link_closed_callback(remote_link_closed)

def program_setup(configdir, table, rates, drop, destination_hexhash, verbosity, timeout, drop_queues,
                  drop_via, max_hops, remote=None, management_identity=None, remote_timeout=RNS.Transport.PATH_REQUEST_TIMEOUT,
                  no_output=False, json=False):
    global remote_link, reticulum
    reticulum = RNS.Reticulum(configdir = configdir, loglevel = 3+verbosity)
    if remote:
        try:
            dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH//8)*2
            if len(remote) != dest_len:
                raise ValueError("Destination length is invalid, must be {hex} hexadecimal characters ({byte} bytes).".format(hex=dest_len, byte=dest_len//2))
            try:
                identity_hash = bytes.fromhex(remote)
                remote_hash = RNS.Destination.hash_from_name_and_identity("rnstransport.remote.management", identity_hash)
            except Exception as e:
                raise ValueError("Invalid destination entered. Check your input.")

            identity = RNS.Identity.from_file(os.path.expanduser(management_identity))
            if identity == None:
                raise ValueError("Could not load management identity from "+str(management_identity))

            try:
                connect_remote(remote_hash, identity, remote_timeout, no_output)
            except Exception as e:
                raise e

        except Exception as e:
            print(str(e))
            exit(20)

        while remote_link == None:
            time.sleep(0.1)


    if table:
        destination_hash = None
        if destination_hexhash != None:
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
                sys.exit(1)

        if not remote_link:
            table = sorted(reticulum.get_path_table(max_hops=max_hops), key=lambda e: (e["interface"], e["hops"]) )
        else:
            if not no_output:
                print("\r                                                          \r", end="")
                print("Sending request...", end=" ")
                sys.stdout.flush()
            receipt = remote_link.request("/path", data = ["table", destination_hash, max_hops])
            while not receipt.concluded():
                time.sleep(0.1)
            response = receipt.get_response()
            if response:
                table = response
                print("\r                                                          \r", end="")
            else:
                if not no_output:
                    print("\r                                                          \r", end="")
                    print("The remote request failed. Likely authentication failure.")
                exit(10)

        displayed = 0
        if json:
            import json
            for p in table:
                for k in p:
                    if isinstance(p[k], bytes):
                        p[k] = RNS.hexrep(p[k], delimit=False)

            print(json.dumps(table))
            exit()
        else:
            for path in table:
                if destination_hash == None or destination_hash == path["hash"]:
                    displayed += 1
                    exp_str = RNS.timestamp_str(path["expires"])
                    if path["hops"] == 1:
                        m_str = " "
                    else:
                        m_str = "s"
                    print(RNS.prettyhexrep(path["hash"])+" is "+str(path["hops"])+" hop"+m_str+" away via "+RNS.prettyhexrep(path["via"])+" on "+path["interface"]+" expires "+RNS.timestamp_str(path["expires"]))

            if destination_hash != None and displayed == 0:
                print("No path known")
                sys.exit(1)

    elif rates:
        destination_hash = None
        if destination_hexhash != None:
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
                sys.exit(1)

        if not remote_link:
            table = reticulum.get_rate_table()
        else:
            if not no_output:
                print("\r                                                          \r", end="")
                print("Sending request...", end=" ")
                sys.stdout.flush()
            receipt = remote_link.request("/path", data = ["rates", destination_hash])
            while not receipt.concluded():
                time.sleep(0.1)
            response = receipt.get_response()
            if response:
                table = response
                print("\r                                                          \r", end="")
            else:
                if not no_output:
                    print("\r                                                          \r", end="")
                    print("The remote request failed. Likely authentication failure.")
                exit(10)

        table = sorted(table, key=lambda e: e["last"])
        if json:
            import json
            for p in table:
                for k in p:
                    if isinstance(p[k], bytes):
                        p[k] = RNS.hexrep(p[k], delimit=False)

            print(json.dumps(table))
            exit()
        else:
            if len(table) == 0:
                print("No information available")

            else:
                displayed = 0
                for entry in table:
                    if destination_hash == None or destination_hash == entry["hash"]:
                        displayed += 1
                        try:
                            last_str = pretty_date(int(entry["last"]))
                            start_ts = entry["timestamps"][0]
                            span = max(time.time() - start_ts, 3600.0)
                            span_hours = span/3600.0
                            span_str = pretty_date(int(entry["timestamps"][0]))
                            hour_rate = round(len(entry["timestamps"])/span_hours, 3)
                            if hour_rate-int(hour_rate) == 0:
                                hour_rate = int(hour_rate)
                            
                            if entry["rate_violations"] > 0:
                                if entry["rate_violations"] == 1:
                                    s_str = ""
                                else:
                                    s_str = "s"

                                rv_str = ", "+str(entry["rate_violations"])+" active rate violation"+s_str
                            else:
                                rv_str = ""
                            
                            if entry["blocked_until"] > time.time():
                                bli = time.time()-(int(entry["blocked_until"])-time.time())
                                bl_str = ", new announces allowed in "+pretty_date(int(bli))
                            else:
                                bl_str = ""

            
                            print(RNS.prettyhexrep(entry["hash"])+" last heard "+last_str+" ago, "+str(hour_rate)+" announces/hour in the last "+span_str+rv_str+bl_str)

                        except Exception as e:
                            print("Error while processing entry for "+RNS.prettyhexrep(entry["hash"]))
                            print(str(e))

                if destination_hash != None and displayed == 0:
                    print("No information available")
                    sys.exit(1)

    elif drop_queues:
        if remote_link:
            if not no_output:
                print("\r                                                          \r", end="")
                print("Dropping announce queues on remote instances not yet implemented")
            exit(255)

        print("Dropping announce queues on all interfaces...")
        reticulum.drop_announce_queues()
    
    elif drop:
        if remote_link:
            if not no_output:
                print("\r                                                          \r", end="")
                print("Dropping path on remote instances not yet implemented")
            exit(255)

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
            sys.exit(1)

        if reticulum.drop_path(destination_hash):
            print("Dropped path to "+RNS.prettyhexrep(destination_hash))
        else:
            print("Unable to drop path to "+RNS.prettyhexrep(destination_hash)+". Does it exist?")
            sys.exit(1)

    elif drop_via:
        if remote_link:
            if not no_output:
                print("\r                                                          \r", end="")
                print("Dropping all paths via specific transport instance on remote instances yet not implemented")
            exit(255)

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
            sys.exit(1)

        if reticulum.drop_all_via(destination_hash):
            print("Dropped all paths via "+RNS.prettyhexrep(destination_hash))
        else:
            print("Unable to drop paths via "+RNS.prettyhexrep(destination_hash)+". Does the transport instance exist?")
            sys.exit(1)

    else:
        if remote_link:
            if not no_output:
                print("\r                                                          \r", end="")
                print("Requesting paths on remote instances not implemented")
            exit(255)

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
            sys.exit(1)
            
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
            next_hop_bytes = reticulum.get_next_hop(destination_hash)
            if next_hop_bytes == None:
                print("\r                                                       \rError: Invalid path data returned")
                sys.exit(1)
            else:
                next_hop = RNS.prettyhexrep(next_hop_bytes)
                next_hop_interface = reticulum.get_next_hop_if_name(destination_hash)

                if hops != 1:
                    ms = "s"
                else:
                    ms = ""

                print("\rPath found, destination "+RNS.prettyhexrep(destination_hash)+" is "+str(hops)+" hop"+ms+" away via "+next_hop+" on "+next_hop_interface)
        else:
            print("\r                                                       \rPath not found")
            sys.exit(1)

    

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
            "-m",
            "--max",
            action="store",
            metavar="hops",
            type=int,
            help="maximum hops to filter path table by",
            default=None
        )

        parser.add_argument(
            "-r",
            "--rates",
            action="store_true",
            help="show announce rate info",
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
            "-D",
            "--drop-announces",
            action="store_true",
            help="drop all queued announces",
            default=False
        )

        parser.add_argument(
            "-x", "--drop-via",
            action="store_true",
            help="drop all paths via specified transport instance",
            default=False
        )

        parser.add_argument(
            "-w",
            action="store",
            metavar="seconds",
            type=float,
            help="timeout before giving up",
            default=RNS.Transport.PATH_REQUEST_TIMEOUT
        )

        parser.add_argument(
            "-R",
            action="store",
            metavar="hash",
            help="transport identity hash of remote instance to manage",
            default=None,
            type=str
        )

        parser.add_argument(
            "-i",
            action="store",
            metavar="path",
            help="path to identity used for remote management",
            default=None,
            type=str
        )

        parser.add_argument(
            "-W",
            action="store",
            metavar="seconds",
            type=float,
            help="timeout before giving up on remote queries",
            default=RNS.Transport.PATH_REQUEST_TIMEOUT
        )
        
        parser.add_argument(
            "-j",
            "--json",
            action="store_true",
            help="output in JSON format",
            default=False
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

        if not args.drop_announces and not args.table and not args.rates and not args.destination and not args.drop_via:
            print("")
            parser.print_help()
            print("")
        else:
            program_setup(
                configdir = configarg,
                table = args.table,
                rates = args.rates,
                drop = args.drop,
                destination_hexhash = args.destination,
                verbosity = args.verbose,
                timeout = args.w,
                drop_queues = args.drop_announces,
                drop_via = args.drop_via,
                max_hops = args.max,
                remote=args.R,
                management_identity=args.i,
                remote_timeout=args.W,
                json=args.json,
            )
            sys.exit(0)

    except KeyboardInterrupt:
        print("")
        exit()

def pretty_date(time=False):
    from datetime import datetime
    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time,datetime):
        diff = now - time
    elif not time:
        diff = now - now
    second_diff = diff.seconds
    day_diff = diff.days
    if day_diff < 0:
        return ''
    if day_diff == 0:
        if second_diff < 10:
            return str(second_diff) + " seconds"
        if second_diff < 60:
            return str(second_diff) + " seconds"
        if second_diff < 120:
            return "1 minute"
        if second_diff < 3600:
            return str(int(second_diff / 60)) + " minutes"
        if second_diff < 7200:
            return "an hour"
        if second_diff < 86400:
            return str(int(second_diff / 3600)) + " hours"
    if day_diff == 1:
        return "1 day"
    if day_diff < 7:
        return str(day_diff) + " days"
    if day_diff < 31:
        return str(int(day_diff / 7)) + " weeks"
    if day_diff < 365:
        return str(int(day_diff / 30)) + " months"
    return str(int(day_diff / 365)) + " years"

if __name__ == "__main__":
    main()