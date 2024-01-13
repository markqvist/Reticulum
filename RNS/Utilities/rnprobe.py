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

DEFAULT_PROBE_SIZE = 16
DEFAULT_TIMEOUT = 12

def program_setup(configdir, destination_hexhash, size=None, full_name = None, verbosity = 0, timeout=None, wait=0, probes=1):
    if size == None: size = DEFAULT_PROBE_SIZE
    if full_name == None:
        print("The full destination name including application name aspects must be specified for the destination")
        exit()
    
    try:
        app_name, aspects = RNS.Destination.app_and_aspects_from_name(full_name)

    except Exception as e:
        print(str(e))
        exit()

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

    if verbosity > 0:
        more_output = True
        verbosity -= 1
    else:
        more_output = False
        verbosity -= 1


    reticulum = RNS.Reticulum(configdir = configdir, loglevel = 3+verbosity)

    if not RNS.Transport.has_path(destination_hash):
        RNS.Transport.request_path(destination_hash)
        print("Path to "+RNS.prettyhexrep(destination_hash)+" requested  ", end=" ")
        sys.stdout.flush()

    _timeout = time.time() + (timeout or DEFAULT_TIMEOUT+reticulum.get_first_hop_timeout(destination_hash))
    i = 0
    syms = "⢄⢂⢁⡁⡈⡐⡠"
    while not RNS.Transport.has_path(destination_hash) and not time.time() > _timeout:
        time.sleep(0.1)
        print(("\b\b"+syms[i]+" "), end="")
        sys.stdout.flush()
        i = (i+1)%len(syms)

    if time.time() > _timeout:
        print("\r                                                          \rPath request timed out")
        exit(1)

    server_identity = RNS.Identity.recall(destination_hash)

    request_destination = RNS.Destination(
        server_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        app_name,
        *aspects
    )

    sent = 0
    replies = 0
    while probes:

        if sent > 0:
            time.sleep(wait)

        try:
            probe = RNS.Packet(request_destination, os.urandom(size))
            probe.pack()
        except OSError:
            print("Error: Probe packet size of "+str(len(probe.raw))+" bytes exceed MTU of "+str(RNS.Reticulum.MTU)+" bytes")
            exit(3)

        receipt = probe.send()
        sent += 1

        if more_output:
            nhd = reticulum.get_next_hop(destination_hash)
            via_str = " via "+RNS.prettyhexrep(nhd) if nhd != None else ""
            if_str  = " on "+str(reticulum.get_next_hop_if_name(destination_hash)) if reticulum.get_next_hop_if_name(destination_hash) != "None" else ""
            more = via_str+if_str
        else:
            more = ""

        print("\rSent probe "+str(sent)+" ("+str(size)+" bytes) to "+RNS.prettyhexrep(destination_hash)+more+"  ", end=" ")

        _timeout = time.time() + (timeout or DEFAULT_TIMEOUT+reticulum.get_first_hop_timeout(destination_hash))
        i = 0
        while receipt.status == RNS.PacketReceipt.SENT and not time.time() > _timeout:
            time.sleep(0.1)
            print(("\b\b"+syms[i]+" "), end="")
            sys.stdout.flush()
            i = (i+1)%len(syms)

        if time.time() > _timeout:
            print("\r                                                                \rProbe timed out")
        
        else:
            print("\b\b ")
            sys.stdout.flush()

            if receipt.status == RNS.PacketReceipt.DELIVERED:
                replies += 1
                hops = RNS.Transport.hops_to(destination_hash)
                if hops != 1:
                    ms = "s"
                else:
                    ms = ""

                rtt = receipt.get_rtt()
                if (rtt >= 1):
                    rtt = round(rtt, 3)
                    rttstring = str(rtt)+" seconds"
                else:
                    rtt = round(rtt*1000, 3)
                    rttstring = str(rtt)+" milliseconds"

                reception_stats = ""
                if reticulum.is_connected_to_shared_instance:
                    reception_rssi = reticulum.get_packet_rssi(receipt.proof_packet.packet_hash)
                    reception_snr  = reticulum.get_packet_snr(receipt.proof_packet.packet_hash)
                    reception_q    = reticulum.get_packet_q(receipt.proof_packet.packet_hash)

                    if reception_rssi != None:
                        reception_stats += " [RSSI "+str(reception_rssi)+" dBm]"
                    
                    if reception_snr != None:
                        reception_stats += " [SNR "+str(reception_snr)+" dB]"
                    
                    if reception_q != None:
                        reception_stats += " [Link Quality "+str(reception_q)+"%]"

                else:
                    if receipt.proof_packet != None:
                        if receipt.proof_packet.rssi != None:
                            reception_stats += " [RSSI "+str(receipt.proof_packet.rssi)+" dBm]"
                        
                        if receipt.proof_packet.snr != None:
                            reception_stats += " [SNR "+str(receipt.proof_packet.snr)+" dB]"

                print(
                    "Valid reply from "+
                    RNS.prettyhexrep(receipt.destination.hash)+
                    "\nRound-trip time is "+rttstring+
                    " over "+str(hops)+" hop"+ms+
                    reception_stats+"\n"
                )

            else:
                print("\r                                                          \rProbe timed out")

        probes -= 1

    loss = round((1-(replies/sent))*100, 2)
    print(f"Sent {sent}, received {replies}, packet loss {loss}%")
    if loss > 0:
        exit(2)
    else:
        exit(0)
    

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Probe Utility")

        parser.add_argument("--config", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
        parser.add_argument("-s", "--size", action="store", default=None, help="size of probe packet payload in bytes", type=int)
        parser.add_argument("-n", "--probes", action="store", default=1, help="number of probes to send", type=int)
        parser.add_argument("-t", "--timeout", metavar="seconds", action="store", default=None, help="timeout before giving up", type=float)
        parser.add_argument("-w", "--wait", metavar="seconds", action="store", default=0, help="time between each probe", type=float)
        parser.add_argument("--version", action="version", version="rnprobe {version}".format(version=__version__))
        parser.add_argument("full_name", nargs="?", default=None, help="full destination name in dotted notation", type=str)
        parser.add_argument("destination_hash", nargs="?", default=None, help="hexadecimal hash of the destination", type=str)

        parser.add_argument('-v', '--verbose', action='count', default=0)

        args = parser.parse_args()

        if args.config:
            configarg = args.config
        else:
            configarg = None

        if not args.destination_hash:
            print("")
            parser.print_help()
            print("")
        else:
            program_setup(
                configdir = configarg,
                destination_hexhash = args.destination_hash,
                size = args.size,
                full_name = args.full_name,
                verbosity = args.verbose,
                probes = args.probes,
                wait = args.wait,
                timeout = args.timeout,
            )

    except KeyboardInterrupt:
        print("")
        exit()

if __name__ == "__main__":
    main()