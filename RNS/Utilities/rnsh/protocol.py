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

import RNS
from RNS.vendor import umsgpack
from RNS.Buffer import StreamDataMessage as RNSStreamDataMessage
import RNS.Utilities.rnsh.retry
import abc
import contextlib
import struct
from abc import ABC, abstractmethod

MSG_MAGIC = 0xac
PROTOCOL_VERSION = 1

def _make_MSGTYPE(val: int):
    return ((MSG_MAGIC << 8) & 0xff00) | (val & 0x00ff)


class NoopMessage(RNS.MessageBase):
    MSGTYPE = _make_MSGTYPE(0)
    def pack(self) -> bytes: return bytes()
    def unpack(self, raw): pass


class WindowSizeMessage(RNS.MessageBase):
    MSGTYPE = _make_MSGTYPE(2)

    def __init__(self, rows: int = None, cols: int = None, hpix: int = None, vpix: int = None):
        super().__init__()
        self.rows = rows
        self.cols = cols
        self.hpix = hpix
        self.vpix = vpix

    def pack(self) -> bytes: return umsgpack.packb((self.rows, self.cols, self.hpix, self.vpix))
    def unpack(self, raw): self.rows, self.cols, self.hpix, self.vpix = umsgpack.unpackb(raw)


class ExecuteCommandMesssage(RNS.MessageBase):
    MSGTYPE = _make_MSGTYPE(3)

    def __init__(self, cmdline: [str] = None, pipe_stdin: bool = False, pipe_stdout: bool = False,
                 pipe_stderr: bool = False, tcflags: [any] = None, term: str | None = None, rows: int = None,
                 cols: int = None, hpix: int = None, vpix: int = None):
        
        super().__init__()
        self.cmdline = cmdline
        self.pipe_stdin = pipe_stdin
        self.pipe_stdout = pipe_stdout
        self.pipe_stderr = pipe_stderr
        self.tcflags = tcflags
        self.term = term
        self.rows = rows
        self.cols = cols
        self.hpix = hpix
        self.vpix = vpix

    def pack(self) -> bytes:
        return umsgpack.packb((self.cmdline, self.pipe_stdin, self.pipe_stdout, self.pipe_stderr,
                               self.tcflags, self.term, self.rows, self.cols, self.hpix, self.vpix))

    def unpack(self, raw):
        self.cmdline, self.pipe_stdin, self.pipe_stdout, self.pipe_stderr, self.tcflags, self.term, self.rows, \
            self.cols, self.hpix, self.vpix = umsgpack.unpackb(raw)


# Create a version of RNS.Buffer.StreamDataMessage that we control
class StreamDataMessage(RNSStreamDataMessage):
    MSGTYPE = _make_MSGTYPE(4)
    STREAM_ID_STDIN  = 0
    STREAM_ID_STDOUT = 1
    STREAM_ID_STDERR = 2


class VersionInfoMessage(RNS.MessageBase):
    MSGTYPE = _make_MSGTYPE(5)

    def __init__(self, sw_version: str = None):
        super().__init__()
        self.sw_version = sw_version or RNS.Utilities.rnsh.__version__
        self.protocol_version = PROTOCOL_VERSION

    def pack(self) -> bytes: return umsgpack.packb((self.sw_version, self.protocol_version))
    def unpack(self, raw): self.sw_version, self.protocol_version = umsgpack.unpackb(raw)


class ErrorMessage(RNS.MessageBase):
    MSGTYPE = _make_MSGTYPE(6)

    def __init__(self, msg: str = None, fatal: bool = False, data: dict = None):
        super().__init__()
        self.msg = msg
        self.fatal = fatal
        self.data = data

    def pack(self) -> bytes: return umsgpack.packb((self.msg, self.fatal, self.data))
    def unpack(self, raw: bytes): self.msg, self.fatal, self.data = umsgpack.unpackb(raw)


class CommandExitedMessage(RNS.MessageBase):
    MSGTYPE = _make_MSGTYPE(7)

    def __init__(self, return_code: int = None):
        super().__init__()
        self.return_code = return_code

    def pack(self) -> bytes: return umsgpack.packb(self.return_code)
    def unpack(self, raw: bytes): self.return_code = umsgpack.unpackb(raw)


message_types = [NoopMessage, VersionInfoMessage, WindowSizeMessage, ExecuteCommandMesssage, StreamDataMessage,
                 CommandExitedMessage, ErrorMessage]

def register_message_types(channel: RNS.Channel.Channel):
    for message_type in message_types: channel.register_message_type(message_type)