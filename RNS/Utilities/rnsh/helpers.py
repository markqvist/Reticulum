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
