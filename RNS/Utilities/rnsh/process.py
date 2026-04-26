# MIT License
#
# Copyright (c) 2023 Aaron Heise
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

from __future__ import annotations
import asyncio
import contextlib
import copy
import errno
import fcntl
import functools
import os
import pty
import select
import signal
import struct
import sys
import termios
import threading
import tty
import types
import typing
import RNS

import RNS.Utilities.rnsh.exception as exception

CTRL_C = "\x03".encode("utf-8")
CTRL_D = "\x04".encode("utf-8")

def tty_add_reader_callback(fd: int, callback: callable, loop: asyncio.AbstractEventLoop = None):
    """
    Add an async reader callback for a tty file descriptor.

    Example usage:

        def reader():
            data = tty_read(fd)
            # do something with data

        tty_add_reader_callback(self._child_fd, reader, self._loop)

    :param fd: file descriptor
    :param callback: callback function
    :param loop: asyncio event loop to which the reader should be added. If None, use the currently-running loop.
    """
    if loop is None:
        loop = asyncio.get_running_loop()
    loop.add_reader(fd, callback)


def tty_read(fd: int) -> bytes:
    """
    Read available bytes from a tty file descriptor. When used in a callback added to a file descriptor using
    tty_add_reader_callback(...), this function creates a solution for non-blocking reads from ttys.
    :param fd: tty file descriptor
    :return: bytes read
    """
    if fd_is_closed(fd):
        raise EOFError

    try:
        run = True
        result = bytearray()
        while not fd_is_closed(fd):
            ready, _, _ = select.select([fd], [], [], 0)
            if len(ready) == 0:
                break
            for f in ready:
                try:
                    data = os.read(f, 4096)
                except OSError as e:
                    if e.errno != errno.EIO and e.errno != errno.EWOULDBLOCK:
                        raise
                else:
                    if not data:  # EOF
                        if data is not None and len(data) > 0:
                            result.extend(data)
                            return result
                        elif len(result) > 0:
                            return result
                        else:
                            raise EOFError
                    if data is not None and len(data) > 0:
                        result.extend(data)
        return result
    
    except EOFError: raise
    except Exception as e: RNS.log(f"TTY read error: {e}", RNS.LOG_ERROR)


def tty_read_poll(fd: int) -> bytes:
    """
    Read available bytes from a tty file descriptor. When used in a callback added to a file descriptor using
    tty_add_reader_callback(...), this function creates a solution for non-blocking reads from ttys.
    :param fd: tty file descriptor
    :return: bytes read
    """
    if fd_is_closed(fd):
        raise EOFError

    result = bytearray()
    try:
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        while True:
            try:
                data = os.read(fd, 4096)
                if not data:
                    # EOF
                    if len(result) > 0:
                        return result
                    raise EOFError
                result.extend(data)
                # continue loop to drain
            except OSError as e:
                if e.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                    break
                if e.errno == errno.EIO:
                    if len(result) > 0:
                        return result
                    raise EOFError
                raise
    except EOFError: raise
    except Exception as e: RNS.log(f"TTY read error: {e}", RNS.LOG_ERROR)
    
    return result


def fd_is_closed(fd: int) -> bool:
    """
    Check if file descriptor is closed
    :param fd: file descriptor
    :return: True if file descriptor is closed
    """
    try:
        fcntl.fcntl(fd, fcntl.F_GETFL) < 0
    except OSError as ose:
        return ose.errno == errno.EBADF


def tty_unset_reader_callbacks(fd: int, loop: asyncio.AbstractEventLoop = None):
    """
    Remove async reader callbacks for file descriptor.
    :param fd: file descriptor
    :param loop: asyncio event loop from which to remove callbacks
    """
    with exception.permit(SystemExit):
        if loop is None:
            loop = asyncio.get_running_loop()
        loop.remove_reader(fd)


def tty_get_winsize(fd: int) -> [int, int, int, int]:
    """
    Ge the window size of a tty.
    :param fd: file descriptor of tty
    :return: (rows, cols, h_pixels, v_pixels)
    """
    packed = fcntl.ioctl(fd, termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0))
    rows, cols, h_pixels, v_pixels = struct.unpack('HHHH', packed)
    return rows, cols, h_pixels, v_pixels


def tty_set_winsize(fd: int, rows: int, cols: int, h_pixels: int, v_pixels: int):
    """
    Set the window size on a tty.
    :param fd: file descriptor of tty
    :param rows: number of visible rows
    :param cols: number of visible columns
    :param h_pixels: number of visible horizontal pixels
    :param v_pixels: number of visible vertical pixels
    """
    if fd < 0:
        return
    packed = struct.pack('HHHH', rows, cols, h_pixels, v_pixels)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, packed)


def process_exists(pid) -> bool:
    """
    Check For the existence of a unix pid.
    :param pid: process id to check
    :return: True if process exists
    """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


class TTYRestorer(contextlib.AbstractContextManager):
    # Indexes of flags within the attrs array
    ATTR_IDX_IFLAG = 0
    ATTR_IDX_OFLAG = 1
    ATTR_IDX_CFLAG = 2
    ATTR_IDX_LFLAG = 4
    ATTR_IDX_CC    = 5

    def __init__(self, fd: int, suppress_logs=False):
        """
        Saves termios attributes for a tty for later restoration.

        The attributes are an array of values with the following meanings.

            tcflag_t c_iflag;      /* input modes */
            tcflag_t c_oflag;      /* output modes */
            tcflag_t c_cflag;      /* control modes */
            tcflag_t c_lflag;      /* local modes */
            cc_t     c_cc[NCCS];   /* special characters */

        :param fd: file descriptor of tty
        """
        self._fd = fd
        self._tattr = None
        self._suppress_logs = suppress_logs
        self._tattr = self.current_attr()
        if not self._tattr and not self._suppress_logs: RNS.log(f"Could not get attrs for fd {fd}", RNS.LOG_DEBUG)

    def raw(self):
        """
        Set raw mode on tty
        """
        if self._fd is None:
            return
        with contextlib.suppress(termios.error):
            tty.setraw(self._fd, termios.TCSANOW)

    def original_attr(self) -> [any]:
        return copy.deepcopy(self._tattr)

    def current_attr(self) -> [any]:
        """
        Get the current termios attributes for the wrapped fd.
        :return: attribute array
        """
        if self._fd is None:
            return None

        with contextlib.suppress(termios.error):
            return copy.deepcopy(termios.tcgetattr(self._fd))
        return None

    def set_attr(self, attr: [any], when: int = termios.TCSADRAIN):
        """
        Set termios attributes
        :param attr: attribute list to set
        :param when: when attributes should be applied (termios.TCSANOW, termios.TCSADRAIN, termios.TCSAFLUSH)
        """
        if not attr or self._fd is None:
            return

        with contextlib.suppress(termios.error):
            termios.tcsetattr(self._fd, when, attr)

    def isatty(self):
        return os.isatty(self._fd) if self._fd is not None else None

    def restore(self):
        """
        Restore termios settings to state captured in constructor.
        """
        self.set_attr(self._tattr, termios.TCSADRAIN)

    def __exit__(self, __exc_type: typing.Type[BaseException], __exc_value: BaseException,
                 __traceback: types.TracebackType) -> bool:
        self.restore()
        return False  #__exc_type is not None and issubclass(__exc_type, termios.error)


def _task_from_event(evt: asyncio.Event, loop: asyncio.AbstractEventLoop = None):
    if not loop:
        loop = asyncio.get_running_loop()

    #TODO: this is hacky
    async def wait():
        while not evt.is_set():
            await asyncio.sleep(0.1)
        return True

    return loop.create_task(wait())


class AggregateException(Exception):
    def __init__(self, inner_exceptions: [Exception]):
        super().__init__()
        self.inner_exceptions = inner_exceptions

    def __str__(self):
        return "Multiple exceptions encountered: \n\n" + "\n\n".join(map(lambda e: str(e), self.inner_exceptions))


async def event_wait_any(evts: [asyncio.Event], timeout: float  = None) -> (any, any):
    tasks = list(map(lambda evt: (evt, _task_from_event(evt)), evts))
    try:
        finished, unfinished = await asyncio.wait(map(lambda t: t[1], tasks),
                                                  timeout=timeout,
                                                  return_when=asyncio.FIRST_COMPLETED)

        if len(unfinished) > 0:
            for task in unfinished:
                task.cancel()
            await asyncio.wait(unfinished)

        exceptions = []

        for f in finished:
            ex = f.exception()
            if ex and not isinstance(ex, asyncio.CancelledError) and not isinstance(ex, TimeoutError):
                exceptions.append(ex)

        if len(exceptions) > 0:
            raise AggregateException(exceptions)

        return next(map(lambda t: next(map(lambda tt: tt[0], tasks)), finished), None)
    finally:
        unfinished = []
        for task in map(lambda t: t[1], tasks):
            if task.done():
                if not task.cancelled():
                    task.exception()
            else:
                task.cancel()
                unfinished.append(task)
        if len(unfinished) > 0:
            await asyncio.wait(unfinished)


async def event_wait(evt: asyncio.Event, timeout: float) -> bool:
    """
    Wait for event to be set, or timeout to expire.
    :param evt: asyncio.Event to wait on
    :param timeout: maximum number of seconds to wait.
    :return: True if event was set, False if timeout expired
    """
    await event_wait_any([evt], timeout=timeout)
    return evt.is_set()


def _launch_child(cmd_line: list[str], env: dict[str, str], stdin_is_pipe: bool, stdout_is_pipe: bool,
                  stderr_is_pipe: bool) -> tuple[int, int, int, int]:
    # Set up PTY and/or pipes
    child_fd = parent_fd = None
    if not (stdin_is_pipe and stdout_is_pipe and stderr_is_pipe):
        parent_fd, child_fd = pty.openpty()
    child_stdin, parent_stdin = (os.pipe() if stdin_is_pipe else (child_fd, parent_fd))
    parent_stdout, child_stdout = (os.pipe() if stdout_is_pipe else (parent_fd, child_fd))
    parent_stderr, child_stderr = (os.pipe() if stderr_is_pipe else (parent_fd, child_fd))

    # Fork
    pid = os.fork()

    if pid == 0:
        try:
            # We are in the child process, so close all open sockets and pipes except for the PTY and/or pipes
            max_fd = os.sysconf("SC_OPEN_MAX")
            for fd in range(3, max_fd):
                if fd not in (child_stdin, child_stdout, child_stderr):
                    try:
                        os.close(fd)
                    except OSError:
                        pass

            # Set up PTY and/or pipes
            os.dup2(child_stdin, 0)
            os.dup2(child_stdout, 1)
            os.dup2(child_stderr, 2)
            # Make PTY controlling if necessary so that CTRL_C/CTRL_D behave as expected
            if child_fd is not None:
                os.setsid()
                try:
                    tty_fd = 0 if not stdin_is_pipe else (1 if not stdout_is_pipe else 2)
                    # Set controlling TTY for this session
                    fcntl.ioctl(tty_fd, termios.TIOCSCTTY, 0)
                except Exception:
                    pass
                # Ensure the child is the foreground process group for the TTY
                try:
                    os.setpgid(0, 0)
                    pgid = os.getpgrp()
                    import struct as _struct
                    fcntl.ioctl(tty_fd, termios.TIOCSPGRP, _struct.pack('i', pgid))
                except Exception:
                    pass
                # Ensure canonical input with signals and local echo enabled
                try:
                    tty_fd = 0 if not stdin_is_pipe else (1 if not stdout_is_pipe else 2)
                    attrs = termios.tcgetattr(tty_fd)
                    lflag = attrs[3]
                    lflag |= termios.ICANON | termios.ISIG | termios.ECHO
                    attrs[3] = lflag
                    termios.tcsetattr(tty_fd, termios.TCSANOW, attrs)
                except Exception:
                    pass

            # Execute the command
            os.execvpe(cmd_line[0], cmd_line, env)
        except Exception as err:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(f"Unable to start {cmd_line[0]}: {err} ({fname}:{exc_tb.tb_lineno})")
            sys.stdout.flush()
        # don't let any other modules get in our way, do an immediate silent exit.
        os._exit(255)

    else:
        # We are in the parent process, so close the child-side of the PTY and/or pipes
        if child_fd is not None:
            os.close(child_fd)
        if child_stdin != child_fd:
            os.close(child_stdin)
        if child_stdout != child_fd:
            os.close(child_stdout)
        if child_stderr != child_fd:
            os.close(child_stderr)
        # # Close the write end of the pipe if a pipe is used for standard input
        # if not stdin_is_pipe:
        #     os.close(parent_stdin)
        # Return the child PID and the file descriptors for the PTY and/or pipes
        return pid, parent_stdin, parent_stdout, parent_stderr


class CallbackSubprocess:
    # time between checks of child process
    PROCESS_POLL_TIME: float = 0.1
    # Close pipes soon after process exit to avoid scheduling on closed event loops
    PROCESS_PIPE_TIME: int = 1

    def __init__(self, argv: [str], env: dict, loop: asyncio.AbstractEventLoop, stdout_callback: callable,
                 stderr_callback: callable, terminated_callback: callable, stdin_is_pipe: bool, stdout_is_pipe: bool,
                 stderr_is_pipe: bool):
        """
        Fork a child process and generate callbacks with output from the process.
        :param argv: the command line, tokenized. The first element must be the absolute path to an executable file.
        :param env: environment variables to override
        :param loop: the asyncio event loop to use
        :param stdout_callback: callback for data, e.g. def callback(data:bytes) -> None
        :param terminated_callback: callback for termination/return code, e.g. def callback(return_code:int) -> None
        """
        assert loop is not None, "loop should not be None"
        assert stdout_callback is not None, "stdout_callback should not be None"
        assert terminated_callback is not None, "terminated_callback should not be None"

        self._command: [str] = argv
        self._env = env or {}
        self._loop = loop
        self._stdout_cb = stdout_callback
        self._stderr_cb = stderr_callback
        self._terminated_cb = terminated_callback
        self._pid: int = None
        self._child_stdin: int = None
        self._child_stdout: int = None
        self._child_stderr: int = None
        self._return_code: int = None
        self._stdout_eof: bool = False
        self._stderr_eof: bool = False
        self._stdin_is_pipe = stdin_is_pipe
        self._stdout_is_pipe = stdout_is_pipe
        self._stderr_is_pipe = stderr_is_pipe
        self._at_line_start: bool = True
        self._tty_line_buffer: bytearray = bytearray()

    def _ensure_pipes_closed(self):
        stdin = self._child_stdin
        stdout = self._child_stdout
        stderr = self._child_stderr
        fds = set(filter(lambda x: x is not None, list({stdin, stdout, stderr})))
        RNS.log(f"Queuing close of pipes for ended process (fds: {fds})", RNS.LOG_DEBUG)

        def ensure_pipes_closed_inner():
            RNS.log(f"Ensuring pipes are closed (fds: {fds})", RNS.LOG_DEBUG)
            for fd in fds:
                RNS.log(f"Closing fd {fd}", RNS.LOG_DEBUG)
                with contextlib.suppress(OSError): tty_unset_reader_callbacks(fd)
                with contextlib.suppress(OSError): os.close(fd)

            self._child_stdin = None
            self._child_stdout = None
            self._child_stderr = None

        # Avoid scheduling on a closed loop
        if self._loop.is_closed(): ensure_pipes_closed_inner()
        else:                      self._loop.call_later(CallbackSubprocess.PROCESS_PIPE_TIME, ensure_pipes_closed_inner)

    def terminate(self, kill_delay: float = 1.0):
        """
        Terminate child process if running
        :param kill_delay: if after kill_delay seconds the child process has not exited, escalate to SIGHUP and SIGKILL
        """

        RNS.log("terminate()", RNS.LOG_EXTREME)
        if not self.running: return

        with exception.permit(SystemExit): os.kill(self._pid, signal.SIGTERM)

        def kill():
            if process_exists(self._pid):
                RNS.log("kill()", RNS.LOG_EXTREME)
                with exception.permit(SystemExit):
                    os.kill(self._pid, signal.SIGHUP)
                    os.kill(self._pid, signal.SIGKILL)

        self._loop.call_later(kill_delay, kill)

        def wait():
            RNS.log("wait()", RNS.LOG_EXTREME)
            with contextlib.suppress(OSError): os.waitpid(self._pid, 0)
            self._ensure_pipes_closed()
            RNS.log("wait() finish", RNS.LOG_EXTREME)

        threading.Thread(target=wait, daemon=True).start()

    def close_stdin(self):
        with contextlib.suppress(Exception):
            os.close(self._child_stdin)
        # Encourage prompt shutdown if child lingers after stdin close
        def _ensure_terminate():
            if self.running:
                self.terminate(kill_delay=0.2)
        if not self._loop.is_closed():
            self._loop.call_later(0.05, _ensure_terminate)

    @property
    def started(self) -> bool:
        """
        :return: True if child process has been started
        """
        return self._pid is not None

    @property
    def running(self) -> bool:
        """
        :return: True if child process is still running
        """
        return self._pid is not None and process_exists(self._pid)

    def write(self, data: bytes):
        """
        Write bytes to the stdin of the child process.
        :param data: bytes to write
        """

        os.write(self._child_stdin, data)

        # TODO: Check what this is actually supposed to solve.
        #
        # For pipe-in + TTY-out, echo should be visible immediately
        if self._stdin_is_pipe and not self._stdout_is_pipe and self._stdout_cb is not None and data not in (CTRL_C, CTRL_D):
            try: self._stdout_cb(data)
            except Exception: pass

    def set_winsize(self, r: int, c: int, h: int, v: int):
        """
        Set the window size on the tty of the child process.
        :param r: rows visible
        :param c: columns visible
        :param h: horizontal pixels visible
        :param v: vertical pixels visible
        :return:
        """
        RNS.log(f"set_winsize({r},{c},{h},{v}", RNS.LOG_DEBUG)
        tty_set_winsize(self._child_stdout, r, c, h, v)

    def copy_winsize(self, fromfd: int):
        """
        Copy window size from one tty to another.
        :param fromfd: source tty file descriptor
        """
        r, c, h, v = tty_get_winsize(fromfd)
        self.set_winsize(r, c, h, v)

    def tcsetattr(self, when: int, attr: list[any]):  # actual type is list[int | list[int | bytes]]
        """
        Set tty attributes.
        :param when: when to apply change: termios.TCSANOW or termios.TCSADRAIN or termios.TCSAFLUSH
        :param attr: attributes to set
        """
        termios.tcsetattr(self._child_stdin, when, attr)

    def tcgetattr(self) -> list[any]:  # actual type is list[int | list[int | bytes]]
        """
        Get tty attributes.
        :return: tty attributes value
        """
        return termios.tcgetattr(self._child_stdout)

    def ttysetraw(self):
        tty.setraw(self._child_stdout, termios.TCSADRAIN)

    def start(self):
        """
        Start the child process.
        """
        RNS.log("start()", RNS.LOG_EXTREME)

        # # Using the parent environment seems to do some weird stuff, at least on macOS
        # parentenv = os.environ.copy()
        # env = {"HOME": parentenv["HOME"],
        #        "PATH": parentenv["PATH"],
        #        "TERM": self._term if self._term is not None else parentenv.get("TERM", "xterm"),
        #        "LANG": parentenv.get("LANG"),
        #        "SHELL": self._command[0]}

        env = os.environ.copy()
        for key in self._env:
            env[key] = self._env[key]

        program = self._command[0]
        assert isinstance(program, str)

        # match = re.search("^/bin/(.*sh)$", program)
        # if match:
        #     self._command[0] = "-" + match.group(1)
        #     env["SHELL"] = program
        #     self._log.debug(f"set login shell {self._command}")

        self._pid, \
            self._child_stdin, \
            self._child_stdout, \
            self._child_stderr = _launch_child(self._command, env, self._stdin_is_pipe, self._stdout_is_pipe,
                                               self._stderr_is_pipe)
        RNS.log(f"Started pid {self.pid}, fds: {self._child_stdin}, {self._child_stdout}, {self._child_stderr}", RNS.LOG_DEBUG)

        def poll():
            try:
                pid, self._return_code = os.waitpid(self._pid, os.WNOHANG)
                if self._return_code is not None:
                    self._return_code = self._return_code & 0xff
                if self._return_code is not None and not process_exists(self._pid):
                    RNS.log(f"polled return code {self._return_code}", RNS.LOG_DEBUG)
                    self._terminated_cb(self._return_code)
                if self.running:
                    self._loop.call_later(CallbackSubprocess.PROCESS_POLL_TIME, poll)
                else:
                    self._ensure_pipes_closed()
            except Exception as e:
                if not hasattr(e, "errno") or e.errno != errno.ECHILD:
                    RNS.log(f"Error in process poll: {e}", RNS.LOG_DEBUG)

        self._loop.call_later(CallbackSubprocess.PROCESS_POLL_TIME, poll)

        def stdout():
            try:
                with exception.permit(SystemExit):
                    data = tty_read_poll(self._child_stdout)
                    if data is not None and len(data) > 0:
                        self._stdout_cb(data)
                        # Opportunistically drain shortly after to coalesce immediate follow-up output
                        if not self._loop.is_closed():
                            self._loop.call_later(0.01, stdout)
            except EOFError:
                self._stdout_eof = True
                tty_unset_reader_callbacks(self._child_stdout)
                self._stdout_cb(bytearray())

        def stderr():
            try:
                with exception.permit(SystemExit):
                    data = tty_read_poll(self._child_stderr)
                    if data is not None and len(data) > 0:
                        self._stderr_cb(data)
                        if not self._loop.is_closed():
                            self._loop.call_later(0.01, stderr)
            except EOFError:
                self._stderr_eof = True
                tty_unset_reader_callbacks(self._child_stderr)
                self._stderr_cb(bytearray())

        tty_add_reader_callback(self._child_stdout, stdout, self._loop)
        if self._child_stderr != self._child_stdout:
            tty_add_reader_callback(self._child_stderr, stderr, self._loop)

    @property
    def stdout_eof(self):
        return self._stdout_eof or not self.running

    @property
    def stderr_eof(self):
        return self._stderr_eof or not self.running


    @property
    def return_code(self) -> int:
        return self._return_code

    @property
    def pid(self) -> int:
        return self._pid


async def main():
    """
    A test driver for the CallbackProcess class.
    python ./process.py /bin/zsh --login
    """

    if len(sys.argv) <= 1:
        print(f"Usage: {sys.argv} <absolute_path_to_child_executable> [child_arg ...]")
        exit(1)

    loop = asyncio.get_event_loop()
    # asyncio.set_event_loop(loop)
    retcode = loop.create_future()

    def stdout(data: bytes): os.write(sys.stdout.fileno(), data)

    def terminated(rc: int): retcode.set_result(rc)

    process = CallbackSubprocess(argv=sys.argv[1:],
                                 env={"TERM": os.environ.get("TERM", "xterm")},
                                 loop=loop,
                                 stdout_callback=stdout,
                                 terminated_callback=terminated)

    def sigint_handler(sig, frame):
        if process is None or process.started and not process.running:
            raise KeyboardInterrupt
        elif process.running:
            process.write("\x03".encode("utf-8"))

    def sigwinch_handler(sig, frame):
        process.copy_winsize(sys.stdin.fileno())

    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGWINCH, sigwinch_handler)

    def stdin():
        try:
            data = tty_read(sys.stdin.fileno())
            if data is not None:
                process.write(data)

        except EOFError:
            tty_unset_reader_callbacks(sys.stdin.fileno())
            process.write(CTRL_D)

    tty_add_reader_callback(sys.stdin.fileno(), stdin)
    process.start()
    # call_soon called it too soon, not sure why.
    loop.call_later(0.001, functools.partial(process.copy_winsize, sys.stdin.fileno()))

    val = await retcode
    RNS.log(f"Got return code {val}", RNS.LOG_DEBUG)
    return val


if __name__ == "__main__":
    tr = TTYRestorer(sys.stdin.fileno())
    try:
        tr.raw()
        asyncio.run(main())
    finally:
        tty_unset_reader_callbacks(sys.stdin.fileno())
        tr.restore()
