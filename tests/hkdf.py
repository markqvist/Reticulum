# Partially generated with lc/kimi_k2.6
# Reviewed and approved by Mark Qvist
import unittest

import os
import time
import random

import RNS
from RNS.Cryptography import hkdf
from RNS.Cryptography.HKDF import hkdf_legacy

HKDF_TEST_SEED = 0x5EE5FAC

# RFC 5869 test vectors HKDF SHA-256 vectors
RFC5869_CASES = [
    # A.1: basic test case
    (
        bytes([0x0b]) * 22,
        bytes(range(0x00, 0x0d)),
        bytes(range(0xf0, 0xfa)),
        42,
        "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865",
    ),
    # A.2: longer inputs/outputs
    (
        bytes(range(0x00, 0x50)),
        bytes(range(0x60, 0xb0)),
        bytes(range(0xb0, 0x100)),
        82,
        "b11e398dc80327a1c8e7f78c596a49344f012eda2d4efad8a050cc4c19afa97c"
        "59045a99cac7827271cb41c65e590e09da3275600c2f09b8367793a9aca3db71"
        "cc30c58179ec3e87c14c01d5c1f3434f1d87",
    ),
    # A.3: zero-length salt/info
    (
        bytes([0x0b]) * 22,
        b"",
        b"",
        42,
        "8da4e775a563c18f715f802a063c5a31b8a11f5c5ee1879ec3454e5f3c738d2d9d201395faa4b61a96c8",
    ),
]


def rand_bytes(rng, length):
    return bytes(rng.randrange(256) for _ in range(length))


class TestHKDF(unittest.TestCase):

    def test_01_rfc5869_vectors(self):
        print("")

        for index, (ikm, salt, info, length, expected_hex) in enumerate(RFC5869_CASES):
            expected = bytes.fromhex(expected_hex)

            new_out = hkdf(length=length, derive_from=ikm, salt=salt, context=info)
            leg_out = hkdf_legacy(length=length, derive_from=ikm, salt=salt, context=info)

            self.assertEqual(new_out, expected)
            self.assertEqual(leg_out, expected)

            print(f"RFC 5869 test case {index+1}: OK (optimized = legacy = reference, {len(expected)} bytes)")

    def test_02_parity_matrix(self):
        print("")

        rng = random.Random(HKDF_TEST_SEED)

        # Core lengths: block boundaries, block+1, counter wrap at
        # 256 blocks (8192 bytes), +1/-1 around it, and medium sizes.
        lengths_core = [ 1, 2, 31, 32, 33, 63, 64, 65, 96, 127, 128, 129,
                         255, 256, 257, 511, 512, 513, 1024, 4096, 8191, 8192, 8193 ]
        # Large lengths: exercised with a reduced combination set.
        lengths_large = [16384, 65536, 262144]

        derive_lens        = [1, 7, 16, 32, 64]
        salt_lens          = [None, 0, 1, 16, 32, 64, 100]
        context_lens       = [None, 0, 1, 16, 64, 128]
        derive_lens_large  = [16, 64]
        salt_lens_large    = [None, 32, 100]
        context_lens_large = [None, 16, 128]

        verified = 0
        for length in lengths_core:
            for dlen in derive_lens:
                for slen in salt_lens:
                    for clen in context_lens:
                        derive_from = rand_bytes(rng, dlen)
                        salt        = None if slen is None else (b"" if slen == 0 else rand_bytes(rng, slen))
                        context     = None if clen is None else (b"" if clen == 0 else rand_bytes(rng, clen))

                        new_out = hkdf(length=length, derive_from=derive_from, salt=salt, context=context)
                        leg_out = hkdf_legacy(length=length, derive_from=derive_from, salt=salt, context=context)

                        self.assertEqual(new_out, leg_out)
                        verified += 1

        for length in lengths_large:
            for dlen in derive_lens_large:
                for slen in salt_lens_large:
                    for clen in context_lens_large:
                        derive_from = rand_bytes(rng, dlen)
                        salt        = None if slen is None else (b"" if slen == 0 else rand_bytes(rng, slen))
                        context     = None if clen is None else (b"" if clen == 0 else rand_bytes(rng, clen))

                        new_out = hkdf(length=length, derive_from=derive_from, salt=salt, context=context)
                        leg_out = hkdf_legacy(length=length, derive_from=derive_from, salt=salt, context=context)

                        self.assertEqual(new_out, leg_out)
                        verified += 1

        print(f"HKDF parity matrix: {verified} deterministic cases verified (optimized == legacy)")

    def test_03_error_parity(self):
        print("")

        invalid_cases = [
            dict(length=0, derive_from=b"x"),
            dict(length=None, derive_from=b"x"),
            dict(length=-1, derive_from=b"x"),
            dict(length="x", derive_from=b"x"),
            dict(length=32, derive_from=""),
            dict(length=32, derive_from=None),
        ]

        def raised_exception(fn, kwargs):
            try:
                fn(**kwargs)
                return None
            except Exception as e: return (type(e).__name__, str(e))

        for kwargs in invalid_cases:
            new_exc = raised_exception(hkdf, kwargs)
            leg_exc = raised_exception(hkdf_legacy, kwargs)

            # Both implementations must raise the exact same exception
            # type with the exact same message on invalid arguments
            self.assertIsNotNone(new_exc)
            self.assertEqual(new_exc, leg_exc)

        print(f"HKDF error parity: {len(invalid_cases)} invalid-argument cases raise identical exception types and messages")

    @unittest.skipIf(os.getenv("RNS_SKIP_PERF_TESTS") != None, "Skipping performance tests")
    def test_04_benchmark(self):
        print("")

        rng = random.Random(HKDF_TEST_SEED ^ 0xA11CE)
        salt = RNS.Reticulum.IFAC_SALT

        sizes = [1500, 16384, 262144]
        runs  = {1500: 40, 16384: 20, 262144: 8}

        print("HKDF implementation benchmark (optimized vs legacy):")
        print(f"{'length':>9} {'legacy avg':>12} {'opt avg':>9} {'speedup':>10}")
        print("-" * 48)

        leg_total = new_total = 0.0
        for size in sizes:
            derive_from = rand_bytes(rng, 16)
            context     = rand_bytes(rng, 7)
            n = runs[size]

            hkdf_legacy(length=size, derive_from=derive_from, salt=salt, context=context)
            hkdf(length=size, derive_from=derive_from, salt=salt, context=context)

            t0 = time.perf_counter()
            for _ in range(n):
                hkdf_legacy(length=size, derive_from=derive_from, salt=salt, context=context)
            leg_avg = (time.perf_counter() - t0) / n

            t0 = time.perf_counter()
            for _ in range(n):
                hkdf(length=size, derive_from=derive_from, salt=salt, context=context)
            new_avg = (time.perf_counter() - t0) / n

            leg_total += leg_avg
            new_total += new_avg

            print(f"{size:>9} {leg_avg*1000:9.3f}m {new_avg*1000:9.3f}m {leg_avg/new_avg:8.1f}x")

        print(f"\nThroughput at {sizes[-1]} bytes: legacy {sizes[-1]/leg_avg/1e6*8:.2f} Mbps, "
              f"new {sizes[-1]/new_avg/1e6*8:.2f} Mbps")
        print(f"Overall speedup across benchmarks: {leg_total/new_total:.1f}x")
        print()


if __name__ == "__main__":
    unittest.main(verbosity=2)
