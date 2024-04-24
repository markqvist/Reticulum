#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2023 Mark Qvist / unsigned.io
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
import argparse
import time
import sys
import os
import base64

from RNS._version import __version__

APP_NAME = "rnid"

SIG_EXT = "rsg"
ENCRYPT_EXT = "rfe"
CHUNK_SIZE = 16*1024*1024


def spin(until=None, msg="", timeout=None):
    i = 0
    syms = "⢄⢂⢁⡁⡈⡐⡠"
    if timeout is not None:
        timeout = time.time()+timeout

    print(msg, end="   ")
    while (timeout is None or time.time()<timeout) and not until():
        time.sleep(0.1)
        print(("\b\b", syms[i]), end=" ", sep="")
        sys.stdout.flush()
        i = (i+1)%len(syms)

    print("\r", *len(msg), "\r", end="", sep="")

    if timeout is not None and time.time() > timeout:
        return False
    else:
        return True

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Identity & Encryption Utility")
        # parser.add_argument("file", nargs="?", default=None, help="input file path", type=str)

        parser.add_argument("--config", metavar="path", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
        parser.add_argument("-i", "--identity", metavar="identity", action="store", default=None, help="hexadecimal Reticulum Destination hash or path to Identity file", type=str)
        parser.add_argument("-g", "--generate", metavar="file", action="store", default=None, help="generate a new Identity")
        parser.add_argument("-m", "--import", dest="import_str", metavar="identity_data", action="store", default=None, help="import Reticulum identity in hex, base32 or base64 format", type=str)
        parser.add_argument("-x", "--export", action="store_true", default=None, help="export identity to hex, base32 or base64 format")

        parser.add_argument("-v", "--verbose", action="count", default=0, help="increase verbosity")
        parser.add_argument("-q", "--quiet", action="count", default=0, help="decrease verbosity")

        parser.add_argument("-a", "--announce", metavar="aspects", action="store", default=None, help="announce a destination based on this Identity")
        parser.add_argument("-H", "--hash", metavar="aspects", action="store", default=None, help="show destination hashes for other aspects for this Identity")
        parser.add_argument("-e", "--encrypt", metavar="file", action="store", default=None, help="encrypt file")
        parser.add_argument("-d", "--decrypt", metavar="file", action="store", default=None, help="decrypt file")
        parser.add_argument("-s", "--sign", metavar="path", action="store", default=None, help="sign file")
        parser.add_argument("-V", "--validate", metavar="path", action="store", default=None, help="validate signature")

        parser.add_argument("-r", "--read", metavar="file", action="store", default=None, help="input file path", type=str)
        parser.add_argument("-w", "--write", metavar="file", action="store", default=None, help="output file path", type=str)
        parser.add_argument("-f", "--force", action="store_true", default=None, help="write output even if it overwrites existing files")
        parser.add_argument("-I", "--stdin", action="store_true", default=False, help=argparse.SUPPRESS) # "read input from STDIN instead of file"
        parser.add_argument("-O", "--stdout", action="store_true", default=False, help=argparse.SUPPRESS) # help="write output to STDOUT instead of file",

        parser.add_argument("-R", "--request", action="store_true", default=False, help="request unknown Identities from the network")
        parser.add_argument("-t", action="store", metavar="seconds", type=float, help="identity request timeout before giving up", default=RNS.Transport.PATH_REQUEST_TIMEOUT)
        parser.add_argument("-p", "--print-identity", action="store_true", default=False, help="print identity info and exit")
        parser.add_argument("-P", "--print-private", action="store_true", default=False, help="allow displaying private keys")

        parser.add_argument("-b", "--base64", action="store_true", default=False, help="Use base64-encoded input and output")
        parser.add_argument("-B", "--base32", action="store_true", default=False, help="Use base32-encoded input and output")

        parser.add_argument("--version", action="version", version="rnid {version}".format(version=__version__))

        args = parser.parse_args()

        ops = sum(1 for t in [args.encrypt, args.decrypt, args.validate, args.sign] if t)
        if ops > 1:
            RNS.log("This utility currently only supports one of the encrypt, decrypt, sign or verify operations per invocation", RNS.LOG_ERROR)
            exit(1)

        if not args.read:
            if args.encrypt:
                args.read = args.encrypt
            if args.decrypt:
                args.read = args.decrypt
            if args.sign:
                args.read = args.sign

        identity_str = args.identity
        if args.import_str:
            identity_bytes = None
            try:
                if args.base64:
                    identity_bytes = base64.urlsafe_b64decode(args.import_str)
                elif args.base32:
                    identity_bytes = base64.b32decode(args.import_str)
                else:
                    identity_bytes = bytes.fromhex(args.import_str)
            except Exception as e:
                print("Invalid identity data specified for import: "+str(e))
                exit(41)

            try:
                identity = RNS.Identity.from_bytes(identity_bytes)
            except Exception as e:
                print("Could not create Reticulum identity from specified data: "+str(e))
                exit(42)

            RNS.log("Identity imported")
            if args.base64:
                RNS.log("Public Key  : "+base64.urlsafe_b64encode(identity.get_public_key()).decode("utf-8"))
            elif args.base32:
                RNS.log("Public Key  : "+base64.b32encode(identity.get_public_key()).decode("utf-8"))
            else:
                RNS.log("Public Key  : "+RNS.hexrep(identity.get_public_key(), delimit=False))
            if identity.prv:
                if args.print_private:
                    if args.base64:
                        RNS.log("Private Key : "+base64.urlsafe_b64encode(identity.get_private_key()).decode("utf-8"))
                    elif args.base32:
                        RNS.log("Private Key : "+base64.b32encode(identity.get_private_key()).decode("utf-8"))
                    else:
                        RNS.log("Private Key : "+RNS.hexrep(identity.get_private_key(), delimit=False))
                else:
                    RNS.log("Private Key : Hidden")

            if args.write:
                try:
                    wp = os.path.expanduser(args.write)
                    if not os.path.isfile(wp) or args.force:
                        identity.to_file(wp)
                        RNS.log("Wrote imported identity to "+str(args.write))
                    else:
                        print("File "+str(wp)+" already exists, not overwriting")
                        exit(43)

                except Exception as e:
                    print("Error while writing imported identity to file: "+str(e))
                    exit(44)

            exit(0)

        if not args.generate and not identity_str:
            print("\nNo identity provided, cannot continue\n")
            parser.print_help()
            print("")
            exit(2)

        else:
            targetloglevel = 4
            verbosity = args.verbose
            quietness = args.quiet
            if verbosity != 0 or quietness != 0:
                targetloglevel = targetloglevel+verbosity-quietness

            # Start Reticulum
            reticulum = RNS.Reticulum(configdir=args.config, loglevel=targetloglevel)
            RNS.compact_log_fmt = True
            if args.stdout:
                RNS.loglevel = -1

            if args.generate:
                identity = RNS.Identity()
                if not args.force and os.path.isfile(args.generate):
                    RNS.log("Identity file "+str(args.generate)+" already exists. Not overwriting.", RNS.LOG_ERROR)
                    exit(3)
                else:
                    try:
                        identity.to_file(args.generate)
                        RNS.log("New identity written to "+str(args.generate))
                        exit(0)
                    except Exception as e:
                        RNS.log("An error ocurred while saving the generated Identity.", RNS.LOG_ERROR)
                        RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                        exit(4)

            identity = None
            if len(identity_str) == RNS.Reticulum.TRUNCATED_HASHLENGTH//8*2 and not os.path.isfile(identity_str):
                # Try recalling Identity from hex-encoded hash
                try:
                    destination_hash = bytes.fromhex(identity_str)
                    identity = RNS.Identity.recall(destination_hash)

                    if identity is None:
                        if not args.request:
                            RNS.log("Could not recall Identity for "+RNS.prettyhexrep(destination_hash)+".", RNS.LOG_ERROR)
                            RNS.log("You can query the network for unknown Identities with the -R option.", RNS.LOG_ERROR)
                            exit(5)
                        else:
                            RNS.Transport.request_path(destination_hash)
                            def spincheck():
                                return RNS.Identity.recall(destination_hash) is not None
                            spin(spincheck, "Requesting unknown Identity for "+RNS.prettyhexrep(destination_hash), args.t)

                            if not spincheck():
                                RNS.log("Identity request timed out", RNS.LOG_ERROR)
                                exit(6)
                            else:
                                identity = RNS.Identity.recall(destination_hash)
                                RNS.log(" ".join(["Received Identity", str(identity), "for destination", RNS.prettyhexrep(destination_hash), "from the network"]))

                    else:
                        RNS.log(" ".join(["Recalled Identity", str(identity), "for destination", RNS.prettyhexrep(destination_hash)]))

                except Exception as e:
                    RNS.log("Invalid hexadecimal hash provided", RNS.LOG_ERROR)
                    exit(7)

            else:
                # Try loading Identity from file
                if not os.path.isfile(identity_str):
                    RNS.log("Specified Identity file not found")
                    exit(8)
                else:
                    try:
                        identity = RNS.Identity.from_file(identity_str)
                        RNS.log(" ".join(["Loaded Identity", str(identity), "from", str(identity_str)]))

                    except Exception as e:
                        RNS.log("Could not decode Identity from specified file")
                        exit(9)

            if identity is not None:
                if args.hash:
                    try:
                        aspects = args.hash.split(".")
                        if not len(aspects) > 0:
                            RNS.log("Invalid destination aspects specified", RNS.LOG_ERROR)
                            exit(32)
                        else:
                            app_name = aspects[0]
                            aspects = aspects[1:]
                            if identity.pub is not None:
                                destination = RNS.Destination(identity, RNS.Destination.OUT, RNS.Destination.SINGLE, app_name, *aspects)
                                RNS.log(" ".join(["The", str(args.hash), "destination for this Identity is", RNS.prettyhexrep(destination.hash)]))
                                RNS.log("The full destination specifier is "+str(destination))
                                time.sleep(0.25)
                                exit(0)
                            else:
                                raise KeyError("No public key known")
                    except Exception as e:
                        RNS.log("An error ocurred while attempting to send the announce.", RNS.LOG_ERROR)
                        RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)

                    exit(0)

                if args.announce:
                    try:
                        aspects = args.announce.split(".")
                        if not len(aspects) > 1:
                            RNS.log("Invalid destination aspects specified", RNS.LOG_ERROR)
                            exit(32)
                        else:
                            app_name = aspects[0]
                            aspects = aspects[1:]
                            if identity.prv is not None:
                                destination = RNS.Destination(identity, RNS.Destination.IN, RNS.Destination.SINGLE, app_name, *aspects)
                                RNS.log("Created destination "+str(destination))
                                RNS.log("Announcing destination "+RNS.prettyhexrep(destination.hash))
                                destination.announce()
                                time.sleep(0.25)
                                exit(0)
                            else:
                                destination = RNS.Destination(identity, RNS.Destination.OUT, RNS.Destination.SINGLE, app_name, *aspects)
                                RNS.log(" ".join(["The", str(args.announce), "destination for this Identity is", RNS.prettyhexrep(destination.hash)]))
                                RNS.log("The full destination specifier is "+str(destination))
                                RNS.log("Cannot announce this destination, since the private key is not held")
                                time.sleep(0.25)
                                exit(33)
                    except Exception as e:
                        RNS.log("An error ocurred while attempting to send the announce.", RNS.LOG_ERROR)
                        RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)

                    exit(0)

                if args.print_identity:
                    if args.base64:
                        RNS.log("Public Key  : "+base64.urlsafe_b64encode(identity.get_public_key()).decode("utf-8"))
                    elif args.base32:
                        RNS.log("Public Key  : "+base64.b32encode(identity.get_public_key()).decode("utf-8"))
                    else:
                        RNS.log("Public Key  : "+RNS.hexrep(identity.get_public_key(), delimit=False))
                    if identity.prv:
                        if args.print_private:
                            if args.base64:
                                RNS.log("Private Key : "+base64.urlsafe_b64encode(identity.get_private_key()).decode("utf-8"))
                            elif args.base32:
                                RNS.log("Private Key : "+base64.b32encode(identity.get_private_key()).decode("utf-8"))
                            else:
                                RNS.log("Private Key : "+RNS.hexrep(identity.get_private_key(), delimit=False))
                        else:
                            RNS.log("Private Key : Hidden")
                    exit(0)

                if args.export:
                    if identity.prv:
                            if args.base64:
                                RNS.log("Exported Identity : "+base64.urlsafe_b64encode(identity.get_private_key()).decode("utf-8"))
                            elif args.base32:
                                RNS.log("Exported Identity : "+base64.b32encode(identity.get_private_key()).decode("utf-8"))
                            else:
                                RNS.log("Exported Identity : "+RNS.hexrep(identity.get_private_key(), delimit=False))
                    else:
                        RNS.log("Identity doesn't hold a private key, cannot export")
                        exit(50)

                    exit(0)

                if args.validate:
                    if not args.read and args.validate.lower().endswith("."+SIG_EXT):
                        args.read = str(args.validate).replace("."+SIG_EXT, "")

                    if not os.path.isfile(args.validate):
                        RNS.log("Signature file "+str(args.read)+" not found", RNS.LOG_ERROR)
                        exit(10)

                    if not os.path.isfile(args.read):
                        RNS.log("Input file "+str(args.read)+" not found", RNS.LOG_ERROR)
                        exit(11)

                data_input = None
                if args.read:
                    if not os.path.isfile(args.read):
                        RNS.log("Input file "+str(args.read)+" not found", RNS.LOG_ERROR)
                        exit(12)
                    else:
                        try:
                            data_input = open(args.read, "rb")
                        except Exception as e:
                            RNS.log("Could not open input file for reading", RNS.LOG_ERROR)
                            RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                            exit(13)

                # TODO: Actually expand this to a good solution
                # probably need to create a wrapper that takes
                # into account not closing stdin when done
                # elif args.stdin:
                #     data_input = sys.stdin

                data_output = None
                if args.encrypt and not args.write and not args.stdout and args.read:
                    args.write = str(args.read)+"."+ENCRYPT_EXT

                if args.decrypt and not args.write and not args.stdout and args.read and args.read.lower().endswith("."+ENCRYPT_EXT):
                    args.write = str(args.read).replace("."+ENCRYPT_EXT, "")

                if args.sign and identity.prv is None:
                    RNS.log("Specified Identity does not hold a private key. Cannot sign.", RNS.LOG_ERROR)
                    exit(14)

                if args.sign and not args.write and not args.stdout and args.read:
                    args.write = str(args.read)+"."+SIG_EXT

                if args.write:
                    if not args.force and os.path.isfile(args.write):
                        RNS.log("Output file "+str(args.write)+" already exists. Not overwriting.", RNS.LOG_ERROR)
                        exit(15)
                    else:
                        try:
                            data_output = open(args.write, "wb")
                        except Exception as e:
                            RNS.log("Could not open output file for writing", RNS.LOG_ERROR)
                            RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                            exit(15)

                # TODO: Actually expand this to a good solution
                # probably need to create a wrapper that takes
                # into account not closing stdout when done
                # elif args.stdout:
                #     data_output = sys.stdout

                if args.sign:
                    if identity.prv is None:
                        RNS.log("Specified Identity does not hold a private key. Cannot sign.", RNS.LOG_ERROR)
                        exit(16)

                    if not data_input:
                        if not args.stdout:
                            RNS.log("Signing requested, but no input data specified", RNS.LOG_ERROR)
                        exit(17)
                    else:
                        if not data_output:
                            if not args.stdout:
                                RNS.log("Signing requested, but no output specified", RNS.LOG_ERROR)
                            exit(18)

                        if not args.stdout:
                            RNS.log("Signing "+str(args.read))

                        try:
                            data_output.write(identity.sign(data_input.read()))
                            data_output.close()
                            data_input.close()

                            if not args.stdout:
                                if args.read:
                                    RNS.log(" ".join([ "File", str(args.read), "signed with", str(identity), "to", str(args.write) ]))
                                    exit(0)

                        except Exception as e:
                            if not args.stdout:
                                RNS.log("An error ocurred while encrypting data.", RNS.LOG_ERROR)
                                RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                            try:
                                data_output.close()
                            except:
                                pass
                            try:
                                data_input.close()
                            except:
                                pass
                            exit(19)

                if args.validate:
                    if not data_input:
                        if not args.stdout:
                            RNS.log("Signature verification requested, but no input data specified", RNS.LOG_ERROR)
                        exit(20)
                    else:
                        # if not args.stdout:
                        #     RNS.log("Verifying "+str(args.validate)+" for "+str(args.read))

                        try:
                            try:
                                sig_input = open(args.validate, "rb")
                            except Exception as e:
                                RNS.log("An error ocurred while opening "+str(args.validate)+".", RNS.LOG_ERROR)
                                RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                                exit(21)

                            validated = identity.validate(sig_input.read(), data_input.read())
                            sig_input.close()
                            data_input.close()

                            if not validated:
                                if not args.stdout:
                                    RNS.log(" ".join(["Signature", str(args.validate), "for file", str(args.read), "is invalid"]), RNS.LOG_ERROR)
                                exit(22)
                            else:
                                if not args.stdout:
                                    RNS.log(" ".join(["Signature", str(args.validate), "for file", str(args.read), "made by Identity", str(identity), "is valid"]))
                                exit(0)

                        except Exception as e:
                            if not args.stdout:
                                RNS.log("An error ocurred while validating signature.", RNS.LOG_ERROR)
                                RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                            try:
                                data_output.close()
                            except:
                                pass
                            try:
                                data_input.close()
                            except:
                                pass
                            exit(23)

                if args.encrypt:
                    if not data_input:
                        if not args.stdout:
                            RNS.log("Encryption requested, but no input data specified", RNS.LOG_ERROR)
                        exit(24)
                    else:
                        if not data_output:
                            if not args.stdout:
                                RNS.log("Encryption requested, but no output specified", RNS.LOG_ERROR)
                            exit(25)

                        if not args.stdout:
                            RNS.log("Encrypting "+str(args.read))

                        try:
                            more_data = True
                            while more_data:
                                chunk = data_input.read(CHUNK_SIZE)
                                if chunk:
                                    data_output.write(identity.encrypt(chunk))
                                else:
                                    more_data = False
                            data_output.close()
                            data_input.close()
                            if not args.stdout:
                                if args.read:
                                    RNS.log(" ".join(["File", str(args.read), "encrypted for", str(identity), "to", str(args.write)]))
                                    exit(0)

                        except Exception as e:
                            if not args.stdout:
                                RNS.log("An error ocurred while encrypting data.", RNS.LOG_ERROR)
                                RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                            try:
                                data_output.close()
                            except:
                                pass
                            try:
                                data_input.close()
                            except:
                                pass
                            exit(26)

                if args.decrypt:
                    if identity.prv is None:
                        RNS.log("Specified Identity does not hold a private key. Cannot decrypt.", RNS.LOG_ERROR)
                        exit(27)

                    if not data_input:
                        if not args.stdout:
                            RNS.log("Decryption requested, but no input data specified", RNS.LOG_ERROR)
                        exit(28)
                    else:
                        if not data_output:
                            if not args.stdout:
                                RNS.log("Decryption requested, but no output specified", RNS.LOG_ERROR)
                            exit(29)

                        if not args.stdout:
                            RNS.log("".join(["Decrypting ", str(args.read), "..."]))

                        try:
                            more_data = True
                            while more_data:
                                chunk = data_input.read(CHUNK_SIZE)
                                if chunk:
                                    plaintext = identity.decrypt(chunk)
                                    if plaintext is None:
                                        if not args.stdout:
                                            RNS.log("Data could not be decrypted with the specified Identity")
                                        exit(30)
                                    else:
                                        data_output.write(plaintext)
                                else:
                                    more_data = False
                            data_output.close()
                            data_input.close()
                            if not args.stdout:
                                if args.read:
                                    RNS.log(" ".join(["File", str(args.read), "decrypted with", str(identity), "to", str(args.write)]))
                                    exit(0)

                        except Exception as e:
                            if not args.stdout:
                                RNS.log("An error ocurred while decrypting data.", RNS.LOG_ERROR)
                                RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                            try:
                                data_output.close()
                            except:
                                pass
                            try:
                                data_input.close()
                            except:
                                pass
                            exit(31)

    except KeyboardInterrupt:
        print("")
        exit(255)


if __name__ == "__main__":
    main()
