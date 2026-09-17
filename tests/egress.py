# Partially generated with lc/kimi_k2.6
# Reviewed and approved by Mark Qvist
import unittest

import time

from RNS.Interfaces.util.TransmitBuffer import TransmitBuffer
from RNS.Interfaces.BackboneInterface import BackboneInterface, BackboneClientInterface

def framed(payload): return b"\x7e" + payload + b"\x7e"

class FakeSock:
    def send(self, data): return len(data)
    def fileno(self): return 999999
    def close(self): return

class FakeIF:
    def __init__(self, tb=None):
        self.transmit_buffer   = tb if tb is not None else TransmitBuffer()
        self._dp_ec_prev_sent  = 0
        self._dp_ec_zero_ticks = 0
        self._dp_ec_last_drain = 10.0
        self.tx_stalled        = False
        self.detached          = False
        self.socket            = FakeSock()
        self.torn_down         = False

    def receive(self, data): self.torn_down = True

class TestHWMLimiter(unittest.TestCase):

    def test_01_hard_valve_bounds_memory(self):
        print("")
        tb = TransmitBuffer()
        limit = 4096
        accepted_count = 0
        total_accepted = 0
        rejected = 0
        for _ in range(200):
            for size in (500, 700):
                frame = framed(b"x" * size)
                accepted = tb.append(frame, limit)
                if accepted:
                    accepted_count += 1
                    total_accepted += len(frame)
                    self.assertLessEqual(len(tb), limit)
                else:
                    rejected += 1
                    # Rejection implies the frame would breach the limit.
                    self.assertGreater(total_accepted + len(frame), limit)

        # The limit must never be exceeded, some frames must have been
        # rejected, and the buffer must still be fully drainable.
        self.assertGreater(rejected, 0)
        self.assertLessEqual(len(tb), limit)
        drained = tb.drain_to(FakeSock())
        self.assertEqual(drained, total_accepted)
        self.assertEqual(len(tb), 0)

    def test_02_oversized_frame_rejected(self):
        print("")
        tb = TransmitBuffer()
        limit = 2048
        self.assertTrue(tb.append(framed(b"x" * 500), limit))
        # A single frame that would exceed the limit is rejected outright,
        # even against an empty buffer.
        self.assertFalse(tb.append(framed(b"x" * 3000), limit))
        self.assertEqual(len(tb), len(framed(b"x" * 500)))
        # The buffer remains fully functional after rejection.
        self.assertTrue(tb.append(framed(b"x" * 1000), limit))
        self.assertEqual(len(tb), len(framed(b"x" * 500)) + len(framed(b"x" * 1000)))
        drained = tb.drain_to(FakeSock())
        self.assertEqual(drained, len(framed(b"x" * 500)) + len(framed(b"x" * 1000)))

    def test_03_valve_accepts_after_drain(self):
        print("")
        tb = TransmitBuffer()
        limit = 2048
        for _ in range(10): self.assertTrue(tb.append(framed(b"x" * 200), limit))
        self.assertEqual(len(tb), len(framed(b"x" * 200)) * 10)
        # Drain most of the buffer; appends are accepted again up to the
        # limit, and the total stays bounded.
        tb.drain_to(FakeSock())
        for _ in range(10): self.assertTrue(tb.append(framed(b"x" * 200), limit))
        self.assertLessEqual(len(tb), limit)

    def test_04_append_without_limit_unbounded(self):
        print("")
        tb = TransmitBuffer()
        for _ in range(100): self.assertTrue(tb.append(framed(b"x" * 200)))
        self.assertEqual(len(tb), len(framed(b"x" * 200)) * 100)

    def test_05_stall_engages_on_zero_drain(self):
        print("")
        tb = TransmitBuffer()
        iface = FakeIF(tb)
        # Fill beyond the mid watermark.
        while len(tb) <= BackboneInterface.DP_EC_MID_WM: tb.append(framed(b"y" * 4096))
        # No drain progress, fewer than STALL_TICKS evaluations must not stall.
        for tick in range(BackboneInterface.DP_EC_STALL_TICKS - 1):
            BackboneInterface._dp_ec_evaluate(iface, 11.0 + tick)
            self.assertFalse(iface.tx_stalled)
        # The STALL_TICKSth zero-drain tick at/above the
        # mid watermark engages the gate.
        BackboneInterface._dp_ec_evaluate(iface, 15.0)
        self.assertTrue(iface.tx_stalled)

    def test_06_stall_releases_below_mid(self):
        print("")
        tb = TransmitBuffer()
        iface = FakeIF(tb)
        while len(tb) <= BackboneInterface.DP_EC_MID_WM: tb.append(framed(b"y" * 4096))
        for t in range(BackboneInterface.DP_EC_STALL_TICKS + 1): BackboneInterface._dp_ec_evaluate(iface, 11.0 + t)
        self.assertTrue(iface.tx_stalled)
        # Drain the buffer completely; the next tick releases the gate.
        tb.drain_to(FakeSock())
        self.assertEqual(len(tb), 0)
        BackboneInterface._dp_ec_evaluate(iface, 20.0)
        self.assertFalse(iface.tx_stalled)
        self.assertEqual(iface._dp_ec_zero_ticks, 0)

    def test_07_stall_engages_on_drain_eta(self):
        print("")
        tb = TransmitBuffer()
        iface = FakeIF(tb)
        while len(tb) <= BackboneInterface.DP_EC_MID_WM: tb.append(framed(b"y" * 4096))
        # Pretend 512 bytes drained since the last tick, the queue would
        # take far longer than DP_EC_MAX_ETA to clear at that rate.
        iface._dp_ec_prev_sent = tb._tx_sent - 512
        BackboneInterface._dp_ec_evaluate(iface, 11.0)
        self.assertTrue(iface.tx_stalled)

    def test_08_stall_hysteresis_no_flap(self):
        print("")
        tb = TransmitBuffer()
        iface = FakeIF(tb)
        while len(tb) <= BackboneInterface.DP_EC_MID_WM: tb.append(framed(b"y" * 4096))

        # Engage the gate with an ETA above max.
        buffered = len(tb)
        iface._dp_ec_prev_sent = tb._tx_sent - 128
        BackboneInterface._dp_ec_evaluate(iface, 11.0)
        self.assertTrue(iface.tx_stalled)

        # A drain ETA between RELEASE and MAX is the hysteresis band,
        # the gate must stay engaged without flapping.
        mid_eta = (BackboneInterface.DP_EC_MAX_ETA + BackboneInterface.DP_EC_RELEASE_ETA) / 2
        mid_drain = buffered / mid_eta
        iface._dp_ec_prev_sent = tb._tx_sent - mid_drain
        BackboneInterface._dp_ec_evaluate(iface, 12.0)
        self.assertTrue(iface.tx_stalled)

        # Only when drainage clears the queue well within the release
        # ETA is the gate released.
        fast_drain = buffered / (BackboneInterface.DP_EC_RELEASE_ETA / 2)
        iface._dp_ec_prev_sent = tb._tx_sent - fast_drain
        BackboneInterface._dp_ec_evaluate(iface, 13.0)
        self.assertFalse(iface.tx_stalled)

    def test_09_sendable_zero_no_stall(self):
        print("")
        tb = TransmitBuffer()
        iface = FakeIF(tb)
        while len(tb) <= BackboneInterface.DP_EC_MID_WM: tb.append(framed(b"y" * 4096))
        # A tick with nothing sendable. All data still unsent but none in
        # the drainer's visible set is impossible with a full buffer, so
        # simulate the empty state instead. An empty buffer must reset
        # stall state and the dead-drain clock.
        tb.drain_to(FakeSock())
        BackboneInterface._dp_ec_evaluate(iface, 11.0)
        self.assertFalse(iface.tx_stalled)
        self.assertEqual(iface._dp_ec_last_drain, 11.0)

    def test_10_dead_peer_escalation(self):
        print("")
        tb = TransmitBuffer()
        iface = FakeIF(tb)
        while len(tb) <= BackboneInterface.DP_EC_MID_WM: tb.append(framed(b"y" * 4096))
        # Last drain progress a long time ago, no drain since.
        iface._dp_ec_last_drain = 10.0
        iface._dp_ec_zero_ticks = BackboneInterface.DP_EC_STALL_TICKS
        escalated = BackboneInterface._dp_ec_evaluate(iface, 100.0)
        self.assertTrue(escalated)
        self.assertTrue(iface.torn_down)

    def test_11_process_outgoing_gate(self):
        print("")
        # Construct a shell client interface object without full
        # initialisation. Process_outgoing only requires the
        # egress-control state and the transmit buffer gating.
        iface = object.__new__(BackboneClientInterface)
        iface.online = True
        iface.detached = False
        iface.tx_stalled = True
        iface.tx_hwm = 1024
        iface.tx_drops = 0
        iface.tx_dropped_bytes = 0
        iface.transmit_buffer = TransmitBuffer()
        iface.socket = None

        iface.process_outgoing(b"gated-frame")
        self.assertEqual(iface.tx_drops, 1)
        self.assertEqual(iface.tx_dropped_bytes, len(framed(b"gated-frame")))
        self.assertEqual(len(iface.transmit_buffer), 0)

if __name__ == "__main__": unittest.main(verbosity=2)