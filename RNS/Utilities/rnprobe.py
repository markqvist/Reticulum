#!/usr/bin/env python3

import RNS
import os
import sys
import time
import argparse

from RNS._version import __version__

DEFAULT_PROBE_SIZE = 16

def program_setup(configdir, destination_hexhash, size=DEFAULT_PROBE_SIZE, full_name = None, verbosity = 0):
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

    i = 0
    syms = "⢄⢂⢁⡁⡈⡐⡠"
    while not RNS.Transport.has_path(destination_hash):
        time.sleep(0.1)
        print(("\b\b"+syms[i]+" "), end="")
        sys.stdout.flush()
        i = (i+1)%len(syms)

    server_identity = RNS.Identity.recall(destination_hash)

    request_destination = RNS.Destination(
        server_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        app_name,
        *aspects
    )

    probe = RNS.Packet(request_destination, os.urandom(size))
    receipt = probe.send()

    if more_output:
        more = " via "+RNS.prettyhexrep(reticulum.get_next_hop(destination_hash))+" on "+str(reticulum.get_next_hop_if_name(destination_hash))
    else:
        more = ""

    print("\rSent "+str(size)+" byte probe to "+RNS.prettyhexrep(destination_hash)+more+"  ", end=" ")

    i = 0
    while not receipt.status == RNS.PacketReceipt.DELIVERED:
        time.sleep(0.1)
        print(("\b\b"+syms[i]+" "), end="")
        sys.stdout.flush()
        i = (i+1)%len(syms)

    print("\b\b ")
    sys.stdout.flush()

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

        if reception_rssi != None:
            reception_stats += " [RSSI "+str(reception_rssi)+" dBm]"
        
        if reception_snr != None:
            reception_stats += " [SNR "+str(reception_snr)+" dB]"

    else:
        if receipt.proof_packet != None:
            if receipt.proof_packet.rssi != None:
                reception_stats += " [RSSI "+str(receipt.proof_packet.rssi)+" dBm]"
            
            if receipt.proof_packet.snr != None:
                reception_stats += " [SNR "+str(receipt.proof_packet.snr)+" dB]"

    print(
        "Valid reply received from "+
        RNS.prettyhexrep(receipt.destination.hash)+
        "\nRound-trip time is "+rttstring+
        " over "+str(hops)+" hop"+ms+
        reception_stats
    )

    

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Probe Utility")

        parser.add_argument("--config",
            action="store",
            default=None,
            help="path to alternative Reticulum config directory",
            type=str
        )

        parser.add_argument(
            "--version",
            action="version",
            version="rnprobe {version}".format(version=__version__)
        )

        parser.add_argument(
            "full_name",
            nargs="?",
            default=None,
            help="full destination name in dotted notation",
            type=str
        )

        parser.add_argument(
            "destination_hash",
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

        if not args.destination_hash:
            print("")
            parser.print_help()
            print("")
        else:
            program_setup(
                configdir = configarg,
                destination_hexhash = args.destination_hash,
                full_name = args.full_name,
                verbosity = args.verbose
            )

    except KeyboardInterrupt:
        print("")
        exit()

if __name__ == "__main__":
    main()