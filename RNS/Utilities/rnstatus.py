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

def size_str(num, suffix='B'):
    units = ['','K','M','G','T','P','E','Z']
    last_unit = 'Y'

    if suffix == 'b':
        num *= 8
        units = ['','K','M','G','T','P','E','Z']
        last_unit = 'Y'

    for unit in units:
        if abs(num) < 1000.0:
            if unit == "":
                return "%.0f %s%s" % (num, unit, suffix)
            else:
                return "%.2f %s%s" % (num, unit, suffix)
        num /= 1000.0

    return "%.2f%s%s" % (num, last_unit, suffix)

request_result = None
request_concluded = False
def get_remote_status(destination_hash, include_lstats, identity, no_output=False, timeout=RNS.Transport.PATH_REQUEST_TIMEOUT):
    global request_result, request_concluded
    link_count = None

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

    def request_failed(request_receipt):
        global request_result, request_concluded
        if not no_output:
            print("\r                                                          \r", end="")
            print("The remote status request failed. Likely authentication failure.")
        request_concluded = True

    def got_response(request_receipt):
        global request_result, request_concluded
        response = request_receipt.response
        if isinstance(response, list):
            status = response[0]
            if len(response) > 1:
                link_count = response[1]
            else:
                link_count = None

            request_result = (status, link_count)

        request_concluded = True

    def remote_link_established(link):
        if not no_output:
            print("\r                                                          \r", end="")
            print("Sending request...", end=" ")
            sys.stdout.flush()
        link.identify(identity)
        link.request("/status", data = [include_lstats], response_callback = got_response, failed_callback = request_failed)

    if not no_output:
        print("\r                                                          \r", end="")
        print("Establishing link with remote transport instance...", end=" ")
        sys.stdout.flush()

    remote_destination = RNS.Destination(remote_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "rnstransport", "remote", "management")
    link = RNS.Link(remote_destination)
    link.set_link_established_callback(remote_link_established)
    link.set_link_closed_callback(remote_link_closed)

    while not request_concluded:
        time.sleep(0.1)

    if request_result != None:
        print("\r                                                          \r", end="")

    return request_result

def program_setup(configdir, dispall=False, verbosity=0, name_filter=None, json=False, astats=False,
                  lstats=False, sorting=None, sort_reverse=False, remote=None, management_identity=None,
                  remote_timeout=RNS.Transport.PATH_REQUEST_TIMEOUT):
    reticulum = RNS.Reticulum(configdir = configdir, loglevel = 3+verbosity)

    link_count = None
    stats = None
    if remote:
        try:
            dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH//8)*2
            if len(remote) != dest_len:
                raise ValueError("Destination length is invalid, must be {hex} hexadecimal characters ({byte} bytes).".format(hex=dest_len, byte=dest_len//2))
            try:
                identity_hash = bytes.fromhex(remote)
                destination_hash = RNS.Destination.hash_from_name_and_identity("rnstransport.remote.management", identity_hash)
            except Exception as e:
                raise ValueError("Invalid destination entered. Check your input.")

            identity = RNS.Identity.from_file(os.path.expanduser(management_identity))
            if identity == None:
                raise ValueError("Could not load management identity from "+str(management_identity))

            try:
                remote_status = get_remote_status(destination_hash, lstats, identity, no_output=json, timeout=remote_timeout)
                if remote_status != None:
                    stats, link_count = remote_status
            except Exception as e:
                raise e
                    
        except Exception as e:
            print(str(e))
            exit(20)

    else:
        if lstats:
            try:
                link_count = reticulum.get_link_count()
            except Exception as e:
                pass

        try:
            stats = reticulum.get_interface_stats()
        except Exception as e:
            pass

    if stats != None:
        if json:
            import json
            for s in stats:
                if isinstance(stats[s], bytes):
                    stats[s] = RNS.hexrep(stats[s], delimit=False)

                if isinstance(stats[s], dict) or isinstance(stats[s], list):
                    for i in stats[s]:
                        if isinstance(i, dict):
                            for k in i:
                                if isinstance(i[k], bytes):
                                    i[k] = RNS.hexrep(i[k], delimit=False)

            print(json.dumps(stats))
            exit()

        interfaces = stats["interfaces"]
        if sorting != None and isinstance(sorting, str):
            sorting = sorting.lower()
            if sorting == "rate" or sorting == "bitrate":
                interfaces.sort(key=lambda i: i["bitrate"], reverse=not sort_reverse)
            if sorting == "rx":
                interfaces.sort(key=lambda i: i["rxb"], reverse=not sort_reverse)
            if sorting == "tx":
                interfaces.sort(key=lambda i: i["txb"], reverse=not sort_reverse)
            if sorting == "traffic":
                interfaces.sort(key=lambda i: i["rxb"]+i["txb"], reverse=not sort_reverse)
            if sorting == "announces" or sorting == "announce":
                interfaces.sort(key=lambda i: i["incoming_announce_frequency"]+i["outgoing_announce_frequency"], reverse=not sort_reverse)
            if sorting == "arx":
                interfaces.sort(key=lambda i: i["incoming_announce_frequency"], reverse=not sort_reverse)
            if sorting == "atx":
                interfaces.sort(key=lambda i: i["outgoing_announce_frequency"], reverse=not sort_reverse)
            if sorting == "held":
                interfaces.sort(key=lambda i: i["held_announces"], reverse=not sort_reverse)

            
        for ifstat in interfaces:
            name = ifstat["name"]

            if dispall or not (
                name.startswith("LocalInterface[") or
                name.startswith("TCPInterface[Client") or
                name.startswith("I2PInterfacePeer[Connected peer") or
                (name.startswith("I2PInterface[") and ("i2p_connectable" in ifstat and ifstat["i2p_connectable"] == False))
                ):

                if not (name.startswith("I2PInterface[") and ("i2p_connectable" in ifstat and ifstat["i2p_connectable"] == False)):
                    if name_filter == None or name_filter.lower() in name.lower():
                        print("")

                        if ifstat["status"]:
                            ss = "Up"
                        else:
                            ss = "Down"

                        if ifstat["mode"] == RNS.Interfaces.Interface.Interface.MODE_ACCESS_POINT:
                            modestr = "Access Point"
                        elif ifstat["mode"] == RNS.Interfaces.Interface.Interface.MODE_POINT_TO_POINT:
                            modestr = "Point-to-Point"
                        elif ifstat["mode"] == RNS.Interfaces.Interface.Interface.MODE_ROAMING:
                            modestr = "Roaming"
                        elif ifstat["mode"] == RNS.Interfaces.Interface.Interface.MODE_BOUNDARY:
                            modestr = "Boundary"
                        elif ifstat["mode"] == RNS.Interfaces.Interface.Interface.MODE_GATEWAY:
                            modestr = "Gateway"
                        else:
                            modestr = "Full"


                        if ifstat["clients"] != None:
                            clients = ifstat["clients"]
                            if name.startswith("Shared Instance["):
                                cnum = max(clients-1,0)
                                if cnum == 1:
                                    spec_str = " program"
                                else:
                                    spec_str = " programs"

                                clients_string = "Serving   : "+str(cnum)+spec_str
                            elif name.startswith("I2PInterface["):
                                if "i2p_connectable" in ifstat and ifstat["i2p_connectable"] == True:
                                    cnum = clients
                                    if cnum == 1:
                                        spec_str = " connected I2P endpoint"
                                    else:
                                        spec_str = " connected I2P endpoints"

                                    clients_string = "Peers     : "+str(cnum)+spec_str
                                else:
                                    clients_string = ""
                            else:
                                clients_string = "Clients   : "+str(clients)

                        else:
                            clients = None

                        print(" {n}".format(n=ifstat["name"]))

                        if "ifac_netname" in ifstat and ifstat["ifac_netname"] != None:
                            print("    Network   : {nn}".format(nn=ifstat["ifac_netname"]))

                        print("    Status    : {ss}".format(ss=ss))

                        if clients != None and clients_string != "":
                            print("    "+clients_string)

                        if not (name.startswith("Shared Instance[") or name.startswith("TCPInterface[Client") or name.startswith("LocalInterface[")):
                            print("    Mode      : {mode}".format(mode=modestr))

                        if "bitrate" in ifstat and ifstat["bitrate"] != None:
                            print("    Rate      : {ss}".format(ss=speed_str(ifstat["bitrate"])))

                        if "battery_percent" in ifstat and ifstat["battery_percent"] != None:
                            try:
                                bpi = int(ifstat["battery_percent"])
                                bss = ifstat["battery_state"]
                                print(f"    Battery   : {bpi}% ({bss})")
                            except:
                                pass

                        if "airtime_short" in ifstat and "airtime_long" in ifstat:
                            print("    Airtime   : {ats}% (15s), {atl}% (1h)".format(ats=str(ifstat["airtime_short"]),atl=str(ifstat["airtime_long"])))
                        
                        if "channel_load_short" in ifstat and "channel_load_long" in ifstat:
                            print("    Ch.Load   : {ats}% (15s), {atl}% (1h)".format(ats=str(ifstat["channel_load_short"]),atl=str(ifstat["channel_load_long"])))
                        
                        if "peers" in ifstat and ifstat["peers"] != None:
                            print("    Peers     : {np} reachable".format(np=ifstat["peers"]))

                        if "tunnelstate" in ifstat and ifstat["tunnelstate"] != None:
                            print("    I2P       : {ts}".format(ts=ifstat["tunnelstate"]))

                        if "ifac_signature" in ifstat and ifstat["ifac_signature"] != None:
                            sigstr = "<…"+RNS.hexrep(ifstat["ifac_signature"][-5:], delimit=False)+">"
                            print("    Access    : {nb}-bit IFAC by {sig}".format(nb=ifstat["ifac_size"]*8, sig=sigstr))
                        
                        if "i2p_b32" in ifstat and ifstat["i2p_b32"] != None:
                            print("    I2P B32   : {ep}".format(ep=str(ifstat["i2p_b32"])))

                        if astats and "announce_queue" in ifstat and ifstat["announce_queue"] != None and ifstat["announce_queue"] > 0:
                            aqn = ifstat["announce_queue"]
                            if aqn == 1:
                                print("    Queued    : {np} announce".format(np=aqn))
                            else:
                                print("    Queued    : {np} announces".format(np=aqn))
                        
                        if astats and "held_announces" in ifstat and ifstat["held_announces"] != None and ifstat["held_announces"] > 0:
                            aqn = ifstat["held_announces"]
                            if aqn == 1:
                                print("    Held      : {np} announce".format(np=aqn))
                            else:
                                print("    Held      : {np} announces".format(np=aqn))
                        
                        if astats and "incoming_announce_frequency" in ifstat and ifstat["incoming_announce_frequency"] != None:
                            print("    Announces : {iaf}↑".format(iaf=RNS.prettyfrequency(ifstat["outgoing_announce_frequency"])))
                            print("                {iaf}↓".format(iaf=RNS.prettyfrequency(ifstat["incoming_announce_frequency"])))

                        print("    Traffic   : {txb}↑\n                {rxb}↓".format(rxb=size_str(ifstat["rxb"]), txb=size_str(ifstat["txb"])))

        lstr = ""
        if link_count != None and lstats:
            ms = "y" if link_count == 1 else "ies"
            if "transport_id" in stats and stats["transport_id"] != None:
                lstr = f", {link_count} entr{ms} in link table"
            else:
                lstr = f" {link_count} entr{ms} in link table"

        if "transport_id" in stats and stats["transport_id"] != None:
            print("\n Transport Instance "+RNS.prettyhexrep(stats["transport_id"])+" running")
            if "probe_responder" in stats and stats["probe_responder"] != None:
                print(" Probe responder at "+RNS.prettyhexrep(stats["probe_responder"])+ " active")
            if "transport_uptime" in stats and stats["transport_uptime"] != None:
                print(" Uptime is "+RNS.prettytime(stats["transport_uptime"])+lstr)
        else:
            if lstr != "":
                print(f"\n{lstr}")

        print("")
                
    else:
        if not remote:
            print("Could not get RNS status")
        else:
            print("Could not get RNS status from remote transport instance "+RNS.prettyhexrep(identity_hash))
        exit(1)

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Network Stack Status")
        parser.add_argument("--config", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
        parser.add_argument("--version", action="version", version="rnstatus {version}".format(version=__version__))

        parser.add_argument(
            "-a",
            "--all",
            action="store_true",
            help="show all interfaces",
            default=False
        )
        
        parser.add_argument(
            "-A",
            "--announce-stats",
            action="store_true",
            help="show announce stats",
            default=False
        )
        
        parser.add_argument(
            "-l",
            "--link-stats",
            action="store_true",
            help="show link stats",
            default=False,
        )
        
        parser.add_argument(
            "-s",
            "--sort",
            action="store",
            help="sort interfaces by [rate, traffic, rx, tx, announces, arx, atx, held]",
            default=None,
            type=str
        )
        
        parser.add_argument(
            "-r",
            "--reverse",
            action="store_true",
            help="reverse sorting",
            default=False,
        )
        
        parser.add_argument(
            "-j",
            "--json",
            action="store_true",
            help="output in JSON format",
            default=False
        )

        parser.add_argument(
            "-R",
            action="store",
            metavar="hash",
            help="transport identity hash of remote instance to get status from",
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
            "-w",
            action="store",
            metavar="seconds",
            type=float,
            help="timeout before giving up on remote queries",
            default=RNS.Transport.PATH_REQUEST_TIMEOUT
        )

        parser.add_argument('-v', '--verbose', action='count', default=0)

        parser.add_argument("filter", nargs="?", default=None, help="only display interfaces with names including filter", type=str)
        
        args = parser.parse_args()

        if args.config:
            configarg = args.config
        else:
            configarg = None

        program_setup(
            configdir = configarg,
            dispall = args.all,
            verbosity=args.verbose,
            name_filter=args.filter,
            json=args.json,
            astats=args.announce_stats,
            lstats=args.link_stats,
            sorting=args.sort,
            sort_reverse=args.reverse,
            remote=args.R,
            management_identity=args.i,
            remote_timeout=args.w,
        )

    except KeyboardInterrupt:
        print("")
        exit()

def speed_str(num, suffix='bps'):
    units = ['','k','M','G','T','P','E','Z']
    last_unit = 'Y'

    if suffix == 'Bps':
        num /= 8
        units = ['','K','M','G','T','P','E','Z']
        last_unit = 'Y'

    for unit in units:
        if abs(num) < 1000.0:
            return "%3.2f %s%s" % (num, unit, suffix)
        num /= 1000.0

    return "%.2f %s%s" % (num, last_unit, suffix)

if __name__ == "__main__":
    main()
