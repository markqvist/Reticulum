from __future__ import annotations
import contextlib
import functools
import asyncio
import RNS.Utilities.rnsh.exception as exception
import RNS.Utilities.rnsh.process as process
import RNS.Utilities.rnsh.helpers as helpers
import RNS.Utilities.rnsh.protocol as protocol
import enum
from typing import TypeVar, Generic, Callable, List
from abc import abstractmethod, ABC
from multiprocessing import Manager
import os
import bz2
import RNS

_TLink = TypeVar("_TLink")
_TIdentity = TypeVar("_TIdentity")

class SEType(enum.IntEnum):
    SE_LINK_CLOSED = 0

class SessionException(Exception):
    def __init__(self, setype: SEType, msg: str, *args):
        super().__init__(msg, args)
        self.type = setype

class LSState(enum.IntEnum):
    LSSTATE_WAIT_IDENT = 1
    LSSTATE_WAIT_VERS  = 2
    LSSTATE_WAIT_CMD   = 3
    LSSTATE_RUNNING    = 4
    LSSTATE_ERROR      = 5
    LSSTATE_TEARDOWN   = 6


class LSOutletBase(ABC):
    @abstractmethod
    def set_initiator_identified_callback(self, cb: Callable[[LSOutletBase, _TIdentity], None]): raise NotImplemented()

    @abstractmethod
    def set_link_closed_callback(self, cb: Callable[[LSOutletBase], None]): raise NotImplemented()

    @abstractmethod
    def unset_link_closed_callback(self): raise NotImplemented()

    @property
    @abstractmethod
    def rtt(self): raise NotImplemented()

    @abstractmethod
    def teardown(self): raise NotImplemented()


class ListenerSession:
    sessions: List[ListenerSession] = []
    allowed_identity_hashes: [any] = []
    allowed_file_identity_hashes: [any] = []
    allow_all: bool = False
    allow_remote_command: bool = False
    default_command: [str] = []
    remote_cmd_as_args = False

    def __init__(self, outlet: LSOutletBase, channel: RNS.Channel.Channel, loop: asyncio.AbstractEventLoop):
        RNS.log(f"Session started for {outlet}", RNS.LOG_INFO)
        self.outlet = outlet
        self.channel = channel
        self.outlet.set_initiator_identified_callback(self._initiator_identified)
        self.outlet.set_link_closed_callback(self._link_closed)
        self.loop = loop
        self.state: LSState = None
        self.remote_identity = None
        self.term: str | None = None
        self.stdin_is_pipe: bool = False
        self.stdout_is_pipe: bool = False
        self.stderr_is_pipe: bool = False
        self.tcflags: [any] = None
        self.cmdline: [str] = None
        self.rows: int = 0
        self.cols: int = 0
        self.hpix: int = 0
        self.vpix: int = 0
        self.stdout_buf = bytearray()
        self.stdout_eof_sent = False
        self.stderr_buf = bytearray()
        self.stderr_eof_sent = False
        self.return_code: int | None = None
        self.return_code_sent = False
        self.process: process.CallbackSubprocess | None = None

        if self.allow_all: self._set_state(LSState.LSSTATE_WAIT_VERS)
        else: self._set_state(LSState.LSSTATE_WAIT_IDENT)

        self.sessions.append(self)
        protocol.register_message_types(self.channel)
        self.channel.add_message_handler(self._handle_message)

    def _terminated(self, return_code: int):
        self.return_code = return_code

    def _set_state(self, state: LSState, timeout_factor: float = 10.0):
        timeout = max(self.outlet.rtt * timeout_factor, max(self.outlet.rtt * 2, 10)) if timeout_factor is not None else None
        RNS.log(f"Set state: {state.name}, timeout {timeout}", RNS.LOG_DEBUG)
        orig_state = self.state
        self.state = state
        if timeout_factor is not None:
            self._call(functools.partial(self._check_protocol_timeout, lambda: self.state == orig_state, state.name), timeout)

    def _call(self, func: callable, delay: float = 0):
        def call_inner():
            if delay == 0: func()
            else: self.loop.call_later(delay, func)
        
        self.loop.call_soon_threadsafe(call_inner)

    def send(self, message: RNS.MessageBase):
        self.channel.send(message)

    def _protocol_error(self, name: str):
        self.terminate(f"Protocol error ({name})")

    def _protocol_timeout_error(self, name: str):
        self.terminate(f"Protocol timeout error: {name}")

    def terminate(self, error: str = None):
        with contextlib.suppress(Exception):
            RNS.log("Terminating session" + (f": {error}" if error else ""), RNS.LOG_DEBUG)
            if error and self.state != LSState.LSSTATE_TEARDOWN:
                with contextlib.suppress(Exception):
                    self.send(protocol.ErrorMessage(error, True))

            self.state = LSState.LSSTATE_ERROR
            self._terminate_process()
            self._call(self._prune, max(self.outlet.rtt * 3, process.CallbackSubprocess.PROCESS_PIPE_TIME+5))

    def _prune(self):
        self.state = LSState.LSSTATE_TEARDOWN
        RNS.log("Pruning session", RNS.LOG_DEBUG)
        with contextlib.suppress(ValueError):
            self.sessions.remove(self)
        with contextlib.suppress(Exception):
            self.outlet.teardown()

    def _check_protocol_timeout(self, fail_condition: Callable[[], bool], name: str):
        timeout = True
        try: timeout = self.state != LSState.LSSTATE_TEARDOWN and fail_condition()
        except Exception as e: RNS.log(f"Error in protocol timeout: {e}", RNS.LOG_ERROR)
        if timeout: self._protocol_timeout_error(name)

    def _link_closed(self, outlet: LSOutletBase):
        outlet.unset_link_closed_callback()

        if outlet != self.outlet:
            RNS.log("Link closed received from incorrect outlet", RNS.LOG_DEBUG)
            return

        RNS.log(f"link_closed {outlet}", RNS.LOG_DEBUG)
        self.terminate()

    def _initiator_identified(self, outlet, identity):
        if outlet != self.outlet:
            RNS.log("Identity received from incorrect outlet", RNS.LOG_DEBUG)
            return

        RNS.log(f"initiator_identified {identity} on link {outlet}", RNS.LOG_INFO)
        if self.state not in [LSState.LSSTATE_WAIT_IDENT, LSState.LSSTATE_WAIT_VERS]:
            self._protocol_error(LSState.LSSTATE_WAIT_IDENT.name)

        if not self.allow_all and identity.hash not in self.allowed_identity_hashes and identity.hash not in self.allowed_file_identity_hashes:
            self.terminate("Identity is not allowed.")

        self.remote_identity = identity
        self._set_state(LSState.LSSTATE_WAIT_VERS)

    @classmethod
    async def pump_all(cls) -> True:
        processed_any = False
        for session in cls.sessions:
            processed = session.pump()
            processed_any = processed_any or processed
            await asyncio.sleep(0)


    @classmethod
    async def terminate_all(cls, reason: str):
        for session in cls.sessions:
            session.terminate(reason)
            await asyncio.sleep(0)

    def pump(self) -> bool:
        def compress_adaptive(buf: bytes):
            comp_tries = RNS.RawChannelWriter.COMPRESSION_TRIES
            comp_try = 1
            comp_success = False
            
            chunk_len = len(buf)
            if chunk_len > RNS.RawChannelWriter.MAX_CHUNK_LEN:
                chunk_len = RNS.RawChannelWriter.MAX_CHUNK_LEN
            chunk_segment = None

            chunk_segment = None
            max_data_len = self.channel.mdu - protocol.StreamDataMessage.OVERHEAD
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

        try:
            if self.state != LSState.LSSTATE_RUNNING:
                return False
            elif not self.channel.is_ready_to_send():
                return False
            elif len(self.stderr_buf) > 0:
                comp_success, processed_length, data = compress_adaptive(self.stderr_buf)
                self.stderr_buf = self.stderr_buf[processed_length:]
                send_eof = self.process.stderr_eof and len(data) == 0 and not self.stderr_eof_sent
                self.stderr_eof_sent = self.stderr_eof_sent or send_eof
                msg = protocol.StreamDataMessage(protocol.StreamDataMessage.STREAM_ID_STDERR,
                                                 data, send_eof, comp_success)
                self.send(msg)
                if send_eof:
                    self.stderr_eof_sent = True
                return True
            elif len(self.stdout_buf) > 0:
                comp_success, processed_length, data = compress_adaptive(self.stdout_buf)
                self.stdout_buf = self.stdout_buf[processed_length:]
                send_eof = self.process.stdout_eof and len(data) == 0 and not self.stdout_eof_sent
                self.stdout_eof_sent = self.stdout_eof_sent or send_eof
                msg = protocol.StreamDataMessage(protocol.StreamDataMessage.STREAM_ID_STDOUT,
                                                 data, send_eof, comp_success)
                self.send(msg)
                if send_eof:
                    self.stdout_eof_sent = True
                return True
            elif self.return_code is not None and not self.return_code_sent:
                msg = protocol.CommandExitedMessage(self.return_code)
                self.send(msg)
                self.return_code_sent = True
                self._call(functools.partial(self._check_protocol_timeout,
                                             lambda: self.state == LSState.LSSTATE_RUNNING, "CommandExitedMessage"),
                           max(self.outlet.rtt * 5, 10))
                return False
        
        except Exception as e: RNS.log(f"Error during pump: {e}", RNS.LOG_ERROR)
        return False

    def _terminate_process(self):
        with contextlib.suppress(Exception):
            if self.process and self.process.running:
                self.process.terminate()

    def _start_cmd(self, cmdline: [str], pipe_stdin: bool, pipe_stdout: bool, pipe_stderr: bool, tcflags: [any],
                   term: str | None, rows: int, cols: int, hpix: int, vpix: int):

        self.cmdline = self.default_command
        if not self.allow_remote_command and cmdline and len(cmdline) > 0:
            self.terminate("Remote command line not allowed by listener")
            return

        if self.remote_cmd_as_args and cmdline and len(cmdline) > 0:
            self.cmdline.extend(cmdline)
        elif cmdline and len(cmdline) > 0:
            self.cmdline = cmdline


        self.stdin_is_pipe = pipe_stdin
        self.stdout_is_pipe = pipe_stdout
        self.stderr_is_pipe = pipe_stderr
        self.tcflags = tcflags
        self.term = term

        def stdout(data: bytes):
            self.stdout_buf.extend(data)

        def stderr(data: bytes):
            self.stderr_buf.extend(data)

        try:
            self.process = process.CallbackSubprocess(argv=self.cmdline,
                                                      env={"TERM": self.term or os.environ.get("TERM") or "xterm",
                                                            "RNS_REMOTE_IDENTITY": (RNS.prettyhexrep(self.remote_identity.hash)
                                                                if self.remote_identity and self.remote_identity.hash else "")},
                                                      loop=self.loop,
                                                      stdout_callback=stdout,
                                                      stderr_callback=stderr,
                                                      terminated_callback=self._terminated,
                                                      stdin_is_pipe=self.stdin_is_pipe,
                                                      stdout_is_pipe=self.stdout_is_pipe,
                                                      stderr_is_pipe=self.stderr_is_pipe)
            self.process.start()
            self._set_window_size(rows, cols, hpix, vpix)
        except Exception as e:
            RNS.log(f"Unable to start process for link {self.outlet}: {e}", RNS.LOG_ERROR)
            self.terminate("Unable to start process")

    def _set_window_size(self, rows: int, cols: int, hpix: int, vpix: int):
        self.rows = rows
        self.cols = cols
        self.hpix = hpix
        self.vpix = vpix
        with contextlib.suppress(Exception):
            self.process.set_winsize(rows, cols, hpix, vpix)

    def _received_stdin(self, data: bytes, eof: bool):
        if data and len(data) > 0:
            self.process.write(data)
        if eof:
            self.process.close_stdin()

    def _handle_message(self, message: RNS.MessageBase):
        if self.state == LSState.LSSTATE_WAIT_IDENT:
            # Ignore any messages until the initiator has identified to avoid race conditions
            # between identity announcement and early protocol messages.
            RNS.log("Ignoring message while waiting for identification", RNS.LOG_DEBUG)
            return
        if self.state == LSState.LSSTATE_WAIT_VERS:
            if not isinstance(message, protocol.VersionInfoMessage):
                self._protocol_error(self.state.name)
                return
            RNS.log(f"Version {message.sw_version}, protocol {message.protocol_version} on link {self.outlet}", RNS.LOG_VERBOSE)
            if message.protocol_version != protocol.PROTOCOL_VERSION:
                self.terminate("Incompatible protocol")
                return
            self.send(protocol.VersionInfoMessage())
            self._set_state(LSState.LSSTATE_WAIT_CMD)
            return
        elif self.state == LSState.LSSTATE_WAIT_CMD:
            if not isinstance(message, protocol.ExecuteCommandMesssage):
                return self._protocol_error(self.state.name)
            RNS.log(f"Execute command message on link {self.outlet}: {message.cmdline}", RNS.LOG_VERBOSE)
            self._set_state(LSState.LSSTATE_RUNNING)
            self._start_cmd(message.cmdline, message.pipe_stdin, message.pipe_stdout, message.pipe_stderr,
                            message.tcflags, message.term, message.rows, message.cols, message.hpix, message.vpix)
            return
        elif self.state == LSState.LSSTATE_RUNNING:
            if isinstance(message, protocol.WindowSizeMessage):
                self._set_window_size(message.rows, message.cols, message.hpix, message.vpix)
            elif isinstance(message, protocol.StreamDataMessage):
                if message.stream_id != protocol.StreamDataMessage.STREAM_ID_STDIN:
                    RNS.log(f"Received stream data for invalid stream {message.stream_id} on link {self.outlet}", RNS.LOG_ERROR)
                    return self._protocol_error(self.state.name)
                self._received_stdin(message.data, message.eof)
                return
            elif isinstance(message, protocol.NoopMessage):
                # echo noop only on listener--used for keepalive/connectivity check
                self.send(message)
                return
        elif self.state in [LSState.LSSTATE_ERROR, LSState.LSSTATE_TEARDOWN]:
            RNS.log(f"Received packet, but in state {self.state.name}", RNS.LOG_ERROR)
            return
        else:
            self._protocol_error("unexpected message")
            return


class RNSOutlet(LSOutletBase):

    def set_initiator_identified_callback(self, cb: Callable[[LSOutletBase, _TIdentity], None]):
        def inner_cb(link, identity: _TIdentity):
            cb(self, identity)

        self.link.set_remote_identified_callback(inner_cb)

    def set_link_closed_callback(self, cb: Callable[[LSOutletBase], None]):
        def inner_cb(link):
            cb(self)

        self.link.set_link_closed_callback(inner_cb)

    def unset_link_closed_callback(self):
        self.link.set_link_closed_callback(None)

    def teardown(self):
        self.link.teardown()

    @property
    def rtt(self) -> float:
        return self.link.rtt

    def __str__(self):
        return f"Outlet RNS Link {self.link}"

    def __init__(self, link: RNS.Link):
        self.link = link
        link.lsoutlet = self

    @staticmethod
    def get_outlet(link: RNS.Link):
        if hasattr(link, "lsoutlet"):
            return link.lsoutlet

        return RNSOutlet(link)