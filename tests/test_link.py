# Tests for RNS.Link

import pytest

from RNS.Link import Link

def test_mtu_bytes():
    data = [
        (0, bytes([0, 0, 0])),
        (5, bytes([0, 0, 5])),
        (256, bytes([0, 1, 0])),
        (65536, bytes([1, 0, 0])),
        (16777215, bytes([255, 255, 255])),
        ]
    for inp, outp in data:
        assert Link.mtu_bytes(inp) == outp, f"Error:{inp} packed wrong"
    pytest.raises(OverflowError, Link.mtu_bytes, -5)  # Out of range
    pytest.raises(OverflowError, Link.mtu_bytes, 20_000_000)  # Out of range
