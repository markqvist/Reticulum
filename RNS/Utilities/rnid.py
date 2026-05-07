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
from RNS.Cryptography.Hashes import sha256
from RNS.Cryptography.Hashes import file_sha256

APP_NAME = "rns"
DEFAULT_ASPECTS = f"{APP_NAME}.id"

PRV_EXT      = "rid"
PUB_EXT      = "pub"
SIG_EXT      = "rsg"
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
R_READ_ERROR        = 252
R_WRITE_ERROR       = 253
R_UNKNOWN_ERROR     = 254
R_INTERRUPTED       = 255

reticulum = None

def validate_args(args):
    ops = 0;
    for o in [args.encrypt, args.decrypt, args.validate, args.sign]:
        if o: ops += 1
    if ops > 1: print("This utility currently only supports one of the encrypt, decrypt, sign or verify operations per invocation"); exit(1)

    g = 0;
    for a in [args.import_pub, args.import_prv, args.identity, args.generate]:
        if a: g += 1
    if g > 1: print("The -i, -g, -m and -M args are mutually exclusive"); exit(1)

    g = 0;
    for a in [args.base64, args.base32]:
        if a: g += 1
    if g > 1: print("The -b and -B args are mutually exclusive"); exit(1)

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
        parser.add_argument("-d", "--decrypt", metavar="file", action="store", default=None, help="decrypt file")
        parser.add_argument("-e", "--encrypt", metavar="file", action="store", default=None, help="encrypt file")
        parser.add_argument("-V", "--validate", metavar="path", action="store", default=None, help="validate signature")
        parser.add_argument("-s", "--sign", metavar="path", action="store", default=None, help="sign file")
        parser.add_argument("--raw", action="store_true", default=False, help="sign raw input data instead of hashing first")

        # I/O Control
        parser.add_argument("-w", "--write", metavar="file", action="store", default=None, help="output file path", type=str)
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
        parser.add_argument("-b", "--base64", action="store_true", default=False, help="Use base64-encoded input and output")
        parser.add_argument("-B", "--base32", action="store_true", default=False, help="Use base32-encoded input and output")

        parser.add_argument("--version", action="version", version="rnid {version}".format(version=__version__))
        
        args = parser.parse_args()
        validate_args(args)

        op_requires_identity = (args.sign or args.encrypt or args.decrypt or args.announce or args.write
                                or args.print_identity or args.print_identity or args.export_pub or args.export_prv)

        identity = get_operating_identity(args, allow_none=not op_requires_identity, no_cache=args.no_cache); op = False
        if not identity and op_requires_identity: print("Could not get working identity"); exit(R_NO_IDENTITY)
        if args.print_identity: print_identity_information(args, identity); op = True
        if args.export_pub: export_pub_identity(args, identity); op = True
        if args.export_prv: export_prv_identity(args, identity); op = True
        if args.hash: print_hash_information(args, identity or args.identity); op = True
        if args.announce: announce(args, identity); op = True
        if args.validate: validate(args, identity); op = True
        if args.sign: sign(args, identity); op = True
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


###################################
# Signing & Validation Operations #
###################################

def get_rsg_data(rsg):
    rsg_data = None
    if   type(rsg) == bytes:             rsg_data = rsg
    elif type(rsg) == io.BufferedReader: rsg_data = rsg.read()
    elif type(rsg) == str:
        try:                             rsg_data = base64.urlsafe_b64decode(rsg)
        except:                          pass
        try:                             rsg_data = base64.b32decode(rsg)
        except:                          pass

    return rsg_data

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
    if not type(required_signer) in [RNS.Identity, type(None)]: raise TypeError(f"Invalid required signer type {type(required_signer)}")

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
            if not "note" in signed_data["meta"]:                          return False, None, None

            try:
                if required_signer:
                    signing_identity = required_signer
                
                else:
                    signing_identity = RNS.Identity(create_keys=False)
                    signing_identity.load_public_key(signed_data["meta"]["pubkey"])
            
            except: return False, None, None
    
            if not signing_identity:                                       return False, None, None
            if signed_data["hash"] != rsg_hash:                            return False, None, signing_identity
            else:
                if not signing_identity.validate(signature, envelope):     return False, signed_data, signing_identity
                else:                                                      return True,  signed_data, signing_identity

            return False, signed_data, signing_identity

def create_rsg(signer_identity, message, note=None, meta=None, output="bin"):
    if not output in ["bin", "hex", "base32", "base64"]:   raise TypeError(f"Invalid output format for rsg creation")
    if not type(signer_identity) == RNS.Identity:          raise TypeError(f"{signer_identity} is not a Reticulum Identity")
    if not signer_identity.get_private_key():              raise ValueError(f"{signer_identity} does not hold a private key")

    signed_data = { "hashtype": "sha256", "hash": get_rsg_hash(message),
                    "meta": { "signer": signer_identity.hash,
                              "pubkey": signer_identity.get_public_key(),
                              "note"  : note } }

    if meta and type(meta) == dict:
        for key in meta:
            if not key in signed_data["meta"]: signed_data["meta"]["key"] = meta["key"]

    envelope  = mp.packb(signed_data)
    signature = signer_identity.sign(envelope)

    return signature+envelope

def validate(args, identity):
    sig_ext                            = f".{SIG_EXT}"
    validate_path                      = os.path.expanduser(args.validate)
    path_is_sigfile                    = validate_path.lower().endswith(sig_ext)
    if path_is_sigfile: signature_path = validate_path; file_path = validate_path[:-len(sig_ext)]
    else:               signature_path = f"{validate_path}{sig_ext}"; file_path = validate_path
    signature_exists                   = os.path.isfile(signature_path)
    file_exists                        = os.path.isfile(file_path)

    if not file_exists:      print(f"The validation target \"{file_path}\" does not exist"); exit(R_NO_FILE)
    if not signature_exists: print(f"No signature file exists for \"{file_path}\""); exit(R_NO_FILE)

    try:
        with open(signature_path, "rb") as fh: is_legacy_format = rsg_is_legacy_format(fh)
    except Exception as e: print(f"Could not detect rsg format: {e}"); exit(R_UNKNOWN_ERROR)

    if not is_legacy_format:
        try:
            with open(signature_path, "rb") as fh: rsg = fh.read()
        except Exception as e: print(f"Could not read rsg: {e}"); exit(R_READ_ERROR)

        try:
            with open(file_path, "rb") as fh:
                try:
                    valid, signed_data, signing_identity = validate_rsg(rsg, message=fh, required_signer=identity)
                    signer_description = f"\nThis file was NOT signed by {identity or signing_identity}"
                    if not valid: print(f"Invalid signature {signature_path} for file {file_path}{signer_description}"); exit(R_INVALID_SIGNATURE)
                    else:         print(f"Signature is valid, the file {file_path} was signed by {signing_identity}"); exit(R_OK)

                except Exception as e: print(f"Error while validating {signature_path}: {e}"); exit(R_UNKNOWN_ERROR)

        except Exception as e: print(f"Could not read {file_path}: {e}"); exit(R_READ_ERROR)

    else:
        if identity == None: print(f"Cannot validate legacy rsg signatures without an explicit required identity"); exit(R_NO_IDENTITY)
        try:
            with open(signature_path, "rb") as fh: signature = fh.read()
        except Exception as e: print(f"Could not read signature: {e}"); exit(R_READ_ERROR)

        try:
            with open(file_path, "rb") as fh: valid = identity.validate(signature, fh.read())
            if not valid: print(f"Invalid signature {signature_path} for file {file_path}\nThis file was NOT signed by {identity}"); exit(R_INVALID_SIGNATURE)
            else:         print(f"Signature is valid, the file {file_path} was signed by {identity}"); exit(R_OK)
        
        except Exception as e: print(f"Could not validate signature: {e}"); exit(R_READ_ERROR)

def sign(args, identity):
    sig_ext          = f".{SIG_EXT}"
    sign_path        = os.path.expanduser(args.sign)
    rsg_path         = f"{sign_path}{sig_ext}"
    file_exists      = os.path.isfile(sign_path)
    signature_exists = os.path.isfile(rsg_path)

    if not identity.get_private_key(): print(f"Cannot sign \"{sign_path}\", the identity does not hold a private key"); exit(R_NO_PRVKEY)
    if not file_exists: print(f"The file \"{sign_path}\" does not exist"); exit(R_NO_FILE)
    if signature_exists and not args.force:
        print(f"The signature file \"{rsg_path}\" already exists, not overwriting"); exit(R_FILE_EXISTS)

    try:
        if args.raw:
            with open(sign_path, "rb") as fh: data = fh.read()
            with open(rsg_path, "wb") as fh: fh.write(identity.sign(data))

        else:
            with open(sign_path, "rb") as in_file:
                rsg = create_rsg(identity, in_file)
                if not rsg: print(f"No signature created, not writing"); exit(R_UNKNOWN_ERROR)
                with open(rsg_path, "wb") as out_file: out_file.write(rsg)

        print(f"Signed file {sign_path} with {identity}"); exit(R_OK)

    except Exception as e: print(f"Could not sign {sign_path}: {e}"); exit(R_UNKNOWN_ERROR)


######################################
# Encryption & Decryption Operations #
######################################

def encrypt(args, identity):
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

    print(f"\nFile {encrypt_path} encrypted for {identity} to {rfe_path}"); exit(R_OK)

def decrypt(args, identity):
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

    print(f"\nFile {rfe_path} decrypted to {decrypt_path}"); exit(R_OK)


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
