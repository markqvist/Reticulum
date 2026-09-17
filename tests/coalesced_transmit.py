# Partially generated with lc/kimi_k2.6
# Reviewed and approved by Mark Qvist
import unittest

import os
import time
import random
import socket
import threading

from RNS.Interfaces.util.TransmitBuffer import TransmitBuffer
from RNS.Interfaces.util.HDLC import HDLC

TARGET     = TransmitBuffer.COALESCE_TARGET
FRAME_SEED = 0x7842AB1E

def framed(payload): return bytes([HDLC.FLAG]) + HDLC.escape(payload) + bytes([HDLC.FLAG])

def unframe(stream):
    frames = []
    fb = stream
    while True:
        frame_start = fb.find(bytes([HDLC.FLAG]))
        if frame_start != -1:
            frame_end = fb.find(bytes([HDLC.FLAG]), frame_start + 1)
            if frame_end != -1:
                frame = fb[frame_start + 1:frame_end]
                frame = frame.replace(bytes([HDLC.ESC, HDLC.FLAG ^ HDLC.ESC_MASK]), bytes([HDLC.FLAG]))
                frame = frame.replace(bytes([HDLC.ESC, HDLC.ESC  ^ HDLC.ESC_MASK]), bytes([HDLC.ESC]))
                if len(frame) > 0:
                    frames.append(bytes(frame))
                fb = fb[frame_end:]
            else: break
        else: break
    return frames

def rng_payload(rng, size):
    raw = bytearray(os.urandom(size))
    if size > 0:
        for off in range(0, size, max(size // 32, 1)):
            raw[off] = 0x7E if (off % 2) else 0x7D
    return bytes(raw)

def assert_accounting(test, tb, expect_len, expect_sendable, expect_frames):
    test.assertEqual(len(tb), expect_len)
    test.assertEqual(tb.sendable, expect_sendable)
    test.assertEqual(tb.frames_buffered, expect_frames)
    test.assertTrue(0 <= tb.sendable <= len(tb))

class TestTransmitBuffer(unittest.TestCase):

    def test_01_empty_state(self):
        print("")
        tb = TransmitBuffer()
        assert_accounting(self, tb, 0, 0, 0)
        self.assertEqual(tb.chunks_buffered, 0)
        self.assertEqual(tb.drain_to(None), 0)  # no chunks -> nothing to do

    # Test that frames appended to an idle queue become sendable
    # at once, so no coalescing latency is incurred for sparse traffic.
    def test_02_sparse_visibility(self):
        print("")
        tb = TransmitBuffer()
        for payload_size in (200, 1024, 16384, 65534):
            tb.append(framed(rng_payload(random.Random(FRAME_SEED), payload_size)))
            self.assertGreater(tb.sendable, 0)
            self.assertGreater(len(tb), 0)

    # Test that small frames coalesce into chunks bounded by
    # the configured coalescing target.
    def test_03_coalescing(self):
        print("")
        tb = TransmitBuffer()
        rng = random.Random(FRAME_SEED)
        payloads = [rng_payload(rng, 200) for _ in range(2000)]
        for p in payloads: tb.append(framed(p))

        self.assertEqual(len(tb), sum(len(framed(p)) for p in payloads))
        self.assertEqual(tb.frames_buffered, len(payloads))
        for chunk, frames in tb._chunks:
            self.assertLessEqual(len(chunk), TARGET)
            self.assertGreater(len(chunk), 0)
            self.assertGreater(frames, 0)

        # Visible accounting must match the chunk queue; buffered accounting
        # must additionally include the producer's in-progress coalescing
        # chunk, which is not visible to the consumer yet.
        in_cur = len(tb._cur) if tb._cur is not None else 0
        in_cur_frames = tb._cur_frames if tb._cur is not None else 0
        visible = sum(len(c) for c, _ in tb._chunks)
        visible_frames = sum(frames for _, frames in tb._chunks)
        self.assertEqual(tb.sendable, visible)
        self.assertEqual(tb.sendable + in_cur, len(tb))
        self.assertEqual(visible_frames + in_cur_frames, len(payloads))
        self.assertEqual(tb.frames_buffered, len(payloads))

    # Test that frames whose on-wire size is at or above the coalescing
    # target are queued as their own chunk. Frames just below must coalesce.
    # Must apply to final, framed and escape on-wire stream.
    def test_04_large_frame_granularity(self):
        print("")
        tb = TransmitBuffer()
        below = bytes([HDLC.FLAG]) + b"A" * (TARGET - 10) + bytes([HDLC.FLAG])
        at    = bytes([HDLC.FLAG]) + b"B" * (TARGET - 2)  + bytes([HDLC.FLAG])
        above = bytes([HDLC.FLAG]) + b"C" * TARGET        + bytes([HDLC.FLAG])
        big   = bytes([HDLC.FLAG]) + b"D" * 262144        + bytes([HDLC.FLAG])

        self.assertLess(len(below), TARGET)
        self.assertEqual(len(at), TARGET)
        self.assertGreater(len(above), TARGET)

        tb.append(below)
        tb.append(at)
        tb.append(above)
        tb.append(big)

        chunks = list(tb._chunks)
        self.assertEqual(len(chunks), 4) # 1 coalesced chunk + 3 own chunks
        self.assertEqual(chunks[0][1], 1)
        self.assertEqual(chunks[0][0], below)
        self.assertEqual(chunks[1][1], 1)
        self.assertEqual(chunks[1][0], at)
        self.assertEqual(chunks[2][1], 1)
        self.assertEqual(chunks[2][0], above)
        self.assertEqual(chunks[3][1], 1)
        self.assertEqual(chunks[3][0], big)
        self.assertEqual(tb.frames_buffered, 4)

    # Test that a partially written head chunk resumes
    # correctly on the next drain.
    def test_05_partial_head_resume(self):
        print("")
        a, b = socket.socketpair()
        a.setblocking(False)
        b.setblocking(False)
        a.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)

        tb = TransmitBuffer()
        rng = random.Random(FRAME_SEED)
        payloads = [rng_payload(rng, 262144) for _ in range(8)]
        frames = [framed(p) for p in payloads]
        for f in frames: tb.append(f)
        expected = b"".join(frames)

        # Drain without any receiver: Small kernel buffer forces partial
        # writes, and the drain must stop gracefully on BlockingIOError.
        written = 0
        w = tb.drain_to(a)
        self.assertGreater(w, 0)
        self.assertLess(w, len(frames[0]))
        written += w
        self.assertLess(tb.sendable, len(expected))
        w = tb.drain_to(a) # window still full, must not raise or corrupt
        self.assertGreaterEqual(w, 0)
        written += w
        self.assertGreaterEqual(len(tb), 0)

        # Drain the kernel side, then run the drain to completion.
        got = bytearray()
        def recv_loop():
            while len(got) < len(expected):
                try: d = b.recv(1 << 20)
                except BlockingIOError:
                    time.sleep(0.001)
                    continue
                if not d:
                    break
                got.extend(d)
        rt = threading.Thread(target=recv_loop, daemon=True)
        rt.start()
        while tb.sendable > 0:
            w = tb.drain_to(a)
            if w == 0: time.sleep(0.001)
        rt.join(timeout=10)
        self.assertFalse(rt.is_alive())
        self.assertEqual(bytes(got), expected)
        assert_accounting(self, tb, 0, 0, 0)
        a.close(); b.close()

    # Test that a full kernel window stops the drain without
    # any exceptions, and that a later drain delivers the rest.
    def test_06_graceful_blocking_io(self):
        print("")
        a, b = socket.socketpair()
        a.setblocking(False)
        b.setblocking(False)
        a.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2048)

        tb = TransmitBuffer()
        rng = random.Random(FRAME_SEED)
        frames = [framed(rng_payload(rng, 200)) for _ in range(100000)]
        for f in frames:
            tb.append(f)
        expected = b"".join(frames)

        # Fill the kernel window. Repeated drains must never raise, and must
        # eventually make no progress while the window is full.
        for _ in range(5_000_000):
            w = tb.drain_to(a)
            if w == 0: break
            if w < 0: self.fail("drain_to returned a negative count")
        self.assertGreater(len(tb), 0)

        # Production for the burst has ended, release the coalescing tail.
        tb.flush()

        got = bytearray()
        def recv_loop():
            while len(got) < len(expected):
                try: d = b.recv(1 << 20)
                except BlockingIOError:
                    time.sleep(0.001)
                    continue
                if not d:
                    break
                got.extend(d)
        rt = threading.Thread(target=recv_loop, daemon=True)
        rt.start()
        while tb.sendable > 0:
            w = tb.drain_to(a)
            if w == 0: time.sleep(0.001)
        rt.join(timeout=10)
        self.assertFalse(rt.is_alive())
        self.assertEqual(bytes(got), expected)
        assert_accounting(self, tb, 0, 0, 0)
        a.close(); b.close()

    # Exactness test of end-to-end, in-order roundtrip delivery.
    def test_07_roundtrip_and_frame_integrity(self):
        print("")
        a, b = socket.socketpair()
        a.setblocking(True)
        b.setblocking(True)

        tb = TransmitBuffer()
        rng = random.Random(FRAME_SEED)
        sizes = [200, 512, 1024, 4096, 8192, 16384, 65534, 65536, 65537, 262144]
        payloads = [rng_payload(rng, size) for size in sizes] * 8
        frames = [framed(p) for p in payloads]
        for f in frames: tb.append(f)
        expected = b"".join(frames)

        # Non-blocking socket, pipelined drain and receive
        a.setblocking(False)
        b.setblocking(False)

        got = bytearray()
        wrote = 0
        deadline = time.time() + 30
        while tb.sendable > 0 or len(got) < len(expected):
            self.assertLess(time.time(), deadline, "test timed out")
            if tb.sendable > 0: wrote += tb.drain_to(a)
            try:
                d = b.recv(1 << 20)
                if d: got.extend(d)
            except BlockingIOError:
                time.sleep(0.0002)

        self.assertEqual(wrote, len(expected))
        assert_accounting(self, tb, 0, 0, 0)
        self.assertEqual(bytes(got), expected)
        self.assertEqual(unframe(bytes(got)), payloads)
        a.close(); b.close()

    # Test that a producer flush makes the in-progress coalescing
    # tail visible, and that the buffer is fully drainable afterwards.
    def test_08_flush_releases_tail(self):
        print("")
        tb = TransmitBuffer()
        rng = random.Random(FRAME_SEED)
        f1 = framed(rng_payload(rng, 200))
        f2 = framed(rng_payload(rng, 200))
        f3 = framed(rng_payload(rng, 200))
        tb.append(f1) # Queue idle -> visible immediately
        tb.append(f2) # Queue busy -> coalesced into tail
        tb.append(f3) # Queue busy -> coalesced into tail

        self.assertEqual(tb.sendable, len(f1))
        self.assertEqual(len(tb), len(f1) + len(f2) + len(f3))
        self.assertEqual(tb.chunks_buffered, 1)

        tb.flush()
        self.assertEqual(tb.sendable, len(f1) + len(f2) + len(f3))
        self.assertEqual(tb.chunks_buffered, 2)
        self.assertEqual(tb.frames_buffered, 3)

    # Ensure frames appended while the queue is busy are not
    # stranded in the coalescing tail.
    def test_09_stranded_tail_delivery(self):
        print("")
        a, b = socket.socketpair()
        a.setblocking(False)
        b.setblocking(False)

        tb = TransmitBuffer()
        rng = random.Random(FRAME_SEED)
        f1 = framed(rng_payload(rng, 200))
        f2 = framed(rng_payload(rng, 200))
        f3 = framed(rng_payload(rng, 200))
        expected = f1 + f2 + f3

        tb.append(f1) # queue idle -> own chunk, visible
        tb.append(f2) # queue busy  -> coalescing tail, invisible
        tb.append(f3) # queue busy  -> coalescing tail, invisible
        self.assertEqual(tb.sendable, len(f1))

        # No further appends. Draining alone without a flush must
        # release and deliver the coalescing tail.
        got = bytearray()
        deadline = time.time() + 10
        while tb.sendable > 0 or len(got) < len(expected):
            self.assertLess(time.time(), deadline, "test timed out")
            tb.drain_to(a)
            try:
                d = b.recv(1 << 20)
                if d: got.extend(d)
            except BlockingIOError:
                time.sleep(0.0002)
        self.assertEqual(bytes(got), expected)
        assert_accounting(self, tb, 0, 0, 0)
        a.close(); b.close()

    # Test that the coalescing tail is released when the queue
    # drains, and that len() is the total buffered and senable
    # is the transmittable part.
    def test_10_sendable_gating(self):
        print("")
        a, b = socket.socketpair()
        a.setblocking(False)
        b.setblocking(False)
        b.settimeout(5.0)

        tb = TransmitBuffer()
        rng = random.Random(FRAME_SEED)
        frames = [framed(rng_payload(rng, 200)) for _ in range(400)]
        expected = b"".join(frames)
        for f in frames:
            tb.append(f)
        self.assertEqual(tb.sendable + (len(tb._cur) if tb._cur is not None else 0), len(tb))

        # Drain to completion. The drain must release the tail by itself.
        got = bytearray()
        deadline = time.time() + 10
        while tb.sendable > 0 or len(got) < len(expected):
            self.assertLess(time.time(), deadline, "test timed out")
            tb.drain_to(a)
            try:
                d = b.recv(1 << 20)
                if d: got.extend(d)
            except BlockingIOError:
                time.sleep(0.0002)
        self.assertEqual(bytes(got), expected)
        assert_accounting(self, tb, 0, 0, 0)
        a.close(); b.close()

    # Exactness test of concurrent producer append while consumer drains.
    def test_11_concurrent_producer_consumer(self):
        print("")
        a, b = socket.socketpair()
        a.setblocking(False)
        b.setblocking(False)
        b.settimeout(5.0)

        tb = TransmitBuffer()
        rng = random.Random(FRAME_SEED)
        sizes = [200, 1024, 8192, 65536, 262144]
        payloads = [rng_payload(rng, rng.choice(sizes)) for _ in range(2500)]
        frames = [framed(p) for p in payloads]
        total = sum(len(f) for f in frames)
        expected = b"".join(frames)

        producer_errors = []
        def producer():
            try:
                for f in frames: tb.append(f)
            except Exception as e:
                producer_errors.append(e)
        pt = threading.Thread(target=producer, daemon=True)
        pt.start()

        got = bytearray()
        def recv_loop():
            while len(got) < total:
                try: d = b.recv(1 << 20)
                except BlockingIOError:
                    time.sleep(0.001)
                    continue
                except socket.timeout: break
                if not d: break
                got.extend(d)
        rt = threading.Thread(target=recv_loop, daemon=True)
        rt.start()

        ct0 = time.perf_counter()
        while pt.is_alive() or tb.sendable > 0:
            tb.drain_to(a)
            time.sleep(0.0002)
        
        # Final drain once the producer has exited.
        w = 1
        while w > 0: w = tb.drain_to(a)
        t_elapsed = time.perf_counter() - ct0

        pt.join(timeout=10)
        self.assertFalse(pt.is_alive())
        self.assertEqual(producer_errors, [])
        # Production for the burst has ended. Release the coalescing tail so
        # every appended byte is transmittable, then drain to completion.
        tb.flush()
        w = 1
        while w > 0: w = tb.drain_to(a)
        rt.join(timeout=10)
        self.assertFalse(rt.is_alive())
        self.assertEqual(len(got), total)
        self.assertEqual(bytes(got), expected)
        assert_accounting(self, tb, 0, 0, 0)
        a.close(); b.close()
        print(f"Concurrent {len(frames)}-frame burst ({total/1e6:.1f} MB) drained in {t_elapsed*1000:.1f} ms")

    # Test small-frame flood and execution time.
    def test_12_small_frame_burst(self):
        print("")
        a, b = socket.socketpair()
        a.setblocking(False)
        b.setblocking(False)

        tb = TransmitBuffer()
        rng = random.Random(FRAME_SEED)
        frames = [framed(rng_payload(rng, 200)) for _ in range(50000)]
        total = sum(len(f) for f in frames)
        expected = b"".join(frames)

        got = bytearray()
        def recv_loop():
            while len(got) < total:
                try: d = b.recv(1 << 20)
                except BlockingIOError:
                    time.sleep(0.001)
                    continue
                if not d: break
                got.extend(d)
        rt = threading.Thread(target=recv_loop, daemon=True)
        rt.start()

        t0 = time.perf_counter()
        for f in frames: tb.append(f)
        tb.flush()
        while tb.sendable > 0: tb.drain_to(a)
        rt.join(timeout=15)
        t_elapsed = time.perf_counter() - t0

        self.assertFalse(rt.is_alive())
        self.assertEqual(len(got), total)
        self.assertEqual(bytes(got), expected)
        assert_accounting(self, tb, 0, 0, 0)
        a.close(); b.close()
        print(f"50k x 200B flood ({total/1e6:.1f} MB) appended+drained in {t_elapsed*1000:.1f} ms")
        self.assertLess(t_elapsed, 10.0)

if __name__ == "__main__": unittest.main(verbosity=2)