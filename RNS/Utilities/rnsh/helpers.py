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

import asyncio
import time

def bitwise_or_if(value: int, condition: bool, orval: int):
    if not condition: return value
    return value | orval

def check_and(value: int, andval: int) -> bool:
    return (value & andval) > 0

class SleepRate:
    def __init__(self, target_period: float):
        self.target_period = target_period
        self.last_wake = time.time()

    def next_sleep_time(self) -> float:
        old_last_wake = self.last_wake
        self.last_wake = time.time()
        next_wake = max(old_last_wake + 0.01, self.last_wake)
        sleep_for = next_wake - self.last_wake
        return sleep_for if sleep_for > 0 else 0

    async def sleep_async(self): await asyncio.sleep(self.next_sleep_time())

    def sleep_block(self): time.sleep(self.next_sleep_time())
