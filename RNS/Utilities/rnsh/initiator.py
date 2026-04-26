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
import enum
import functools
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
import bz2
import RNS.Utilities.rnsh.protocol as protocol
import RNS.Utilities.rnsh.helpers as helpers
import RNS.Utilities.rnsh.rnsh as rnsh

_identity = None
_reticulum = None
_cmd: [str] | None = None
DATA_AVAIL_MSG = "data available"
_finished: asyncio.Event = None
_retry_timer: retry.RetryThread | None = None
_destination: RNS.Destination | None = None
_loop: asyncio.AbstractEventLoop | None = None


async def _check_finished(timeout: float = 0):
    return _finished is not None and await process.event_wait(_finished, timeout=timeout)

def _sigint_handler(sig, loop):
    global _finished
    RNS.log(f"{signal.Signals(sig).name}", RNS.LOG_DEBUG)
    if _finished is not None: _finished.set()
    else: raise KeyboardInterrupt()

async def _spin_tty(until=None, msg=None, timeout=None):
    i = 0
    syms = "⢄⢂⢁⡁⡈⡐⡠"
    if timeout != None: timeout = time.time()+timeout

    print(msg+"  ", end=" ")
    while (timeout == None or time.time()<timeout) and not until():
        await asyncio.sleep(0.1)
        print(("\b\b"+syms[i]+" "), end="")
        sys.stdout.flush()
        i = (i+1)%len(syms)

    print("\r"+" "*len(msg)+"  \r", end="")

    if timeout != None and time.time() > timeout: return False
    else:                                         return True


async def _spin_pipe(until: callable = None, msg=None, timeout: float | None = None) -> bool:
    if timeout is not None: timeout += time.time()

    while (timeout is None or time.time() < timeout) and not until():
        if await _check_finished(0.1): raise asyncio.CancelledError()
    
    if timeout is not None and time.time() > timeout: return False
    else: return True

async def _spin(until: callable = None, msg=None, timeout: float | None = None, quiet: bool = False) -> bool:
    if not quiet and os.isatty(1): return await _spin_tty(until, msg, timeout)
    else:                          return await _spin_pipe(until, msg, timeout)

_link: RNS.Link | None = None
_remote_exec_grace = 2.0
_pq = queue.Queue()


class InitiatorState(enum.IntEnum):
    IS_INITIAL      = 0
    IS_LINKED     = 1
    IS_WAIT_VERS  = 2
    IS_RUNNING    = 3
    IS_TERMINATE  = 4
    IS_TEARDOWN   = 5

def _client_link_closed(link):
    if _finished: _finished.set()

def _client_message_handler(message: RNS.MessageBase): _pq.put(message)

def compute_target_rns_loglevel(verbosity: int, quietness: int, base_level: int = RNS.LOG_INFO) -> int:
    try:
        target = int(base_level) + int(verbosity) - int(quietness)
        if target < RNS.LOG_CRITICAL: target = RNS.LOG_CRITICAL
        if target > RNS.LOG_DEBUG:    target = RNS.LOG_DEBUG
        return target
    
    except Exception: return base_level


class RemoteExecutionError(Exception):
    def __init__(self, msg): self.msg = msg


async def _initiate_link(configdir, rnsconfigdir, identitypath=None, verbosity=0, quietness=0, noid=False, destination=None,
                         timeout=RNS.Transport.PATH_REQUEST_TIMEOUT):
    global _identity, _reticulum, _link, _destination, _remote_exec_grace

    dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH // 8) * 2
    if len(destination) != dest_len:
        raise RemoteExecutionError(
            "Allowed destination length is invalid, must be {hex} hexadecimal characters ({byte} bytes).".format(
                hex=dest_len, byte=dest_len // 2))
    try:
        destination_hash = bytes.fromhex(destination)
    except Exception as e:
        raise RemoteExecutionError("Invalid destination entered. Check your input.")

    if _reticulum is None:
        targetloglevel = compute_target_rns_loglevel(verbosity, quietness, RNS.LOG_ERROR)
        RNS.logfile = os.path.join(configdir, "logfile")
        _reticulum = RNS.Reticulum(configdir=rnsconfigdir, loglevel=targetloglevel, logdest=RNS.LOG_FILE)

    if _identity is None:
        _identity = rnsh.prepare_identity(identitypath)

    if not RNS.Transport.has_path(destination_hash):
        RNS.Transport.request_path(destination_hash)
        RNS.log(f"Requesting path...", RNS.LOG_INFO)
        if not await _spin(until=lambda: RNS.Transport.has_path(destination_hash), msg="Requesting path...",
                           timeout=timeout, quiet=quietness > 0):
            raise RemoteExecutionError("Path not found")

    if _destination is None:
        listener_identity = RNS.Identity.recall(destination_hash)
        _destination = RNS.Destination(
            listener_identity,
            RNS.Destination.OUT,
            RNS.Destination.SINGLE,
            rnsh.APP_NAME
        )

    if _link is None or _link.status == RNS.Link.PENDING:
        RNS.log("No link", RNS.LOG_DEBUG)
        _link = RNS.Link(_destination)
        _link.did_identify = False

        _link.set_link_closed_callback(_client_link_closed)

    RNS.log(f"Establishing link...", RNS.LOG_VERBOSE)
    if not await _spin(until=lambda: _link.status == RNS.Link.ACTIVE, msg="Establishing link...",
                       timeout=timeout, quiet=quietness > 0):
        raise RemoteExecutionError("Could not establish link with " + RNS.prettyhexrep(destination_hash))

    RNS.log("Have link", RNS.LOG_DEBUG)
    if not noid and not _link.did_identify:
        # Delay a tiny bit to allow listener to fully enter WAIT_IDENT state
        await asyncio.sleep(min(1, _link.rtt * 1.1 + 0.05))
        _link.identify(_identity)
        _link.did_identify = True


async def _handle_error(errmsg: RNS.MessageBase):
    if isinstance(errmsg, protocol.ErrorMessage):
        with contextlib.suppress(Exception):
            if _link and _link.status == RNS.Link.ACTIVE:
                _link.teardown()
        await asyncio.sleep(0.1)
        raise RemoteExecutionError(f"Remote error: {errmsg.msg}")


async def initiate(configdir: str, rnsconfigdir:str, identitypath: str, verbosity: int, quietness: int, noid: bool, destination: str,
                   timeout: float, command: [str] | None = None):
    global _finished, _link
    with process.TTYRestorer(sys.stdin.fileno()) as ttyRestorer:
        loop = asyncio.get_running_loop()
        state = InitiatorState.IS_INITIAL
        data_buffer = bytearray(sys.stdin.buffer.read()) if not os.isatty(sys.stdin.fileno()) else bytearray()
        line_buffer = bytearray()

        await _initiate_link(configdir=configdir,
                             rnsconfigdir=rnsconfigdir,
                             identitypath=identitypath,
                             verbosity=verbosity,
                             quietness=quietness,
                             noid=noid,
                             destination=destination,
                             timeout=timeout)

        if not _link or _link.status not in [RNS.Link.ACTIVE, RNS.Link.PENDING]:
            return 255

        state = InitiatorState.IS_LINKED
        outlet = session.RNSOutlet(_link)
        channel = _link.get_channel()
        protocol.register_message_types(channel)
        channel.add_message_handler(_client_message_handler)

        # Next step after linking and identifying: send version
        # if not await _spin(lambda: messenger.is_outlet_ready(outlet), timeout=5, quiet=quietness > 0):
        #     print("Error bringing up link")
        #     return 253

        channel.send(protocol.VersionInfoMessage())
        try:
            vm = _pq.get(timeout=max(outlet.rtt * 20, 5))
            await _handle_error(vm)
            if not isinstance(vm, protocol.VersionInfoMessage):
                raise Exception("Invalid message received")
            RNS.log(f"Server version info: sw {vm.sw_version} prot {vm.protocol_version}", RNS.LOG_DEBUG)
            state = InitiatorState.IS_RUNNING
        except queue.Empty:
            print("Protocol error")
            return 254

        winch = False
        def sigwinch_handler():
            nonlocal winch
            winch = True

        esc = False
        pre_esc = True
        line_mode = False
        line_flush = False
        blind_write_count = 0
        flush_chars = ["\x01", "\x03", "\x04", "\x05", "\x0c", "\x11", "\x13", "\x15", "\x19", "\t", "\x1A", "\x1B"]
        def handle_escape(b):
            nonlocal line_mode
            if b == "?":
                os.write(1, "\n\r\n\rSupported rnsh escape sequences:".encode("utf-8"))
                os.write(1, "\n\r  ~~  Send the escape character by typing it twice".encode("utf-8"))
                os.write(1, "\n\r  ~.  Terminate session and exit immediately".encode("utf-8"))
                os.write(1, "\n\r  ~L  Toggle line-interactive mode".encode("utf-8"))
                os.write(1, "\n\r  ~?  Display this quick reference\n\r".encode("utf-8"))
                os.write(1, "\n\r(Escape sequences are only recognized immediately after newline)\n\r".encode("utf-8"))
                return None
            elif b == ".":
                _link.teardown()
                return None
            elif b == "L":
                line_mode = not line_mode
                if line_mode:
                    os.write(1, "\n\rLine-interactive mode enabled\n\r".encode("utf-8"))
                else:
                    os.write(1, "\n\rLine-interactive mode disabled\n\r".encode("utf-8"))
                return None

            return b

        stdin_eof = False
        def stdin():
            nonlocal stdin_eof, pre_esc, esc, line_mode
            nonlocal line_flush, blind_write_count
            try:
                in_data = process.tty_read(sys.stdin.fileno())
                if in_data is not None:
                    data = bytearray()
                    for b in bytes(in_data):
                        c = chr(b)
                        if c == "\r":
                            pre_esc = True
                            line_flush = True
                            data.append(b)
                        elif line_mode and c in flush_chars:
                            pre_esc = False
                            line_flush = True
                            data.append(b)
                        elif line_mode and (c == "\b" or c == "\x7f"):
                            pre_esc = False
                            if len(line_buffer)>0:
                                line_buffer.pop(-1)
                                blind_write_count -= 1
                                os.write(1, "\b \b".encode("utf-8"))
                        elif pre_esc == True and c == "~":
                            pre_esc = False
                            esc = True
                        elif esc == True:
                            ret = handle_escape(c)
                            if ret != None:
                                if ret != "~":
                                    data.append(ord("~"))
                                data.append(ord(ret))
                            esc = False
                        else:
                            pre_esc = False
                            data.append(b)

                    if not line_mode:
                        data_buffer.extend(data)
                    else:
                        line_buffer.extend(data)
                        if line_flush:
                            data_buffer.extend(line_buffer)
                            line_buffer.clear()
                            os.write(1, ("\b \b"*blind_write_count).encode("utf-8"))
                            line_flush = False
                            blind_write_count = 0
                        else:
                            os.write(1, data)
                            blind_write_count += len(data)

            except EOFError:
                if os.isatty(0):
                    data_buffer.extend(process.CTRL_D)
                stdin_eof = True
                process.tty_unset_reader_callbacks(sys.stdin.fileno())

        process.tty_add_reader_callback(sys.stdin.fileno(), stdin)

        tcattr = None
        rows, cols, hpix, vpix = (None, None, None, None)
        try:
            tcattr = termios.tcgetattr(0)
            rows, cols, hpix, vpix = process.tty_get_winsize(0)
        except:
            try:
                tcattr = termios.tcgetattr(1)
                rows, cols, hpix, vpix = process.tty_get_winsize(1)
            except:
                try:
                    tcattr = termios.tcgetattr(2)
                    rows, cols, hpix, vpix = process.tty_get_winsize(2)
                except:
                    pass

        await _spin(lambda: channel.is_ready_to_send(), "Waiting for channel...", 1, quietness > 0)
        channel.send(protocol.ExecuteCommandMesssage(cmdline=command,
                                                     pipe_stdin=not os.isatty(0),
                                                     pipe_stdout=not os.isatty(1),
                                                     pipe_stderr=not os.isatty(2),
                                                     tcflags=tcattr,
                                                     term=os.environ.get("TERM", None),
                                                     rows=rows,
                                                     cols=cols,
                                                     hpix=hpix,
                                                     vpix=vpix))

        loop.add_signal_handler(signal.SIGWINCH, sigwinch_handler)
        _finished = asyncio.Event()
        loop.add_signal_handler(signal.SIGINT, functools.partial(_sigint_handler, signal.SIGINT, loop))
        loop.add_signal_handler(signal.SIGTERM, functools.partial(_sigint_handler, signal.SIGTERM, loop))
        mdu = _link.MDU - 16
        sent_eof = False
        last_winch = time.time()
        sleeper = helpers.SleepRate(0.01)
        processed = False
        while not await _check_finished() and state in [InitiatorState.IS_RUNNING]:
            try:
                try:
                    message = _pq.get(timeout=sleeper.next_sleep_time() if not processed else 0.0005)
                    await _handle_error(message)
                    processed = True
                    if isinstance(message, protocol.StreamDataMessage):
                        if message.stream_id == protocol.StreamDataMessage.STREAM_ID_STDOUT:
                            if message.data and len(message.data) > 0:
                                ttyRestorer.raw()
                                RNS.log(f"stdout: {message.data}", RNS.LOG_DEBUG)
                                os.write(1, message.data)
                                sys.stdout.flush()
                            if message.eof:
                                os.close(1)
                        if message.stream_id == protocol.StreamDataMessage.STREAM_ID_STDERR:
                            if message.data and len(message.data) > 0:
                                ttyRestorer.raw()
                                RNS.log(f"stdout: {message.data}", RNS.LOG_DEBUG)
                                os.write(2, message.data)
                                sys.stderr.flush()
                            if message.eof:
                                os.close(2)
                    elif isinstance(message, protocol.CommandExitedMessage):
                        RNS.log(f"received return code {message.return_code}, exiting", RNS.LOG_DEBUG)
                        return message.return_code
                    elif isinstance(message, protocol.ErrorMessage):
                        RNS.log(f"Remote error: {message.data}", RNS.LOG_ERROR)
                        if message.fatal:
                            _link.teardown()
                            return 200

                except queue.Empty:
                    processed = False

                if channel.is_ready_to_send():
                    def compress_adaptive(buf: bytes):
                        comp_tries = RNS.RawChannelWriter.COMPRESSION_TRIES
                        comp_try = 1
                        comp_success = False
                        
                        chunk_len = len(buf)
                        if chunk_len > RNS.RawChannelWriter.MAX_CHUNK_LEN:
                            chunk_len = RNS.RawChannelWriter.MAX_CHUNK_LEN
                        chunk_segment = None

                        chunk_segment = None
                        max_data_len = channel.mdu - protocol.StreamDataMessage.OVERHEAD
                        while chunk_len > 32 and comp_try < comp_tries:
                            chunk_segment_length = int(chunk_len/comp_try)
                            compressed_chunk = bz2.compress(buf[:chunk_segment_length])
                            compressed_length = len(compressed_chunk)
                            if compressed_length < max_data_len and compressed_length < chunk_segment_length:
                                comp_success = True
                                break
                            else:
                                comp_try += 1

                        if comp_success:
                            diff = max_data_len - len(compressed_chunk)
                            chunk = compressed_chunk
                            processed_length = chunk_segment_length
                        else:
                            chunk = bytes(buf[:max_data_len])
                            processed_length = len(chunk)

                        return comp_success, processed_length, chunk

                    comp_success, processed_length, chunk = compress_adaptive(data_buffer)
                    stdin = chunk
                    data_buffer = data_buffer[processed_length:]
                    eof = not sent_eof and stdin_eof and len(stdin) == 0
                    if len(stdin) > 0 or eof:
                        channel.send(protocol.StreamDataMessage(protocol.StreamDataMessage.STREAM_ID_STDIN, stdin, eof, comp_success))
                        sent_eof = eof
                        processed = True

                # send window change, but rate limited
                if winch and time.time() - last_winch > _link.rtt * 25:
                    last_winch = time.time()
                    winch = False
                    with contextlib.suppress(Exception):
                        r, c, h, v = process.tty_get_winsize(0)
                        channel.send(protocol.WindowSizeMessage(r, c, h, v))
                        processed = True
            except RemoteExecutionError as e:
                print(e.msg)
                return 255
            except Exception as ex:
                print(f"Client exception: {ex}")
                if _link and _link.status != RNS.Link.CLOSED:
                    _link.teardown()
                    return 127

        RNS.log("Main loop done", RNS.LOG_DEBUG)
        return 0