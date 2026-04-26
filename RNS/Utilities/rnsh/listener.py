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
import os
import queue
import shlex
import signal
import sys
import termios
import threading
import time
import tty
from typing import Callable, TypeVar
import RNS
import RNS.Utilities.rnsh.exception as exception
import RNS.Utilities.rnsh.process as process
import RNS.Utilities.rnsh.retry as retry
import RNS.Utilities.rnsh.session as session
import re
import contextlib

import pwd
import RNS.Utilities.rnsh.protocol as protocol
import RNS.Utilities.rnsh.helpers as helpers
import RNS.Utilities.rnsh.rnsh as rnsh


_identity = None
_reticulum = None
_allow_all = False
_allowed_file = None
_allowed_identity_hashes = []
_allowed_file_identity_hashes = []
_cmd: [str] | None = None
DATA_AVAIL_MSG = "data available"
_finished: asyncio.Event = None
_retry_timer: retry.RetryThread | None = None
_destination: RNS.Destination | None = None
_loop: asyncio.AbstractEventLoop | None = None
_no_remote_command = True
_remote_cmd_as_args = False


async def _check_finished(timeout: float = 0):
    return await process.event_wait(_finished, timeout=timeout)


def _sigint_handler(sig, loop):
    global _finished
    RNS.log(f"Signal: {signal.Signals(sig).name}", RNS.LOG_DEBUG)
    if _finished is not None: _finished.set()
    else: raise KeyboardInterrupt()

def _reload_allowed_file():
    global _allowed_file, _allowed_file_identity_hashes
    if _allowed_file != None:
        try:
            with open(_allowed_file, "r") as file:
                dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH // 8) * 2
                added = 0
                line = 0
                _allowed_file_identity_hashes = []
                for allow in file.read().replace("\r", "").split("\n"):
                    line += 1
                    if len(allow) == dest_len:
                        try:
                            destination_hash = bytes.fromhex(allow)
                            _allowed_file_identity_hashes.append(destination_hash)
                            added += 1
                        except Exception:
                            RNS.log(f"Discarded invalid Identity hash in {_allowed_file} at line {line}", RNS.LOG_DEBUG)

                ms = "y" if added == 1 else "ies"
                RNS.log(f"Loaded {added} allowed identit{ms} from "+str(_allowed_file), RNS.LOG_DEBUG)
        
        except Exception as e: RNS.log(f"Error while reloading allowed indetities file: {e}", RNS.LOG_ERROR)

def compute_target_rns_loglevel(verbosity: int, quietness: int, base_level: int = RNS.LOG_INFO) -> int:
    try:
        target = int(base_level) + int(verbosity) - int(quietness)
        if target < RNS.LOG_CRITICAL: target = RNS.LOG_CRITICAL
        if target > RNS.LOG_DEBUG:    target = RNS.LOG_DEBUG
        return target
    
    except Exception: return base_level

async def listen(configdir, rnsconfigdir, command, identitypath=None, service_name=None, verbosity=0, quietness=0, allowed=None,
                 allowed_file=None, disable_auth=None, announce_period=900, no_remote_command=True, remote_cmd_as_args=False,
                 loop: asyncio.AbstractEventLoop = None):
    global _identity, _allow_all, _allowed_identity_hashes, _allowed_file, _allowed_file_identity_hashes
    global _reticulum, _cmd, _destination, _no_remote_command, _remote_cmd_as_args, _finished

    if not loop: loop = asyncio.get_running_loop()
    if service_name is None or len(service_name) == 0:
        service_name = "default"

    RNS.log(f"Using service name {service_name}", RNS.LOG_INFO)

    # More -v should increase verbosity (higher RNS.loglevel); -q should decrease it
    targetloglevel = compute_target_rns_loglevel(verbosity, quietness, RNS.LOG_INFO)
    _reticulum = RNS.Reticulum(configdir=rnsconfigdir, loglevel=targetloglevel)
    _identity = rnsh.prepare_identity(identitypath, service_name)
    _destination = RNS.Destination(_identity, RNS.Destination.IN, RNS.Destination.SINGLE, rnsh.APP_NAME)
    
    RNS.log(f"rnsh listening for commands on {RNS.prettyhexrep(_destination.hash)}", RNS.LOG_NOTICE)
    
    _cmd = command
    if _cmd is None or len(_cmd) == 0:
        shell = None
        try: shell = pwd.getpwuid(os.getuid()).pw_shell
        except Exception as e: RNS.log(f"Error looking up shell: {e}", RNS.LOG_ERROR)
        RNS.log(f"Using {shell} for default command.", RNS.LOG_INFO)

        # Ensure a sane shell default. Fall back to /bin/sh if lookup fails.
        if not shell or len(shell) == 0: shell = "/bin/sh"
        _cmd = [shell]
    
    else: RNS.log(f"Using command {shlex.join(_cmd)}", RNS.LOG_INFO)

    _no_remote_command = no_remote_command
    session.ListenerSession.allow_remote_command = not no_remote_command
    _remote_cmd_as_args = remote_cmd_as_args
    if (_cmd is None or len(_cmd) == 0 or _cmd[0] is None or len(_cmd[0]) == 0) \
            and (_no_remote_command or _remote_cmd_as_args):
        raise Exception(f"Unable to look up shell for {os.getlogin}, cannot proceed with -A or -C and no <program>.")

    session.ListenerSession.default_command = _cmd
    session.ListenerSession.remote_cmd_as_args = _remote_cmd_as_args

    if disable_auth:
        _allow_all = True
        session.ListenerSession.allow_all = True
    else:
        if allowed_file is not None:
            _allowed_file = allowed_file
            _reload_allowed_file()

        if allowed is not None:
            for a in allowed:
                try:
                    dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH // 8) * 2
                    if len(a) != dest_len:
                        raise ValueError(
                            "Allowed destination length is invalid, must be {hex} hexadecimal " +
                            "characters ({byte} bytes).".format(
                                hex=dest_len, byte=dest_len // 2))
                    try:
                        destination_hash = bytes.fromhex(a)
                        _allowed_identity_hashes.append(destination_hash)
                        session.ListenerSession.allowed_identity_hashes.append(destination_hash)
                    except Exception:
                        raise ValueError("Invalid destination entered. Check your input.")
                
                except Exception as e:
                    RNS.log(f"Unhandled error: {e}", RNS.LOG_ERROR)
                    RNS.trace_exception(e)
                    exit(1)

    if (len(_allowed_identity_hashes) < 1 and len(_allowed_file_identity_hashes) < 1) and not disable_auth:
        RNS.log("Warning: No allowed identities configured, rnsh will not accept any connections!", RNS.LOG_WARNING)

    def link_established(lnk: RNS.Link):
        _reload_allowed_file()
        session.ListenerSession.allowed_file_identity_hashes = _allowed_file_identity_hashes
        session.ListenerSession(session.RNSOutlet.get_outlet(lnk), lnk.get_channel(), loop)
    _destination.set_link_established_callback(link_established)

    _finished = asyncio.Event()
    signal.signal(signal.SIGINT, _sigint_handler)

    if announce_period is not None: _destination.announce()

    last_announce = time.time()
    sleeper = helpers.SleepRate(0.01)

    try:
        while not await _check_finished():
            if announce_period and 0 < announce_period < time.time() - last_announce:
                last_announce = time.time()
                _destination.announce()
            if len(session.ListenerSession.sessions) > 0:
                # no sleep if there's work to do
                if not await session.ListenerSession.pump_all():
                    await sleeper.sleep_async()
            else:
                await asyncio.sleep(0.25)
    finally:
        RNS.log("Shutting down", RNS.LOG_NOTICE)
        await session.ListenerSession.terminate_all("Shutting down")
        await asyncio.sleep(1)
        links_still_active = list(filter(lambda l: l.status != RNS.Link.CLOSED, _destination.links))
        for link in links_still_active:
            if link.status not in [RNS.Link.CLOSED]:
                link.teardown()
                await asyncio.sleep(0.01)