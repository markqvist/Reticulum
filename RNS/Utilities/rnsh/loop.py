import asyncio
import functools
from typing import Callable

def sig_handler_sys_to_loop(handler: Callable[[int, any], None]) -> Callable[[int, asyncio.AbstractEventLoop], None]:
    def wrapped(cb: Callable[[int, any], None], signal: int, loop: asyncio.AbstractEventLoop): cb(signal, None)
    return functools.partial(wrapped, handler)

def loop_set_signal(sig, handler: Callable[[int, asyncio.AbstractEventLoop], None], loop: asyncio.AbstractEventLoop = None):
    if loop is None: loop = asyncio.get_running_loop()
    loop.remove_signal_handler(sig)
    loop.add_signal_handler(sig, functools.partial(handler, sig, loop))