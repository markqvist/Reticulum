# Partially generated with lc/kimi_k2.6
# Reviewed and approved by Mark Qvist
import unittest

import os
import time
import random

import RNS
from RNS import Transport

IFAC_TEST_SEED = 0x1FACAD3
IFAC_NETNAME = b"rns-ifac-test-net"


def rand_bytes(rng, length):
    return bytes(rng.randrange(256) for _ in range(length))


class FakeInterface:
    def __init__(self, ifac_size, ifac_key):
        self.ifac_size = ifac_size
        self.ifac_key  = ifac_key
        self.ifac_identity = RNS.Identity.from_bytes(ifac_key)
        self.violations = []

    def ifac_violation(self, description):
        self.violations.append(description)


def make_interface(ifac_size):
    ifac_key = RNS.Cryptography.hkdf(length=64, derive_from=RNS.Identity.full_hash(IFAC_NETNAME),
                                     salt=RNS.Reticulum.IFAC_SALT, context=None)

    return FakeInterface(ifac_size, ifac_key)


def make_plain_packet(rng, size, pattern="random"):
    """Generate a deterministic protocol-realistic packet: a random or
    structured payload with the IFAC flag bit of the first header byte
    clear (as plaintext frames always have)."""
    if pattern == "random":  raw = rand_bytes(rng, size)
    elif pattern == "zeros": raw = bytes(size)
    elif pattern == "ones":  raw = bytes([0xFF]) * size
    elif pattern == "seq":   raw = bytes((i % 256) for i in range(size))
    else: raise ValueError(f"Unknown pattern {pattern}")

    raw = bytearray(raw)
    raw[0] &= 0x7F
    return bytes(raw)


class TestIFAC(unittest.TestCase):

    def test_01_outgoing_parity(self):
        print("")

        rng = random.Random(IFAC_TEST_SEED)

        sizes      = [8, 16, 32, 100, 500, 1064, 4096, 16384]
        ifac_sizes = [1, 8, 16]
        patterns   = ["random", "zeros", "ones", "seq"]

        verified = 0
        for size in sizes:
            for ifac_size in ifac_sizes:
                iface = make_interface(ifac_size)
                for pattern in patterns:
                    raw = make_plain_packet(rng, size, pattern)

                    out_new = Transport.handle_outgoing_ifac(iface, raw)
                    out_leg = Transport.handle_outgoing_ifac_legacy(iface, raw)

                    self.assertEqual(out_new, out_leg)
                    self.assertEqual(len(out_new), size + ifac_size)
                    verified += 1

        for ifac_size in (8, 16):
            iface = make_interface(ifac_size)
            raw = make_plain_packet(rng, 262144, "random")
            out_new = Transport.handle_outgoing_ifac(iface, raw)
            out_leg = Transport.handle_outgoing_ifac_legacy(iface, raw)
            self.assertEqual(out_new, out_leg)
            verified += 1

        print(f"IFAC outgoing parity: {verified} deterministic cases verified")

    def test_02_incoming_parity(self):
        print("")

        rng = random.Random(IFAC_TEST_SEED ^ 0x1FAC)

        sizes      = [8, 16, 32, 100, 500, 1064, 4096, 16384]
        ifac_sizes = [1, 8, 16]
        patterns   = ["random", "zeros", "ones", "seq"]

        verified = 0
        for size in sizes:
            for ifac_size in ifac_sizes:
                iface = make_interface(ifac_size)
                for pattern in patterns:
                    raw = make_plain_packet(rng, size, pattern)
                    frame = Transport.handle_outgoing_ifac(iface, raw)

                    ok_new, out_new = Transport.handle_ifac(frame, iface)
                    ok_leg, out_leg = Transport.handle_ifac_legacy(frame, iface)

                    self.assertTrue(ok_new)
                    self.assertTrue(ok_leg)
                    self.assertEqual(out_new, out_leg)
                    verified += 1

        for ifac_size in (8, 16):
            iface = make_interface(ifac_size)
            raw = make_plain_packet(rng, 262144, "random")
            frame = Transport.handle_outgoing_ifac(iface, raw)
            ok_new, out_new = Transport.handle_ifac(frame, iface)
            ok_leg, out_leg = Transport.handle_ifac_legacy(frame, iface)
            self.assertTrue(ok_new)
            self.assertTrue(ok_leg)
            self.assertEqual(out_new, out_leg)
            verified += 1

        print(f"IFAC incoming parity: {verified} deterministic cases verified")

    def test_03_roundtrip(self):
        print("")

        rng = random.Random(IFAC_TEST_SEED ^ 0x0FAC)

        # All four TX/RX handler combinations must recover the original packet
        combos = [
            (Transport.handle_outgoing_ifac,        Transport.handle_ifac),
            (Transport.handle_outgoing_ifac,        Transport.handle_ifac_legacy),
            (Transport.handle_outgoing_ifac_legacy, Transport.handle_ifac),
            (Transport.handle_outgoing_ifac_legacy, Transport.handle_ifac_legacy),
        ]

        sizes     = [16, 1064, 16384]
        ifac_sizes = [1, 8, 16]

        verified = 0
        for tx, rx in combos:
            for size in sizes:
                for ifac_size in ifac_sizes:
                    iface = make_interface(ifac_size)
                    raw = make_plain_packet(rng, size, "random")

                    frame = tx(iface, raw)
                    ok, out = rx(frame, iface)

                    self.assertTrue(ok)
                    self.assertEqual(out, raw)
                    verified += 1

        print(f"IFAC round-trip: {verified} deterministic TX/RX combinations verified\n All four handler pairings recover the packet exactly.")

    def test_04_invariants(self):
        print("")

        rng = random.Random(IFAC_TEST_SEED ^ 0xCAFE)
        iface = make_interface(16)

        for size in (16, 1064, 16384):
            raw = make_plain_packet(rng, size, "random")

            out_new = Transport.handle_outgoing_ifac(iface, raw)
            out_leg = Transport.handle_outgoing_ifac_legacy(iface, raw)

            # IFAC flag must be set on the masked frame
            self.assertEqual(out_new[0] & 0x80, 0x80)

            # The IFAC tag region must be transmitted in the clear and
            # identical in both implementations
            self.assertEqual(out_new[2:2+iface.ifac_size], out_leg[2:2+iface.ifac_size])
            self.assertEqual(out_new[2:2+iface.ifac_size], iface.ifac_identity.sign(raw)[-iface.ifac_size:])

            # Second header byte must be masked identically
            self.assertEqual(out_new[1], out_leg[1])

            # The incoming handler must clear the IFAC flag in its output
            ok, out = Transport.handle_ifac(out_new, iface)
            self.assertTrue(ok)
            self.assertEqual(out[0] & 0x80, 0)

        print("IFAC invariants: flag set on frame, tag in clear and identical, flag cleared on input recovery")

    def test_05_invalid_tags(self):
        print("")

        rng = random.Random(IFAC_TEST_SEED ^ 0xBAD)

        sizes      = [100, 1064, 16384]
        ifac_sizes = [1, 8, 16]

        for size in sizes:
            for ifac_size in ifac_sizes:
                iface = make_interface(ifac_size)
                raw = make_plain_packet(rng, size, "random")
                frame = bytearray(Transport.handle_outgoing_ifac(iface, raw))

                corruptions = []
                # Corrupt a masked payload byte
                corrupted = bytearray(frame)
                corrupted[-1] ^= 0x01
                corruptions.append(bytes(corrupted))

                # Corrupt the second header byte
                corrupted = bytearray(frame)
                corrupted[1] ^= 0x40
                corruptions.append(bytes(corrupted))

                # Corrupt a byte in the IFAC tag region
                if ifac_size > 0:
                    corrupted = bytearray(frame)
                    corrupted[2 + ifac_size//2] ^= 0x01
                    corruptions.append(bytes(corrupted))

                for corrupted in corruptions:
                    ok_new, out_new = Transport.handle_ifac(corrupted, iface)
                    ok_leg, out_leg = Transport.handle_ifac_legacy(corrupted, iface)

                    # Both implementations must behave identically on any
                    # corrupted frame, including the violation report
                    self.assertEqual(ok_new, ok_leg)
                    self.assertEqual(out_new, out_leg)
                    self.assertEqual(iface.violations[-1:], ["Invalid IFAC on packet"])

                    # With >= 8 bytes of tag entropy, rejection is
                    # deterministic. At ifac_size = 1 the truncated tag has
                    # only 8 bits, so a corrupted frame can statistically
                    # collide with the original truncation (1/256) - both
                    # implementations behave identically either way.
                    if ifac_size >= 8: self.assertFalse(ok_new)

        print("IFAC invalid tags: behaviour and violation reporting identical "
              "between implementations; deterministic rejection verified for "
              "8+ byte tags")

    @unittest.skipIf(os.getenv("RNS_SKIP_PERF_TESTS") != None, "Skipping performance tests")
    def test_06_benchmark(self):
        print("")

        rng = random.Random(IFAC_TEST_SEED ^ 0xBEEF)

        sizes = [1500, 16384, 262144]
        runs  = {1500: 30, 16384: 15, 262144: 5}

        print("IFAC handler benchmark (optimized vs legacy):")
        print(f"{'size':>8} {'out lgc':>11} {'out opt':>11} {'out spd':>8} | "
              f"{'in lgc':>11} {'in new':>11} {'in spd':>8}")
        print("-" * 84)

        total_leg = total_new = 0.0
        for size in sizes:
            iface = make_interface(16)
            raw = make_plain_packet(rng, size, "random")
            frame = Transport.handle_outgoing_ifac(iface, raw)
            n = runs[size]

            # Warmup
            Transport.handle_outgoing_ifac_legacy(iface, raw)
            Transport.handle_outgoing_ifac(iface, raw)
            Transport.handle_ifac_legacy(frame, iface)
            Transport.handle_ifac(frame, iface)

            t0 = time.perf_counter()
            for _ in range(n): Transport.handle_outgoing_ifac_legacy(iface, raw)
            out_leg = (time.perf_counter() - t0) / n

            t0 = time.perf_counter()
            for _ in range(n): Transport.handle_outgoing_ifac(iface, raw)
            out_new = (time.perf_counter() - t0) / n

            t0 = time.perf_counter()
            for _ in range(n): Transport.handle_ifac_legacy(frame, iface)
            in_leg = (time.perf_counter() - t0) / n

            t0 = time.perf_counter()
            for _ in range(n): Transport.handle_ifac(frame, iface)
            in_new = (time.perf_counter() - t0) / n

            total_leg += out_leg + in_leg
            total_new += out_new + in_new

            def ms(t): return f"{t*1000:.3f}m"

            print(f"{size:>8} {ms(out_leg):>11} {ms(out_new):>11} {out_leg/out_new:7.1f}x | "
                  f"{ms(in_leg):>11} {ms(in_new):>11} {in_leg/in_new:7.1f}x")

        print(f"\nCombined TX+RX at {sizes[-1]} bytes: legacy "
              f"{(out_leg+in_leg)*1000:.2f} ms/pkt, optimized {(out_new+in_new)*1000:.2f} ms/pkt, "
              f"{(out_leg+in_leg)/(out_new+in_new):.1f}x speedup")
        print(f"Overall speedup across benchmarks: {total_leg/total_new:.1f}x")
        print()

if __name__ == "__main__":
    unittest.main(verbosity=2)