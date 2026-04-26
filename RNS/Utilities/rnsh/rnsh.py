#!/usr/bin/env python3
#
#         Based on the original rnsh program by Aaron Heise (@acehoss)
# https://github.com/acehoss/rnsh - MIT License - Copyright (c) 2023 Aaron Heise
#     This version of rnsh is included in RNS under the Reticulum License
#
# Reticulum License
#
# Copyright (c) 2016-2026 Mark Qvist
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

from __future__ import annotations

import asyncio
import base64

import re
import os
import sys

import RNS
import RNS.Utilities.rnsh.process as process
import RNS.Utilities.rnsh.session as session
import RNS.Utilities.rnsh.args
import RNS.Utilities.rnsh.loop
import RNS.Utilities.rnsh.listener as listener
import RNS.Utilities.rnsh.initiator as initiator
from RNS.Utilities.rnsh.args import parse_arguments

APP_NAME = "rnsh"
loop: asyncio.AbstractEventLoop | None = None

def _sanitize_service_name(service_name:str) -> str: return re.sub(r'\W+', '', service_name)

def prepare_identity(identity_path, service_name: str = None) -> tuple[RNS.Identity]:
    service_name = _sanitize_service_name(service_name or "")
    if identity_path is None:
        identity_path = RNS.Reticulum.identitypath + "/" + APP_NAME + \
                        (f".{service_name}" if service_name and len(service_name) > 0 else "")

    identity = None
    if os.path.isfile(identity_path):
        identity = RNS.Identity.from_file(identity_path)

    if identity is None:
        RNS.log("No valid saved identity found, creating new...", RNS.LOG_INFO)
        identity = RNS.Identity()
        identity.to_file(identity_path)
    
    return identity


def print_identity(configdir, identitypath, service_name, include_destination: bool):
    reticulum = RNS.Reticulum(configdir=configdir, loglevel=RNS.LOG_INFO)
    if service_name and len(service_name) > 0:
        print(f"Using service name \"{service_name}\"")
    identity = prepare_identity(identitypath, service_name)
    destination = RNS.Destination(identity, RNS.Destination.IN, RNS.Destination.SINGLE, APP_NAME)
    print("Identity     : " + str(identity))
    if include_destination:
        print("Listening on : " + RNS.prettyhexrep(destination.hash))

    exit(0)

verbose_set = False

def ensure_config_directory():
    if os.path.isdir(os.path.expanduser("~/.config/rnsh")): return os.path.expanduser("~/.config/rnsh")
    elif os.path.isdir(os.path.expanduser("~/.rnsh")): return os.path.expanduser("~/.rnsh")
    else:
        try:
            os.makedirs(os.path.expanduser("~/.rnsh"))
            return os.path.expanduser("~/.rnsh")

        except Exception as e:
            RNS.log(f"Could not get or create rnsh configuration directory, aborting", RNS.LOG_CRITICAL)
            os._exit(1)


async def _rnsh_cli_main():
    global verbose_set
    args, parser = parse_arguments()
    verbose_set = args.verbose > 0

    configdir = ensure_config_directory()

    if args.print_identity:
        print_identity(args.config, args.identity, args.service, args.listen)
        return 0

    if args.listen:
        allowed_file = None
        dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH//8)*2
        if os.path.isfile(os.path.expanduser("~/.config/rnsh/allowed_identities")):
            allowed_file = os.path.expanduser("~/.config/rnsh/allowed_identities")
        elif os.path.isfile(os.path.expanduser("~/.rnsh/allowed_identities")):
            allowed_file = os.path.expanduser("~/.rnsh/allowed_identities")

        await listener.listen(configdir=configdir,
                              rnsconfigdir=args.config,
                              command=args.command,
                              identitypath=args.identity,
                              service_name=args.service,
                              verbosity=args.verbose,
                              quietness=args.quiet,
                              allowed=args.allowed or [],
                              allowed_file=allowed_file,
                              disable_auth=args.no_auth,
                              announce_period=args.announce,
                              no_remote_command=args.no_remote_command,
                              remote_cmd_as_args=args.remote_command_as_args)
        return 0

    if args.destination is not None:
        return_code = await initiator.initiate(configdir=configdir,
                                               rnsconfigdir=args.config,
                                               identitypath=args.identity,
                                               verbosity=args.verbose,
                                               quietness=args.quiet,
                                               noid=args.no_id,
                                               destination=args.destination,
                                               timeout=args.timeout,
                                               command=args.command
        )
        return return_code if args.mirror else 0
    else:
        print("")
        parser.print_help()
        print("")
        return 1


def main():
    global verbose_set
    return_code = 1
    exc = None
    try: return_code = asyncio.run(_rnsh_cli_main())
    except SystemExit: pass
    except KeyboardInterrupt: pass
    except Exception as ex:
        print(f"Unhandled exception: {ex}")
        exc = ex
    
    process.tty_unset_reader_callbacks(0)
    if verbose_set and exc: raise exc
    sys.exit(return_code if return_code is not None else 255)


if __name__ == "__main__": main()
