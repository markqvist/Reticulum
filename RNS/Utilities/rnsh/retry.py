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

import asyncio
import threading
import time
import rnsh.exception as exception
from typing import Callable
from contextlib import AbstractContextManager
import types
import typing


class RetryStatus:
    def __init__(self, tag: any, try_limit: int, wait_delay: float, retry_callback: Callable[[any, int], any],
                 timeout_callback: Callable[[any, int], None], tries: int = 1):
        
        self.tag = tag
        self.try_limit = try_limit
        self.tries = tries
        self.wait_delay = wait_delay
        self.retry_callback = retry_callback
        self.timeout_callback = timeout_callback
        self.try_time = time.time()
        self.completed = False

    @property
    def ready(self):
        ready = time.time() > self.try_time + self.wait_delay
        RNS.log(f"ready check {self.tag} try_time {self.try_time} wait_delay {self.wait_delay} " +
                        f"next_try {self.try_time + self.wait_delay} now {time.time()} " +
                        f"exceeded {time.time() - self.try_time - self.wait_delay} ready {ready}", RNS.LOG_DEBUG)
        return ready

    @property
    def timed_out(self):
        return self.ready and self.tries >= self.try_limit

    def timeout(self):
        self.completed = True
        self.timeout_callback(self.tag, self.tries)

    def retry(self) -> any:
        self.tries = self.tries + 1
        self.try_time = time.time()
        return self.retry_callback(self.tag, self.tries)


class RetryThread(AbstractContextManager):
    def __init__(self, loop_period: float = 0.25, name: str = "retry thread"):
        self._loop_period = loop_period
        self._statuses: list[RetryStatus] = []
        self._tag_counter = 0
        self._lock = threading.RLock()
        self._run = True
        self._finished: asyncio.Future = None
        self._thread = threading.Thread(name=name, target=self._thread_run, daemon=True)
        self._thread.start()

    def is_alive(self):
        return self._thread.is_alive()

    def close(self, loop: asyncio.AbstractEventLoop = None) -> asyncio.Future:
        RNS.log("Stopping timer thread", RNS.LOG_DEBUG)
        if loop is None:
            self._run = False
            self._thread.join()
            return None
        else:
            self._finished = loop.create_future()
            return self._finished

    def wait(self, timeout: float = None):
        if timeout:
            timeout = timeout + time.time()

        while timeout is None or time.time() < timeout:
            with self._lock:
                task_count = len(self._statuses)
            if task_count == 0:
                return
            time.sleep(0.1)


    def _thread_run(self):
        while self._run and self._finished is None:
            time.sleep(self._loop_period)
            ready: list[RetryStatus] = []
            prune: list[RetryStatus] = []
            with self._lock: ready.extend(list(filter(lambda s: s.ready, self._statuses)))
            
            for retry in ready:
                try:
                    if not retry.completed:
                        if retry.timed_out:
                            RNS.log(f"Timed out {retry.tag} after {retry.try_limit} tries", RNS.LOG_DEBUG)
                            retry.timeout()
                            prune.append(retry)
                        elif retry.ready:
                            RNS.log(f"Retrying {retry.tag}, try {retry.tries + 1}/{retry.try_limit}", RNS.LOG_DEBUG)
                            should_continue = retry.retry()
                            if not should_continue: self.complete(retry.tag)
                
                except Exception as e:
                    RNS.log(f"Error processing retry id {retry.tag}: {e}", RNS.LOG_ERROR)
                    prune.append(retry)

            with self._lock:
                for retry in prune:
                    RNS.log(f"pruned retry {retry.tag}, retry count {retry.tries}/{retry.try_limit}", RNS.LOG_DEBUG)
                    with exception.permit(SystemExit): self._statuses.remove(retry)

        if self._finished is not None: self._finished.set_result(None)

    def _get_next_tag(self):
        self._tag_counter += 1
        return self._tag_counter

    def has_tag(self, tag: any) -> bool:
        with self._lock: return next(filter(lambda s: s.tag == tag, self._statuses), None) is not None

    def begin(self, try_limit: int, wait_delay: float, try_callback: Callable[[any, int], any],
              timeout_callback: Callable[[any, int], None]) -> any:
        
        RNS.log(f"Running first try", RNS.LOG_DEBUG)
        tag = try_callback(None, 1)
        RNS.log(f"First try got id {tag}", RNS.LOG_DEBUG)
        
        if not tag:
            RNS.log(f"Callback returned None/False/0, considering complete.", RNS.LOG_DEBUG)
            return None
        
        with self._lock:
            if tag is None: tag = self._get_next_tag()
            self.complete(tag)

            self._statuses.append(RetryStatus(tag=tag,
                                              tries=1,
                                              try_limit=try_limit,
                                              wait_delay=wait_delay,
                                              retry_callback=try_callback,
                                              timeout_callback=timeout_callback))
        
        RNS.log(f"Added retry timer for {tag}", RNS.LOG_DEBUG)
        return tag

    def complete(self, tag: any):
        assert tag is not None
        with self._lock:
            status = next(filter(lambda l: l.tag == tag, self._statuses), None)
            if status is not None:
                status.completed = True
                self._statuses.remove(status)
                RNS.log(f"completed {tag}", RNS.LOG_DEBUG)
                return

        RNS.log(f"status not found to complete {tag}", RNS.LOG_DEBUG)

    def complete_all(self):
        with self._lock:
            for status in self._statuses:
                status.completed = True
                RNS.log(f"completed {status.tag}", RNS.LOG_DEBUG)
            
            self._statuses.clear()

    def __exit__(self, __exc_type: typing.Type[BaseException], __exc_value: BaseException,
                 __traceback: types.TracebackType) -> bool:
        self.close()
        return False
