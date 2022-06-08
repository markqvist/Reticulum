# MIT License
#
# Copyright (c) 2015 Brian Warner and other contributors

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

from RNS.Cryptography.Hashes import sha512
from .basic import (bytes_to_clamped_scalar,
                    bytes_to_scalar, scalar_to_bytes,
                    bytes_to_element, Base)
import hashlib, binascii

def H(m):
    return sha512(m)

def publickey(seed):
    # turn first half of SHA512(seed) into scalar, then into point
    assert len(seed) == 32
    a = bytes_to_clamped_scalar(H(seed)[:32])
    A = Base.scalarmult(a)
    return A.to_bytes()

def Hint(m):
    h = H(m)
    return int(binascii.hexlify(h[::-1]), 16)

def signature(m,sk,pk):
    assert len(sk) == 32 # seed
    assert len(pk) == 32
    h = H(sk[:32])
    a_bytes, inter = h[:32], h[32:]
    a = bytes_to_clamped_scalar(a_bytes)
    r = Hint(inter + m)
    R = Base.scalarmult(r)
    R_bytes = R.to_bytes()
    S = r + Hint(R_bytes + pk + m) * a
    return R_bytes + scalar_to_bytes(S)

def checkvalid(s, m, pk):
    if len(s) != 64: raise Exception("signature length is wrong")
    if len(pk) != 32: raise Exception("public-key length is wrong")
    R = bytes_to_element(s[:32])
    A = bytes_to_element(pk)
    S = bytes_to_scalar(s[32:])
    h = Hint(s[:32] + pk + m)
    v1 = Base.scalarmult(S)
    v2 = R.add(A.scalarmult(h))
    return v1==v2

# wrappers

import os

def create_signing_key():
    seed = os.urandom(32)
    return seed

def create_verifying_key(signing_key):
    return publickey(signing_key)

def sign(skbytes, msg):
    """Return just the signature, given the message and just the secret
    key."""
    if len(skbytes) != 32:
        raise ValueError("Bad signing key length %d" % len(skbytes))
    vkbytes = create_verifying_key(skbytes)
    sig = signature(msg, skbytes, vkbytes)
    return sig

def verify(vkbytes, sig, msg):
    if len(vkbytes) != 32:
        raise ValueError("Bad verifying key length %d" % len(vkbytes))
    if len(sig) != 64:
        raise ValueError("Bad signature length %d" % len(sig))
    rc = checkvalid(sig, msg, vkbytes)
    if not rc:
        raise ValueError("rc != 0", rc)
    return True
