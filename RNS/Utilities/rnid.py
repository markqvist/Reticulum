#!/usr/bin/env python3

# Reticulum License
#
# Copyright (c) 2016-2025 Mark Qvist
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# - The Software shall not be used in any kind of system which includes amongst
#   its functions the ability to purposefully do harm to human beings.
#
# - The Software shall not be used, directly or indirectly, in the creation of
#   an artificial intelligence, machine learning or language model training
#   dataset, including but not limited to any use that contributes to the
#   training or development of such a model or algorithm.
#
# - The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
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
import io
import base64

from RNS._version import __version__
from RNS.vendor import umsgpack as mp
from RNS.vendor.configobj import ConfigObj
from RNS.vendor.validate import Validator
from RNS.Cryptography.Hashes import sha256
from RNS.Cryptography.Hashes import file_sha256

APP_NAME = "rns"
DEFAULT_ASPECTS = f"{APP_NAME}.id"
NO_MESSAGE = 0x01
NO_META    = 0x02

PRV_EXT      = "rid"
PUB_EXT      = "pub"
SIG_EXT      = "rsg"
MSG_EXT      = "rsm"
ENCRYPT_EXT  = "rfe"
CHUNK_BLOCKS = 1024*1024
ENC_CHUNK    = CHUNK_BLOCKS*RNS.Identity.AES256_BLOCKSIZE
DEC_CHUNK    = ENC_CHUNK + RNS.Cryptography.Token.TOKEN_OVERHEAD*2

RSG_HASHTYPES = ["sha256"]

R_OK                = 0
R_NO_SIG_FILE       = 1
R_NO_IDENTITY       = 2
R_NO_PUBKEY         = 3
R_NO_PRVKEY         = 4
R_NO_KEYS           = 5
R_NO_FILE           = 6
R_INVALID_FILE      = 7
R_INVALID_IDENTITY  = 8
R_INVALID_ASPECTS   = 9
R_INVALID_SIGNATURE = 10
R_FILE_EXISTS       = 11
R_DECRYPT_FAILED    = 12
R_INVALID_ARGS      = 250
R_SEQUENCE_ERROR    = 251
R_READ_ERROR        = 252
R_WRITE_ERROR       = 253
R_UNKNOWN_ERROR     = 254
R_INTERRUPTED       = 255

reticulum = None

def validate_args(args):
    ops = 0;
    for o in [args.encrypt, args.decrypt, args.validate, args.sign, args.sign_message]:
        if o: ops += 1
    if ops > 1: print("This utility currently only supports one of the encrypt, decrypt, sign or verify operations per invocation"); exit(1)

    g = 0;
    for a in [args.import_pub, args.import_prv, args.identity, args.generate]:
        if a: g += 1
    if g > 1: print("The -i, -g, -m and -M args are mutually exclusive"); exit(1)

    g = 0;
    for a in [args.base64, args.base32, args.base256, args.hex]:
        if a: g += 1
    if g > 1: print("The -b, -B, --hex and --base256 args are mutually exclusive"); exit(1)

    return True

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Identity & Encryption Utility")

        # Identity Resolution
        parser.add_argument("--config", metavar="path", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
        parser.add_argument("-i", "--identity", metavar="rid", action="store", default=None, help="hexadecimal Reticulum identity or destination hash, or path to Identity file", type=str)
        parser.add_argument("-g", "--generate", metavar="path", action="store", default=None, help="generate a new Identity and save to path")
        parser.add_argument("-m", "--import-pub", dest="import_pub", metavar="rid", action="store", default=None, help="import public Reticulum identity in hex, base32 or base64 format, or from file", type=str)
        parser.add_argument("-M", "--import-prv", dest="import_prv", metavar="rid", action="store", default=None, help="import Reticulum identity in hex, base32 or base64 format, or from file", type=str)
        parser.add_argument("-x", "--export-pub", action="store_true", default=None, help="export public identity to hex, base32 or base64 format")
        parser.add_argument("-X", "--export-prv", action="store_true", default=None, help="export private identity to hex, base32 or base64 format, or to file")

        # Verbosity Control
        parser.add_argument("-v", "--verbose", action="count", default=0, help="increase verbosity")
        parser.add_argument("-q", "--quiet", action="count", default=0, help="decrease verbosity")

        # Operations
        parser.add_argument("-a", "--announce", metavar="aspects", action="store", nargs="?", const=DEFAULT_ASPECTS, default=None, help="announce a destination based on this Identity")
        parser.add_argument("-H", "--hash", metavar="aspects", action="store", default=None, help="show destination hashes for other aspects for this Identity")
        parser.add_argument("-d", "--decrypt", metavar="file", action="store", nargs="*", default=None, help="decrypt file")
        parser.add_argument("-e", "--encrypt", metavar="file", action="store", nargs="*", default=None, help="encrypt file")
        parser.add_argument("-V", "--validate", metavar="path", action="store", nargs="*", default=None, help="validate signature")
        parser.add_argument("-s", "--sign", metavar="path", action="store", nargs="*", default=None, help="sign file")
        parser.add_argument("-S", "--sign-message", metavar="text", action="store", nargs="?", const=NO_MESSAGE, default=None, help="create embedded signed message")
        parser.add_argument("-E", "--embed-meta", metavar="path", action="store", nargs="?", const=NO_META, default=None, help="embed metadata structure from file")
        parser.add_argument("--meta-spec", metavar="path", action="store", nargs="?", default=None, help="validate metadata for embedding with spec from file")
        parser.add_argument("--raw", action="store_true", default=False, help="sign raw input data instead of hashing first")

        # I/O Control
        parser.add_argument("-w", "--write", metavar="path", action="store", default=None, help="output file path", type=str)
        parser.add_argument("-r", "--read", metavar="path", action="store", default=None, help="input file path for operations with optional file input", type=str)
        parser.add_argument("-f", "--force", action="store_true", default=None, help="write output even if it overwrites existing files")
        parser.add_argument("-I", "--stdin", action="store_true", default=False, help=argparse.SUPPRESS) # help="read input from STDIN instead of file"
        parser.add_argument("-O", "--stdout", action="store_true", default=False, help=argparse.SUPPRESS) # help="write output to STDOUT instead of file"

        # Information Flow
        parser.add_argument("-R", "--request", action="store_true", default=False, help="request unknown Identities from the network")
        parser.add_argument("-N", "--no-cache", action="store_true", default=False, help="never used cached or network-sourced information")
        parser.add_argument("-t", action="store", metavar="seconds", type=float, help="identity request timeout before giving up", default=RNS.Transport.PATH_REQUEST_TIMEOUT)
        parser.add_argument("-p", "--print-identity", action="store_true", default=False, help="print identity info and exit")
        parser.add_argument("-P", "--print-private", action="store_true", default=False, help="allow displaying private keys")

        # Formatting Control
        parser.add_argument("-B", "--base32", action="store_true", default=False, help="Use base32-encoded input and output")
        parser.add_argument("-b", "--base64", action="store_true", default=False, help="Use base64-encoded input and output")
        parser.add_argument("-U", "--base256", action="store_true", default=False, help="Use base256-encoded input and output")
        parser.add_argument("-F", "--hex", action="store_true", default=False, help="Use hex-encoded input and output")
        parser.add_argument("--meta", action="store_true", default=False, help="Display RSM metadata if available")

        parser.add_argument("--version", action="version", version="rnid {version}".format(version=__version__))
        
        args = parser.parse_args()
        validate_args(args)

        op_requires_identity = (args.sign or args.sign_message or args.encrypt or args.decrypt or args.announce or args.write
                                or args.print_identity or args.print_identity or args.export_pub or args.export_prv)

        identity = get_operating_identity(args, allow_none=not op_requires_identity, no_cache=args.no_cache); op = False
        if not identity and op_requires_identity: print("Could not get working identity"); exit(R_NO_IDENTITY)
        if args.print_identity: print_identity_information(args, identity); op = True
        if args.export_pub: export_pub_identity(args, identity); op = True
        if args.export_prv: export_prv_identity(args, identity); op = True
        if args.hash: print_hash_information(args, identity or args.identity); op = True
        if args.announce: announce(args, identity); op = True
        if args.validate: validate(args, identity or args.identity); op = True
        if args.sign: sign(args, identity); op = True
        if args.sign_message: sign_message(args, identity); op = True
        if args.encrypt: encrypt(args, identity); op = True
        if args.decrypt: decrypt(args, identity); op = True
        if args.write: write_identity(args, identity); op = True
        if args.generate: op = True

        if not op: parser.print_help()

        exit(0)

    except KeyboardInterrupt: print(""); exit(R_INTERRUPTED)


#####################
# Reticulum Helpers #
#####################

def ensure_reticulum(args):
    global reticulum
    if not reticulum:
        targetloglevel = 4; verbosity = args.verbose; quietness = args.quiet
        if verbosity != 0 or quietness != 0: targetloglevel = targetloglevel+verbosity-quietness
        reticulum = RNS.Reticulum(configdir=args.config, loglevel=targetloglevel)
        RNS.compact_log_fmt = True
        if args.stdout: RNS.loglevel = -1


#################################
# Identity Loading & Resolution #
#################################

def get_operating_identity(args, allow_none=False, no_cache=False):
    global reticulum
    identity = None

    if args.generate:
        identity = RNS.Identity()
        if not args.force and os.path.isfile(args.generate):
            print("Identity file "+str(args.generate)+" already exists. Not overwriting.")
            exit(R_FILE_EXISTS)
        
        else:
            try: identity.to_file(args.generate); print(f"New identity {identity} written to {args.generate}")
            except Exception as e: print(f"An error ocurred while saving the generated Identity: {e}"); exit(R_WRITE_ERROR)

    elif args.identity:
        load_path = None
        try: load_path = os.path.expanduser(args.identity)
        except: pass

        # Attempt to load Identity from .rid file
        if load_path and os.path.isfile(load_path):
            try:
                identity = RNS.Identity.from_file(load_path)
                print(f"Loaded Identity {identity} from {load_path}")
                if not identity.get_private_key() or not identity.get_public_key():
                    raise SystemError("Missing key data in loaded identity")

            except Exception as e: print(f"Could not load Identity from specified file: {e}"); exit(R_INVALID_IDENTITY)

        elif no_cache:
            if allow_none: return None
            else: print("Could not resolve identity"); exit(R_NO_IDENTITY)

        # Attempt to recall Identity from hex-encoded hash
        elif len(args.identity) == RNS.Reticulum.TRUNCATED_HASHLENGTH//8*2:
            try:
                ensure_reticulum(args)
                requested_hash = bytes.fromhex(args.identity)
                identity = RNS.Identity.recall(requested_hash) or RNS.Identity.recall(requested_hash, from_identity_hash=True)

                if identity == None:
                    if allow_none and not args.request: return None
                    elif not args.request:
                        print("Could not recall Identity for "+RNS.prettyhexrep(requested_hash)+".")
                        print("You can query the network for unknown Identities with the -R option.")
                        exit(R_NO_IDENTITY)
                    
                    else:
                        id_destination_hash = RNS.Destination.hash_from_name_and_identity(DEFAULT_ASPECTS, requested_hash)
                        RNS.Transport.request_path(requested_hash)      # Acquire if this was a destination hash
                        RNS.Transport.request_path(id_destination_hash) # Acquire if this was an identity hash
                        
                        def spincheck():
                            received = RNS.Identity.recall(requested_hash) or RNS.Identity.recall(requested_hash, from_identity_hash=True)
                            return received != None
                        spin(spincheck, "Requesting unknown Identity for "+RNS.prettyhexrep(requested_hash), args.t)

                        if not spincheck():
                            print("Identity request timed out");
                            if not allow_none: exit(R_NO_IDENTITY)
                            else: return None
                        
                        else:
                            identity = RNS.Identity.recall(requested_hash) or RNS.Identity.recall(requested_hash, from_identity_hash=True)
                            print("Received Identity "+str(identity)+" for destination "+RNS.prettyhexrep(requested_hash)+" from the network")

                else:
                    ident_str = str(identity)
                    hash_str  = RNS.prettyhexrep(requested_hash)
                    if ident_str == hash_str: print(f"Recalled Identity {ident_str}")
                    else:                     print(f"Recalled Identity {ident_str} for destination {hash_str}")

                if identity and identity.hash: reticulum._retain_identity(identity.hash)

            except Exception as e: print(f"Invalid hexadecimal hash provided: {e}"); exit(R_INVALID_IDENTITY)

    elif args.import_pub or args.import_prv:
        prvsize = RNS.Identity.KEYSIZE//8
        pubsize = prvsize
        identity_bytes = None
        if args.import_pub:
            try:
                identity_bytes = None
                import_path = os.path.expanduser(args.import_pub)
                if os.path.isfile(import_path):
                    try:
                        with open(import_path, "rb") as fh: file_input = fh.read()
                        if file_input and len(file_input) == pubsize:
                            identity_bytes = file_input
                            print(f"Reticulum Identity imported from {import_path}")
                    except: pass

                if not identity_bytes:
                    if len(args.import_pub) == pubsize*2:
                        try:
                            identity_bytes = bytes.fromhex(args.import_pub)
                            print("Reticulum Identity imported from hex input")
                        except: pass

                if not identity_bytes:
                    try:
                        b32_decoded = base64.b32decode(args.import_pub)
                        if len(b32_decoded) == pubsize:
                            identity_bytes = b32_decoded
                            print("Reticulum Identity imported from base32 input")
                    except: pass

                if not identity_bytes:
                    try:
                        b64_decoded = base64.urlsafe_b64decode(args.import_pub)
                        if len(b64_decoded) == pubsize:
                            identity_bytes = b64_decoded
                            print("Reticulum Identity imported from base64 input")
                    except: pass

                if not identity_bytes: print("Could not decode specified data to a valid public Reticulum Identity"); exit(R_INVALID_IDENTITY)

            except Exception as e: print("Invalid identity data specified for private identity import: "+str(e)); exit(R_INVALID_IDENTITY)

        elif args.import_prv:
            try:
                identity_bytes = None
                import_path = os.path.expanduser(args.import_prv)
                if os.path.isfile(import_path):
                    try:
                        with open(import_path, "rb") as fh: file_input = fh.read()
                        if file_input and len(file_input) == prvsize:
                            identity_bytes = file_input
                            print(f"Reticulum Identity imported from {import_path}")
                    except: pass

                if not identity_bytes:
                    if len(args.import_prv) == prvsize*2:
                        try:
                            identity_bytes = bytes.fromhex(args.import_prv)
                            print("Reticulum Identity imported from hex input")
                        except: pass

                if not identity_bytes:
                    try:
                        b32_decoded = base64.b32decode(args.import_prv)
                        if len(b32_decoded) == prvsize:
                            identity_bytes = b32_decoded
                            print("Reticulum Identity imported from base32 input")
                    except: pass

                if not identity_bytes:
                    try:
                        b64_decoded = base64.urlsafe_b64decode(args.import_prv)
                        if len(b64_decoded) == prvsize:
                            identity_bytes = b64_decoded
                            print("Reticulum Identity imported from base64 input")
                    except: pass

                if not identity_bytes: print("Could not decode specified data to a valid private Reticulum Identity"); exit(R_INVALID_IDENTITY)

            except Exception as e: print("Invalid identity data specified for private identity import: "+str(e)); exit(R_INVALID_IDENTITY)

        if args.import_prv:
            try: identity = RNS.Identity.from_bytes(identity_bytes)
            except Exception as e: print("Could not create Reticulum identity from specified data: "+str(e)); exit(R_INVALID_IDENTITY)

        elif args.import_pub:
            try:
                identity = RNS.Identity(create_keys=False)
                identity.load_public_key(identity_bytes)
            except Exception as e: print("Could not create Reticulum identity from specified data: "+str(e)); exit(R_INVALID_IDENTITY)

    return identity


######################
# Network Operations #
######################

def announce(args, identity):
    try:
        ensure_reticulum(args)
        aspects = args.announce.split(".")
        if not len(aspects) > 1: print("Invalid destination aspects specified"); exit(R_INVALID_ASPECTS)
        else:
            app_name = aspects[0]; aspects = aspects[1:]
            if not identity.get_private_key(): print("Cannot announce this destination, since the private key is not held"); exit(R_NO_PRVKEY)
            else:
                destination = RNS.Destination(identity, RNS.Destination.IN, RNS.Destination.SINGLE, app_name, *aspects)
                print(f"Announcing {args.announce} destination {RNS.prettyhexrep(destination.hash)} for identity {identity}")
                destination.announce(); time.sleep(0.25)

    except Exception as e: print(f"An error ocurred while attempting to send the announce: {e}"); exit(R_UNKNOWN_ERROR)


########################################
# Canonical RSG Manipulation Functions #
########################################

def get_rsg_data(rsg):
    rsg_data = None
    if   type(rsg) == bytes:             rsg_data = rsg
    elif type(rsg) == io.BufferedReader: rsg_data = rsg.read()
    elif type(rsg) == str:
        try:                             rsg_data = base64.urlsafe_b64decode(rsg)
        except:                          pass
        try:                             rsg_data = base64.b32decode(rsg.strip(RSG_PADDING))
        except:                          pass
        try:                             rsg_data = bytes.fromhex(rsg.strip(RSG_PADDING))
        except:                          pass
        try:                             rsg_data = RNS.b256_to_bytes(rsg.strip(RSG_PADDING.decode("utf-8")))
        except:                          pass

    return rsg_data

def extract_signed_rsg_data(rsg):
    siglen   = RNS.Identity.SIGLENGTH//8
    rsg_data = get_rsg_data(rsg)
    envelope = rsg_data[siglen:]

    try: return mp.unpackb(envelope)
    except: return None

def get_rsg_hash(message):
    sha = None
    if   type(message) == bytes:             sha = sha256(message)
    elif type(message) == str:               sha = sha256(message.encode("utf-8"))
    elif type(message) == io.BufferedReader: sha = file_sha256(message)
    else:                                    raise TypeError(f"Invalid input type {type(message)} for rsg creation")

    if not sha: raise ValueError("Hash calculation for rsg signature input failed")
    return sha

def rsg_is_legacy_format(rsg):
    rsg_data = get_rsg_data(rsg)
    if not rsg_data: return False
    return True if len(rsg_data) == RNS.Identity.SIGLENGTH//8 else False

def validate_rsg(rsg, message=None, required_signer=None):
    if not message: raise ValueError(f"No message specified for rsg validation")
    if not type(required_signer) in [RNS.Identity, bytes, type(None)]: raise TypeError(f"Invalid required signer type {type(required_signer)}")
    
    if   type(required_signer) == RNS.Identity: required_signer_hash = required_signer.hash
    elif type(required_signer) == bytes:        required_signer_hash = required_signer
    else:                                       required_signer_hash = None

    siglen = RNS.Identity.SIGLENGTH//8
    rsg_data = get_rsg_data(rsg)
    rsg_hash = get_rsg_hash(message)

    if len(rsg_data) == siglen: raise ValueError(f"Cannot validate legacy rsg format")

    if not rsg_data: return False, None, None
    else:
        if len(rsg_data) < siglen+1: return False, None, None
        else:
            signing_identity = None
            signature        = rsg_data[:siglen]
            envelope         = rsg_data[siglen:]

            try: signed_data = mp.unpackb(envelope)
            except: return False, None, None

            if not "hashtype" in signed_data or not "hash" in signed_data: return False, None, None
            if not signed_data["hashtype"] in RSG_HASHTYPES:               return False, None, None
            if not "meta" in signed_data:                                  return False, None, None
            if not "signer" in signed_data["meta"]:                        return False, None, None
            if not "pubkey" in signed_data["meta"]:                        return False, None, None

            try:
                if type(required_signer) == RNS.Identity:
                    signing_identity = required_signer
                
                else:
                    signing_identity = RNS.Identity(create_keys=False)
                    signing_identity.load_public_key(signed_data["meta"]["pubkey"])

            except: return False, None, None

            if required_signer_hash == None: required_signer_hash = signing_identity.hash

            if not signing_identity:                                       return False, None, None
            if not signing_identity.hash == required_signer_hash:          return False, None, signing_identity
            if signed_data["hash"] != rsg_hash:                            return False, None, signing_identity
            else:
                if not signing_identity.validate(signature, envelope):     return False, signed_data, signing_identity
                else:                                                      return True,  signed_data, signing_identity

            return False, signed_data, signing_identity

def create_rsg(signer_identity, message, embed=False, meta=None, output="bin"):
    if not output in ["bin", "hex", "base32", "base256", "base64"]: raise TypeError(f"Invalid output format for rsg creation")
    if not type(signer_identity) == RNS.Identity:                   raise TypeError(f"{signer_identity} is not a Reticulum Identity")
    if not signer_identity.get_private_key():                       raise ValueError(f"{signer_identity} does not hold a private key")

    signed_data = { "hashtype": "sha256", "hash": get_rsg_hash(message),
                    "meta": { "signer": signer_identity.hash,
                              "pubkey": signer_identity.get_public_key(),
                              "note"  : None } } # TODO: Remove default note field in 1.2.9

    if embed:
        if type(message) == str: message = message.encode("utf-8")
        signed_data["message"] = message

    if meta and type(meta) == dict:
        for key in meta:
            if not key in signed_data["meta"]: signed_data["meta"][key] = meta[key]

    envelope  = mp.packb(signed_data)
    signature = signer_identity.sign(envelope)
    rsg_data  = signature+envelope

    if   output == "bin":     rsg = rsg_data
    elif output == "hex":     rsg = RNS.hexrep(rsg_data, delimit=False).encode("ascii")
    elif output == "base32":  rsg = base64.b32encode(rsg_data)
    elif output == "base64":  rsg = base64.urlsafe_b64encode(rsg_data)
    elif output == "base256": rsg = RNS.b256rep(rsg_data)
    else:                     return None

    return rsg

RSG_ASCII_HEADER = b"#### Start of rsg data "
RSG_ASCII_FOOTER = b" End of rsg data ####"
RSG_ASCII_ROW_WIDTH = 64
RSG_PADDING = b"="
def wrap_rsg(rsg):
    if type(rsg) == str: return wrap_rsg_str(rsg)
    def pad(chunk): return chunk+(RSG_ASCII_ROW_WIDTH-len(chunk))*RSG_PADDING
    header = RSG_ASCII_HEADER+b"#"*(RSG_ASCII_ROW_WIDTH-len(RSG_ASCII_HEADER))
    footer = b"#"*(RSG_ASCII_ROW_WIDTH-len(RSG_ASCII_FOOTER))+RSG_ASCII_FOOTER
    wrapped = header+b"\n"
    read = 0
    while len(rsg):
        chunk = rsg[:RSG_ASCII_ROW_WIDTH]
        if len(chunk) < RSG_ASCII_ROW_WIDTH: chunk = pad(chunk)
        wrapped += chunk+b"\n"; read += len(chunk)
        rsg = rsg[len(chunk):]

    wrapped += footer
    return wrapped.decode("ascii")

def wrap_rsg_str(rsg):
    def pad(chunk): return chunk+(RSG_ASCII_ROW_WIDTH-len(chunk))*RSG_PADDING.decode("utf-8")
    header = RSG_ASCII_HEADER.decode("utf-8")+"#"*(RSG_ASCII_ROW_WIDTH-len(RSG_ASCII_HEADER.decode("utf-8")))
    footer = "#"*(RSG_ASCII_ROW_WIDTH-len(RSG_ASCII_FOOTER.decode("utf-8")))+RSG_ASCII_FOOTER.decode("utf-8")
    wrapped = header+"\n"
    read = 0
    while len(rsg):
        chunk = rsg[:RSG_ASCII_ROW_WIDTH]
        if len(chunk) < RSG_ASCII_ROW_WIDTH: chunk = pad(chunk)
        wrapped += chunk+"\n"; read += len(chunk)
        rsg = rsg[len(chunk):]

    wrapped += footer
    return wrapped

def unwrap_rsg(wrapped_rsg):
    unwrapped = ""
    if type(wrapped_rsg) == bytes: wrapped_rsg = wrapped_rsg.decode("ascii")
    elif type(wrapped_rsg) == str: pass
    else: return None

    for line in wrapped_rsg.splitlines():
        if not line.strip():     continue
        if line.startswith("#"): continue
        unwrapped += line

    return unwrapped if unwrapped else None

def rsg_meta_from_file(path, spec_path=None):
    if spec_path: meta_spec = ConfigObj(spec_path)
    else:         meta_spec = None
    parsed = ConfigObj(path, configspec=meta_spec)

    if meta_spec:
        validation = parsed.validate(Validator())
        if not validation == True: raise ValueError("Metadata did not pass spec validation")

    return parsed.dict()

def rsg_meta_from_str(meta, spec=None):
    if spec: meta_spec = ConfigObj(spec.splitlines())
    else:    meta_spec = None
    parsed = ConfigObj(meta.splitlines(), configspec=meta_spec)

    if meta_spec:
        validation = parsed.validate(Validator())
        if not validation == True: raise ValueError("Metadata did not pass spec validation")

    return parsed.dict()

###################################
# Signing & Validation Operations #
###################################

def validate(args, identity, __recursive=False):
    if type(args.validate) == list:
        paths     = args.validate.copy()
        validated = 0
        for path in paths:
            args.validate = path
            code = validate(args, identity, __recursive=True)
            if code != 0: print(f"Sequence error on recursive signature validation"); exit(R_SEQUENCE_ERROR)
            else:         validated += 1

        if len(paths) != validated: print(f"Sequence error on recursive signature validation"); exit(R_SEQUENCE_ERROR)
        else:                       exit(R_OK)

    msg_ext                            = f".{MSG_EXT}"
    sig_ext                            = f".{SIG_EXT}"
    validate_path                      = os.path.expanduser(args.validate)
    path_is_msgfile                    = validate_path.lower().endswith(msg_ext)
    path_is_sigfile                    = validate_path.lower().endswith(sig_ext)
    if path_is_sigfile: signature_path = validate_path; file_path = validate_path[:-len(sig_ext)]
    else:               signature_path = f"{validate_path}{sig_ext}"; file_path = validate_path
    signature_exists                   = os.path.isfile(signature_path)
    file_exists                        = os.path.isfile(file_path)

    if path_is_msgfile:      return validate_message(args, identity, __recursive=__recursive)
    if not file_exists:      print(f"The validation target \"{file_path}\" does not exist"); exit(R_NO_FILE)
    if not signature_exists: print(f"No signature file exists for \"{file_path}\""); exit(R_NO_FILE)

    try:
        with open(signature_path, "rb") as fh: is_legacy_format = rsg_is_legacy_format(fh)
    except Exception as e: print(f"Could not detect rsg format: {e}"); exit(R_UNKNOWN_ERROR)

    if not is_legacy_format:
        try:
            with open(signature_path, "rb") as fh: rsg = fh.read()
        except Exception as e: print(f"Could not read rsg: {e}"); exit(R_READ_ERROR)

        if type(identity) == str:
            if not len(identity) == RNS.Reticulum.TRUNCATED_HASHLENGTH//8*2: print("Invalid identity hash length"); exit(R_INVALID_IDENTITY)
            try: identity = bytes.fromhex(identity)
            except Exception as e: print(f"Invalid identity hash: {e}"); exit(R_INVALID_IDENTITY)

        try:
            with open(file_path, "rb") as fh:
                try:
                    valid, signed_data, signing_identity = validate_rsg(rsg, message=fh, required_signer=identity)
                    identity_str = RNS.prettyhexrep(identity) if type(identity) == bytes else f"{identity}"
                    signer_description = f"\nThis file was NOT signed by {identity_str or signing_identity}" if identity else ""
                    if not valid: print(f"Invalid signature {signature_path} for file {file_path}{signer_description}"); exit(R_INVALID_SIGNATURE)
                    else:         print(f"Signature is valid, the file {file_path} was signed by {signing_identity}"); return exit(R_OK) if not __recursive else R_OK

                except Exception as e: print(f"Error while validating {signature_path}: {e}"); exit(R_UNKNOWN_ERROR)

        except Exception as e: print(f"Could not read {file_path}: {e}"); exit(R_READ_ERROR)

    else:
        if type(identity) != RNS.Identity: print(f"Cannot validate legacy rsg signatures without an explicit required identity"); exit(R_NO_IDENTITY)
        try:
            with open(signature_path, "rb") as fh: signature = fh.read()
        except Exception as e: print(f"Could not read signature: {e}"); exit(R_READ_ERROR)

        try:
            with open(file_path, "rb") as fh: valid = identity.validate(signature, fh.read())
            if not valid: print(f"Invalid signature {signature_path} for file {file_path}\nThis file was NOT signed by {identity}"); exit(R_INVALID_SIGNATURE)
            else:         print(f"Signature is valid, the file {file_path} was signed by {identity}"); exit(R_OK)
        
        except Exception as e: print(f"Could not validate signature: {e}"); exit(R_READ_ERROR)

def validate_message(args, identity, __recursive=False):
    msg_ext                            = f".{MSG_EXT}"
    validate_path                      = os.path.expanduser(args.validate)
    path_is_msgfile                    = validate_path.lower().endswith(msg_ext)
    if path_is_msgfile: signature_path = validate_path
    signature_exists                   = os.path.isfile(signature_path)

    if not signature_exists: print(f"The signature file \"{signature_path}\" does not exist"); exit(R_NO_FILE)

    try:
        with open(signature_path, "rb") as fh: rsg = fh.read()
    except Exception as e: print(f"Could not read rsg: {e}"); exit(R_READ_ERROR)

    if type(identity) == str:
        if not len(identity) == RNS.Reticulum.TRUNCATED_HASHLENGTH//8*2: print("Invalid identity hash length"); exit(R_INVALID_IDENTITY)
        try: identity = bytes.fromhex(identity)
        except Exception as e: print(f"Invalid identity hash: {e}"); exit(R_INVALID_IDENTITY)

    try:
        rsm_contents = extract_signed_rsg_data(rsg)
        if not "message" in rsm_contents: print(f"No embedded message in {signature_path}"); exit(R_INVALID_SIGNATURE)
        valid, signed_data, signing_identity = validate_rsg(rsg, message=rsm_contents["message"], required_signer=identity)
        identity_str = RNS.prettyhexrep(identity) if type(identity) == bytes else f"{identity}"
        signer_description = f"\nThe message was NOT signed by {identity_str or signing_identity}" if identity else ""
        if not valid: print(f"Invalid signature in {signature_path}{signer_description}"); exit(R_INVALID_SIGNATURE)
        else:
            if args.meta:
                print("RSM Metadata\n============\n")
                def recurse(entry, key, level=1):
                    try:
                        indent = "  "*level
                        if type(entry) == dict:
                            print(f"d{indent}{key}:")
                            for key in entry: recurse(entry[key], key, level=level+1)
                        else:
                            maxwidth = 64
                            etype = "u"
                            if   type(entry) == str:   etype = "s"
                            elif type(entry) == bytes: etype = "b"
                            elif type(entry) == list:  etype = "l"
                            elif type(entry) == dict:  etype = "d"
                            elif type(entry) == int:   etype = "i"
                            elif type(entry) == float: etype = "f"
                            elif entry == None:        etype = "N"
                            if key == "note" and entry == None: return # TODO: Remove this check in 1.2.9
                            if type(entry) == bytes: entry = RNS.hexrep(entry, delimit=False)
                            leadin = f"{etype}{indent}{key}="; leadln = len(leadin)
                            entry = f"{entry}"; chunk = entry[:maxwidth]; entry = entry[maxwidth:]
                            print(f"{leadin}{chunk}")
                            while len(entry): chunk = entry[:maxwidth]; entry = entry[maxwidth:]; print(f" "*leadln+chunk)
                    except: print(f"E{indent}{key}=<Decode Error>")

                meta = signed_data["meta"]
                for key in meta: entry = meta[key]; recurse(entry, key)
                print("\nValidation\n==========")

            c = ":" if not args.meta else ""
            f = " following" if not args.meta else ""
            print(f"\nSignature is valid, the{f} message was signed by {signing_identity}{c}\n")
            if args.meta: print("Message\n=======\n")
            print(signed_data["message"].decode("utf-8"))

            return exit(R_OK) if not __recursive else R_OK

    except Exception as e: print(f"Error while validating {signature_path}: {e}"); exit(R_UNKNOWN_ERROR)

def sign(args, identity, __recursive=False):
    if type(args.sign) == list:
        paths  = args.sign.copy()
        signed = 0
        for path in paths:
            args.sign = path
            code = sign(args, identity, __recursive=True)
            if code != 0: print(f"Sequence error on recursive signature creation"); exit(R_SEQUENCE_ERROR)
            else:         signed += 1

        if len(paths) != signed: print(f"Sequence error on recursive signature creation"); exit(R_SEQUENCE_ERROR)
        else:                    exit(R_OK)

    sig_ext          = f".{SIG_EXT}"
    sign_path        = os.path.expanduser(args.sign)
    rsg_path         = f"{sign_path}{sig_ext}"
    file_exists      = os.path.isfile(sign_path)
    signature_exists = os.path.isfile(rsg_path)

    if   args.base32:  output = "base32"
    elif args.base64:  output = "base64"
    elif args.base256: output = "base256"
    elif args.hex:     output = "hex"
    else:              output = "bin"

    if not identity.get_private_key(): print(f"Cannot sign \"{sign_path}\", the identity does not hold a private key"); exit(R_NO_PRVKEY)
    if not file_exists: print(f"The file \"{sign_path}\" does not exist"); exit(R_NO_FILE)
    if output == "bin" and signature_exists and not args.force:
        print(f"The signature file \"{rsg_path}\" already exists, not overwriting"); exit(R_FILE_EXISTS)

    try:
        if args.raw:
            with open(sign_path, "rb") as fh: data = fh.read()
            with open(rsg_path, "wb") as fh: fh.write(identity.sign(data))

        else:
            with open(sign_path, "rb") as in_file: rsg = create_rsg(identity, in_file, output=output)
            if not rsg: print(f"No signature created, not writing"); exit(R_UNKNOWN_ERROR)

            if output == "bin":
                with open(rsg_path, "wb") as out_file: out_file.write(rsg)

            elif output in ["base32", "base64", "base256", "hex"]: print(f"\n{wrap_rsg(rsg)}\n")
            else: print("No valid output format specified"); exit(R_INVALID_ARGS)

        print(f"Signed file {sign_path} with {identity}"); return exit(R_OK) if not __recursive else R_OK

    except Exception as e: print(f"Could not sign {sign_path}: {e}"); exit(R_UNKNOWN_ERROR)

def sign_message(args, identity):
    message = args.sign_message
    meta = None

    if   args.base32:  output = "base32"
    elif args.base64:  output = "base64"
    elif args.base256: output = "base256"
    elif args.hex:     output = "hex"
    else:              output = "bin"

    if output == "bin" and not args.write: print("No write path specified"); exit(R_INVALID_ARGS)
    if not identity: print(f"Cannot sign, no working identity available"); exit(R_NO_IDENTITY)
    if not identity.get_private_key(): print(f"Cannot sign, the identity does not hold a private key"); exit(R_NO_PRVKEY)

    if args.read:
        if message != NO_MESSAGE: print("Both an input file and command-line provided message was specified, aborting"); exit(R_INVALID_ARGS)
        sign_path = os.path.expanduser(args.read)
        if not os.path.isfile(sign_path): print(f"The file {sign_path} does not exist"); exit(R_NO_FILE)
        with open(sign_path, "r", encoding="utf-8") as fh: message = fh.read()

    if message == NO_MESSAGE: message = get_editor_content()
    if not message: print("No message specified"); exit(R_INVALID_ARGS)

    if args.embed_meta:
        meta_path = os.path.expanduser(args.embed_meta)
        meta_spec_path = meta_path+".spec" if not args.meta_spec else args.meta_spec
        if not os.path.isfile(meta_path): print(f"Metadata file {meta_path} does not exist"); exit(R_NO_FILE)
        if not os.path.isfile(meta_spec_path): meta_spec_path = None
        spec_info = f" using spec from {meta_spec_path}" if meta_spec_path else ""
        print(f"Embedding metadata from {meta_path}{spec_info}")

        try: meta = rsg_meta_from_file(meta_path, spec_path=meta_spec_path)
        except Exception as e: print(f"Could not load metadata from {meta_path}: {e}"); exit(R_UNKNOWN_ERROR)

    try:
        rsg = create_rsg(identity, message, embed=True, meta=meta, output=output)
        if not rsg: print(f"No signature created, not writing"); exit(R_UNKNOWN_ERROR)

        if output == "bin":
            sig_ext          = f".{MSG_EXT}"
            rsg_path         = os.path.expanduser(args.write)
            rsg_path         = f"{rsg_path}{sig_ext}" if not rsg_path.endswith(sig_ext) else rsg_path
            signature_exists = os.path.isfile(rsg_path)
            if signature_exists and not args.force: print(f"The signature file \"{rsg_path}\" already exists, not overwriting"); exit(R_FILE_EXISTS)
            with open(rsg_path, "wb") as out_file: out_file.write(rsg)
            print(f"Message signed with {identity} saved to {rsg_path}"); exit(R_OK)

        elif output in ["base32", "base64", "base256", "hex"]: print(f"\n{wrap_rsg(rsg)}\n")
        else: print("No valid output format specified"); exit(R_INVALID_ARGS)

        print(f"Message signed with {identity}"); exit(R_OK)

    except Exception as e: print(f"Could not sign message: {e}"); exit(R_UNKNOWN_ERROR)


######################################
# Encryption & Decryption Operations #
######################################

def encrypt(args, identity, __recursive=False):
    if type(args.encrypt) == list:
        paths     = args.encrypt.copy()
        encrypted = 0
        for path in paths:
            args.encrypt = path
            code = encrypt(args, identity, __recursive=True)
            if code != 0: print(f"Sequence error on recursive file encryption"); exit(R_SEQUENCE_ERROR)
            else:         encrypted += 1

        if len(paths) != encrypted: print(f"Sequence error on recursive file encryption"); exit(R_SEQUENCE_ERROR)
        else:                       exit(R_OK)

    enc_ext      = f".{ENCRYPT_EXT}"
    encrypt_path = os.path.expanduser(args.encrypt)
    rfe_path     = args.write if args.write else f"{encrypt_path}{enc_ext}"
    file_exists  = os.path.isfile(encrypt_path)
    rfe_exists   = os.path.isfile(rfe_path)

    if not identity: print(f"Cannot encrypt \"{encrypt_path}\", no identity specified"); exit(R_NO_IDENTITY)
    if not identity.get_public_key(): print(f"Cannot encrypt \"{encrypt_path}\", the identity does not hold a public key"); exit(R_NO_PUBKEY)
    if not file_exists: print(f"The file \"{encrypt_path}\" does not exist"); exit(R_NO_FILE)

    if rfe_exists and not args.force:
        print(f"The encryption output file \"{rfe_path}\" already exists, not overwriting"); exit(R_FILE_EXISTS)

    try:
        with open(encrypt_path, "rb") as input_fh:
            try:
                with open(rfe_path, "wb") as output_fh:
                    wrote = 0
                    data_remaining = True
                    while data_remaining:
                        chunk = input_fh.read(ENC_CHUNK)
                        if chunk: wrote += output_fh.write(identity.encrypt(chunk))
                        else: data_remaining = False
                        print(f"\rWrote {RNS.prettysize(wrote)} to {rfe_path}   ", end="")

            except Exception as e: print(f"\nError writing encrypted output to {rfe_path}: {e}"); exit(R_WRITE_ERROR)
    except Exception as e: print(f"\nError reading {encrypt_path} for encryption: {e}"); exit(R_WRITE_ERROR)

    print(f"\nFile {encrypt_path} encrypted for {identity} to {rfe_path}"); return exit(R_OK) if not __recursive else R_OK

def decrypt(args, identity, __recursive=False):
    if type(args.decrypt) == list:
        paths     = args.decrypt.copy()
        decrypted = 0
        for path in paths:
            args.decrypt = path
            code = decrypt(args, identity, __recursive=True)
            if code != 0: print(f"Sequence error on recursive file decryption"); exit(R_SEQUENCE_ERROR)
            else:         decrypted += 1

        if len(paths) != decrypted: print(f"Sequence error on recursive file decryption"); exit(R_SEQUENCE_ERROR)
        else:                       exit(R_OK)

    enc_ext      = f".{ENCRYPT_EXT}"
    rfe_path     = os.path.expanduser(args.decrypt)
    if not rfe_path.endswith(enc_ext): print(f"The file {rfe_path} does not appear to be a Reticulum encrypted file"); exit(R_INVALID_FILE)

    decrypt_path = os.path.expanduser(args.write) if args.write else f"{rfe_path[:-len(enc_ext)]}"
    if not decrypt_path: print(f"Invalid output filename"); exit(R_INVALID_FILE)

    rfe_exists   = os.path.isfile(rfe_path)
    file_exists  = os.path.isfile(decrypt_path)

    if not identity: print(f"Cannot decrypt \"{rfe_path}\", no identity specified"); exit(R_NO_IDENTITY)
    if not identity.get_private_key(): print(f"Cannot decrypt \"{rfe_path}\", the identity does not hold a private key"); exit(R_NO_PRVKEY)
    if not rfe_exists: print(f"The file \"{rfe_path}\" does not exist"); exit(R_NO_FILE)

    if file_exists and not args.force:
        print(f"The decryption output file \"{decrypt_path}\" already exists, not overwriting"); exit(R_FILE_EXISTS)

    try:
        with open(rfe_path, "rb") as input_fh:
            try:
                with open(decrypt_path, "wb") as output_fh:
                    data_remaining = True
                    wrote = 0
                    while data_remaining:
                        chunk = input_fh.read(DEC_CHUNK)
                        if chunk:
                            decrypted = identity.decrypt(chunk)
                            if not decrypted: print(f"The provided identity could not decrypt the file"); exit(R_DECRYPT_FAILED)
                            else:             wrote += output_fh.write(decrypted)
                            print(f"\rWrote {RNS.prettysize(wrote)} to {decrypt_path}   ", end="")
                        
                        else: data_remaining = False

            except Exception as e: print(f"\nError writing decrypted output to {decrypt_path}: {e}"); exit(R_WRITE_ERROR)
    except Exception as e: print(f"\nError reading {rfe_path} for decryption: {e}"); exit(R_WRITE_ERROR)

    print(f"\nFile {rfe_path} decrypted to {decrypt_path}"); return exit(R_OK) if not __recursive else R_OK


################
#  File Output #
################

def write_identity(args, identity):
    try:
        wp = os.path.expanduser(args.write)
        args.write = False
        if identity.get_private_key() and args.export_prv:
            if not os.path.isfile(wp) or args.force:
                identity.to_file(wp)
                print("Wrote private identity to "+str(wp))
            else: print("File "+str(wp)+" already exists, not overwriting"); exit(R_FILE_EXISTS)
        
        elif identity.get_public_key():
            if not wp.lower().endswith(f".{PUB_EXT}"): wp += f".{PUB_EXT}"
            if not os.path.isfile(wp) or args.force:
                identity.pub_to_file(wp)
                print("Wrote public identity to "+str(wp))
            else: print("File "+str(wp)+" already exists, not overwriting"); exit(R_FILE_EXISTS)

        else: print("Identity holds neither a public nor private key"); exit(R_NO_KEYS)
    except Exception as e: print("Error while writing imported identity to file: "+str(e)); exit(R_WRITE_ERROR)


###################
# Terminal Output #
###################

def print_identity_information(args, identity):
    print("Identity Hash : "+RNS.prettyhexrep(identity.hash))
    if   args.base64: print("Public Key    : "+base64.urlsafe_b64encode(identity.get_public_key()).decode("utf-8"))
    elif args.base32: print("Public Key    : "+base64.b32encode(identity.get_public_key()).decode("utf-8"))
    else:             print("Public Key    : "+RNS.hexrep(identity.get_public_key(), delimit=False))
    
    if identity.prv:
        if args.print_private:
            if   args.base64: print("Private Key   : "+base64.urlsafe_b64encode(identity.get_private_key()).decode("utf-8"))
            elif args.base32: print("Private Key   : "+base64.b32encode(identity.get_private_key()).decode("utf-8"))
            else:             print("Private Key   : "+RNS.hexrep(identity.get_private_key(), delimit=False))
        else:                 print("Private Key   : Hidden")

def print_hash_information(args, identity):
    try:
        hashlen = RNS.Reticulum.TRUNCATED_HASHLENGTH//8*2
        if not type(identity) in [RNS.Identity, str]: print("Invalid identity"); exit(R_INVALID_IDENTITY)
        if type(identity) == str and len(identity) != hashlen: print("Invalid identity hash length"); exit(R_INVALID_IDENTITY)

        aspects = args.hash.split(".")
        if not len(aspects) > 0: print("Invalid destination aspects specified"); exit(R_INVALID_ASPECTS)
        else:
            app_name = aspects[0]; aspects = aspects[1:]
            if type(identity) == RNS.Identity and not identity.get_public_key(): print("Identity does not hold a public key"); exit(R_NO_PUBKEY)
            else:
                if type(identity) == RNS.Identity:
                    identity_hash = identity.hash
                    destination = RNS.Destination(identity, RNS.Destination.OUT, RNS.Destination.SINGLE, app_name, *aspects)
                
                elif type(identity) == str:
                    destination = None
                    try: identity_hash = bytes.fromhex(identity)
                    except Exception as e: print(f"Invalid identity: {e}"); exit(R_INVALID_IDENTITY)

                else: print("Invalid identity"); exit(R_INVALID_IDENTITY)

                destination_hash = RNS.Destination.hash_from_name_and_identity(args.hash, identity_hash)
                print(f"The {args.hash} destination for this Identity is {RNS.prettyhexrep(destination_hash)}")
                if destination: print("The full destination specifier is "+str(destination))
    
    except Exception as e: print(f"An error ocurred while attempting to get hash information: {e}"); exit(R_UNKNOWN_ERROR)

def export_pub_identity(args, identity):
    k = identity.get_public_key()
    if not k: print("Identity doesn't hold a public key, cannot export"); exit(R_NO_PUBKEY)
    else:
        if   args.base64: print("Public Identity Keys  : "+base64.urlsafe_b64encode(k).decode("utf-8"))
        elif args.base32: print("Public Identity Keys  : "+base64.b32encode(k).decode("utf-8"))
        else:             print("Public Identity Keys  : "+RNS.hexrep(k, delimit=False))

def export_prv_identity(args, identity):
    k = identity.get_private_key()
    if not k: print("Identity doesn't hold a private key, cannot export"); exit(R_NO_PRVKEY)
    else:
        if   args.base64: print("Private Identity Keys : "+base64.urlsafe_b64encode(k).decode("utf-8"))
        elif args.base32: print("Private Identity Keys : "+base64.b32encode(k).decode("utf-8"))
        else:             print("Private Identity Keys : "+RNS.hexrep(k, delimit=False))


##############################
# Helper & Utility Functions #
##############################

def get_editor_content():
    import subprocess
    from tempfile import NamedTemporaryFile
    template = ""
    editor = os.environ.get("EDITOR", "")
    if not editor:
        for fallback in ["nano", "vim", "vi"]:
            try:
                subprocess.run(["which", fallback], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                editor = fallback
                break
            except subprocess.CalledProcessError: continue

    if not editor: print("Could not launch editor"); exit(R_READ_ERROR);
    try:
        with NamedTemporaryFile(mode="w+", suffix=".tmp", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(template)

        result = subprocess.run([editor, tmp_path])
        if result.returncode != 0: print(f"Editor exited with error code {result.returncode}"); os.unlink(tmp_path); exit(R_READ_ERROR)
        with open(tmp_path, "r") as f: content = f.read()
        os.unlink(tmp_path)
        return content.encode("utf-8")

    except Exception as e: print(f"Could not get content from editor: {e}"); exit(R_READ_ERROR)

def spin(until=None, msg=None, timeout=None):
    i = 0
    syms = "⢄⢂⢁⡁⡈⡐⡠"
    if timeout != None: timeout = time.time()+timeout

    print(msg+"  ", end=" ")
    while (timeout == None or time.time()<timeout) and not until():
        time.sleep(0.1)
        print(("\b\b"+syms[i]+" "), end="")
        sys.stdout.flush()
        i = (i+1)%len(syms)

    print("\r"+" "*len(msg)+"  \r", end="")

    if timeout != None and time.time() > timeout: return False
    else:                                         return True

if __name__ == "__main__":
    main()
