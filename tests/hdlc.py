# Partially generated with lc/kimi_k2.6
# Reviewed and approved by Mark Qvist
import unittest

import os
import time
import random

from RNS.Interfaces.util.HDLC import HDLC, ReceiveBuffer

SEED    = 0x52EC0FF
MIN_LEN = 19 # HEADER_MINSIZE
MTU     = 1048576

def framed(payload): return HDLC.FLAG_B + HDLC.escape(payload) + HDLC.FLAG_B

def rand_payload(rng, size):
    p = bytearray(os.urandom(size))
    for off in range(0, max(size, 1), max(size // 16, 1)):
        p[off] = 0x7E if (off % 2) else 0x7D
    return bytes(p)

# Original, pre-refactor HDLC handler algorithm
def legacy_feed(state, data, mtu, min_len, max_len):
    if len(data) > 0:
        state["buf"] += data
        flags_remaining = True
        while flags_remaining:
            frame_start = state["buf"].find(HDLC.FLAG)
            if frame_start != -1:
                frame_end = state["buf"].find(HDLC.FLAG, frame_start+1)
                if frame_end != -1:
                    frame = state["buf"][frame_start+1:frame_end]
                    frame = frame.replace(bytes([HDLC.ESC, HDLC.FLAG ^ HDLC.ESC_MASK]), bytes([HDLC.FLAG]))
                    frame = frame.replace(bytes([HDLC.ESC, HDLC.ESC  ^ HDLC.ESC_MASK]), bytes([HDLC.ESC]))
                    frame_len = len(frame)
                    if frame_len != 0:
                        if check_frame_len(frame_len, min_len, max_len): state["frames"].append(frame)
                        else:                                            state["invalids"].append(frame_len)

                    state["buf"] = state["buf"][frame_end:]

                else:
                    if len(state["buf"]) > mtu*2: state["buf"] = b""
                    flags_remaining = False
            else:
                state["buf"] = b""
                flags_remaining = False

def check_frame_len(frame_len, min_len, max_len):
    if   frame_len <= min_len: return False
    elif max_len == None:      return True
    elif frame_len >  max_len: return False
    else:                      return True

class Harness:
    def __init__(self, mtu=MTU, min_len=MIN_LEN, max_len=None, track_invalid=True):
        self.frames = []
        self.invalids = []
        self.rb = ReceiveBuffer(mtu, min_len, max_len, on_frame=self.frames.append,
                                on_invalid=self.invalids.append if track_invalid else None)
    def unconsumed(self):
        return bytes(self.rb._buf[self.rb._off:])

class TestReceiveBuffer(unittest.TestCase):
    # Legacy parity, also checks that the closing flag of
    # the last consumed frame is retained as the start
    # marker for the next unframing.
    def test_01_single_frame_roundtrip(self):
        print("")
        rng = random.Random(SEED)
        for size in (20, 200, 4096, 262144):
            p = rand_payload(rng, size)
            h = Harness()
            h.rb.feed(framed(p))
            self.assertEqual(h.frames, [p])
            self.assertEqual(h.invalids, [])
            self.assertEqual(h.unconsumed(), HDLC.FLAG_B)
            self.assertEqual(len(h.rb), 1)

    # Test frames split across arbitrary feed boundaries
    def test_02_split_chunks_straddle(self):
        print("")
        rng = random.Random(SEED)
        payloads = [rand_payload(rng, rng.choice((20, 200, 1024, 16384))) for _ in range(200)]
        stream = b"".join(framed(p) for p in payloads)

        h = Harness()
        # One-byte-per-feed pathological case
        for byte in stream: h.rb.feed(bytes([byte]))

        self.assertEqual(h.frames, payloads)
        self.assertEqual(len(h.rb), 1) # trailing flag

    # Test exactness of escape-heavy payloads
    def test_03_escape_roundtrip(self):
        print("")
        rng = random.Random(SEED ^ 0xE5C)
        payloads = []
        for _ in range(100):
            size = rng.choice((64, 512, 8192))
            p = bytearray(os.urandom(size))
            # Dense 0x7E/0x7D injection
            for i in range(0, size, 3): p[i] = 0x7E if (i % 2) else 0x7D
            payloads.append(bytes(p))

        h = Harness()
        for p in payloads: h.rb.feed(framed(p))
        self.assertEqual(h.frames, payloads)

    # Empty frames must skip silently
    def test_04_consecutive_flags_skipped(self):
        print("")
        rng = random.Random(SEED)
        p1 = rand_payload(rng, 100)
        p2 = rand_payload(rng, 100)
        h = Harness()
        h.rb.feed(framed(p1) + HDLC.FLAG_B + HDLC.FLAG_B + framed(p2))
        self.assertEqual(h.frames, [p1, p2])
        self.assertEqual(h.invalids, [])

    # Test that invalid sized frames report correctly
    def test_05_size_range(self):
        print("")
        h = Harness(min_len=19, max_len=100)
        h.rb.feed(framed(b"x" * 5))   # frame len 5   -> too short
        h.rb.feed(framed(b"x" * 19))  # frame len 19  -> not > 19, which is bad
        h.rb.feed(framed(b"x" * 100)) # frame len 100 -> within range
        h.rb.feed(framed(b"x" * 101)) # frame len 101 -> too long
        self.assertEqual(h.frames, [b"x" * 100])
        self.assertEqual(h.invalids, [5, 19, 101])

        # Without an on_invalid hook, out-of-range frames are dropped
        h2 = Harness(min_len=19, max_len=100, track_invalid=False)
        h2.rb.feed(framed(b"x" * 5))
        h2.rb.feed(framed(b"x" * 50))
        h2.rb.feed(framed(b"x" * 101))
        self.assertEqual(h2.frames, [b"x" * 50])
        self.assertEqual(h2.invalids, [])

    # A flag without a closing flag is retained up to the
    # overflow bound, beyond which the buffer must reset
    def test_06_partial_and_overflow_reset(self):
        print("")
        h = Harness(mtu=1024)
        # Partial frame within bound must retained
        h.rb.feed(b"\x7e" + b"Y" * 100)
        self.assertEqual(len(h.rb), 101)
        self.assertEqual(h.frames, [])
        # ... and completing it delivers the frame
        h.rb.feed(b"Z" * 40 + b"\x7e")
        self.assertEqual(h.frames, [b"Y" * 100 + b"Z" * 40])
        self.assertEqual(len(h.rb), 1)

        # Partial frame past the overflow bound must drop and reset
        h2 = Harness(mtu=1024)
        h2.rb.feed(b"\x7e" + b"Y" * 5000)
        self.assertEqual(len(h2.rb), 0)
        # Buffer must be usable after the reset
        h2.rb.feed(framed(b"x" * 100))
        self.assertEqual(h2.frames, [b"x" * 100])

    # Test that input without any flag is discarded immediately
    def test_07_garbage_reset(self):
        print("")
        h = Harness()
        h.rb.feed(b"\x00" * 100000 + b"\x01" * 100000)
        self.assertEqual(len(h.rb), 0)
        self.assertEqual(h.frames, [])
        h.rb.feed(framed(b"x" * 100))
        self.assertEqual(h.frames, [b"x" * 100])

    # Random stream parity checks
    def test_08_parity_random_streams(self):
        print("")
        rng = random.Random(SEED)
        verified = 0

        def inert(size): return bytes(rng.randrange(1, 0x7D) for _ in range(size))

        for round in range(20):
            stream = bytearray()
            intended = []
            for _ in range(rng.randrange(5, 60)):
                kind = rng.randrange(5)
                if   kind == 0: stream += inert(rng.randrange(40, 300))           # Garbage
                elif kind == 1: stream += b"\x7e" + inert(rng.randrange(50, 400)) # Unclosed partial
                else:
                    p = rand_payload(rng, rng.randrange(20, 8192))
                    intended.append(p)
                    stream += framed(p)

            legacy = {"buf": b"", "frames": [], "invalids": []}
            mine = Harness()
            pos = 0
            while pos < len(stream):
                step = rng.randrange(1, 4096)
                chunk = bytes(stream[pos:pos + step])
                pos += step
                legacy_feed(legacy, chunk, MTU, MIN_LEN, None)
                mine.rb.feed(chunk)
                # Behavioural and internal-state parity after every chunk
                self.assertEqual(mine.frames, legacy["frames"])
                self.assertEqual(mine.invalids, legacy["invalids"])
                self.assertEqual(mine.unconsumed(), legacy["buf"])

            # Full-stream parity and intended-payload presence.
            self.assertEqual(mine.frames, legacy["frames"])
            self.assertEqual(mine.unconsumed(), legacy["buf"])
            for p in intended: self.assertGreaterEqual(mine.frames.count(p), intended.count(p))
            verified += 1

        print(f"  Random-stream parity: {verified} streams verified")

    # Small-frame flood parity
    def test_09_parity_flood(self):
        print("")
        rng = random.Random(SEED)
        payloads = [rand_payload(rng, 200) for _ in range(20000)]
        stream = b"".join(framed(p) for p in payloads)

        legacy = {"buf": b"", "frames": [], "invalids": []}
        mine = Harness()
        t0 = time.perf_counter()
        for i in range(0, len(stream), MTU):
            chunk = stream[i:i + MTU]
            legacy_feed(legacy, chunk, MTU, MIN_LEN, None)
            mine.rb.feed(chunk)
        t_elapsed = time.perf_counter() - t0

        self.assertEqual(mine.frames, legacy["frames"])
        self.assertEqual(mine.frames, payloads)
        self.assertEqual(mine.unconsumed(), legacy["buf"])
        self.assertLess(t_elapsed, 10.0)
        print(f"  20k x 200B flood ({len(stream)/1e6:.1f} MB) parity-verified in {t_elapsed*1000:.1f} ms")

    # Large frames in small chunks
    def test_10_parity_large_frames(self):
        print("")
        rng = random.Random(SEED ^ 0x1AF)
        payloads = [rand_payload(rng, 262144) for _ in range(8)]
        stream = b"".join(framed(p) for p in payloads)

        legacy = {"buf": b"", "frames": [], "invalids": []}
        mine = Harness(mtu=262144)
        pos = 0
        while pos < len(stream):
            chunk = stream[pos:pos + 4096]
            pos += 4096
            legacy_feed(legacy, chunk, 262144, MIN_LEN, None)
            mine.rb.feed(chunk)
            self.assertEqual(mine.frames, legacy["frames"])
            self.assertEqual(mine.unconsumed(), legacy["buf"])
        self.assertEqual(mine.frames, payloads)

    # After a burst is fully consumed, the internal buffer must be compacted
    def test_11_len_and_compaction(self):
        print("")
        rng = random.Random(SEED)
        h = Harness()
        for _ in range(1000):
            h.rb.feed(framed(rand_payload(rng, 200)))
        self.assertEqual(len(h.rb), 1)      # Trailing flag marker
        self.assertEqual(len(h.rb._buf), 1) # Fully compacted
        self.assertEqual(h.rb._off, 0)
        self.assertEqual(len(h.frames), 1000)

if __name__ == "__main__": unittest.main(verbosity=2)