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

import os
import base64
from . import _ed25519
BadSignatureError = _ed25519.BadSignatureError

def create_keypair(entropy=os.urandom):
    SEEDLEN = int(_ed25519.SECRETKEYBYTES/2)
    assert SEEDLEN == 32
    seed = entropy(SEEDLEN)
    sk = SigningKey(seed)
    vk = sk.get_verifying_key()
    return sk, vk

class BadPrefixError(Exception):
    pass

def remove_prefix(s_bytes, prefix):
    assert(type(s_bytes) == type(prefix))
    if s_bytes[:len(prefix)] != prefix:
        raise BadPrefixError("did not see expected '%s' prefix" % (prefix,))
    return s_bytes[len(prefix):]

def to_ascii(s_bytes, prefix="", encoding="base64"):
    """Return a version-prefixed ASCII representation of the given binary
    string. 'encoding' indicates how to do the encoding, and can be one of:
     * base64
     * base32
     * base16 (or hex)

    This function handles bytes, not bits, so it does not append any trailing
    '=' (unlike standard base64.b64encode). It also lowercases the base32
    output.

    'prefix' will be prepended to the encoded form, and is useful for
    distinguishing the purpose and version of the binary string. E.g. you
    could prepend 'pub0-' to a VerifyingKey string to allow the receiving
    code to raise a useful error if someone pasted in a signature string by
    mistake.
    """
    assert isinstance(s_bytes, bytes)
    if not isinstance(prefix, bytes):
        prefix = prefix.encode('ascii')
    if encoding == "base64":
        s_ascii = base64.b64encode(s_bytes).decode('ascii').rstrip("=")
    elif encoding == "base32":
        s_ascii = base64.b32encode(s_bytes).decode('ascii').rstrip("=").lower()
    elif encoding in ("base16", "hex"):
        s_ascii = base64.b16encode(s_bytes).decode('ascii').lower()
    else:
        raise NotImplementedError
    return prefix+s_ascii.encode('ascii')

def from_ascii(s_ascii, prefix="", encoding="base64"):
    """This is the opposite of to_ascii. It will throw BadPrefixError if
    the prefix is not found.
    """
    if isinstance(s_ascii, bytes):
        s_ascii = s_ascii.decode('ascii')
    if isinstance(prefix, bytes):
        prefix = prefix.decode('ascii')
    s_ascii = remove_prefix(s_ascii.strip(), prefix)
    if encoding == "base64":
        s_ascii += "="*((4 - len(s_ascii)%4)%4)
        s_bytes = base64.b64decode(s_ascii)
    elif encoding == "base32":
        s_ascii += "="*((8 - len(s_ascii)%8)%8)
        s_bytes = base64.b32decode(s_ascii.upper())
    elif encoding in ("base16", "hex"):
        s_bytes = base64.b16decode(s_ascii.upper())
    else:
        raise NotImplementedError
    return s_bytes

class SigningKey(object):
    # this can only be used to reconstruct a key created by create_keypair().
    def __init__(self, sk_s, prefix="", encoding=None):
        assert isinstance(sk_s, bytes)
        if not isinstance(prefix, bytes):
            prefix = prefix.encode('ascii')
        sk_s = remove_prefix(sk_s, prefix)
        if encoding is not None:
            sk_s = from_ascii(sk_s, encoding=encoding)
        if len(sk_s) == 32:
            # create from seed
            vk_s, sk_s = _ed25519.publickey(sk_s)
        else:
            if len(sk_s) != 32+32:
                raise ValueError("SigningKey takes 32-byte seed or 64-byte string")
        self.sk_s = sk_s # seed+pubkey
        self.vk_s = sk_s[32:] # just pubkey

    def to_bytes(self, prefix=""):
        if not isinstance(prefix, bytes):
            prefix = prefix.encode('ascii')
        return prefix+self.sk_s

    def to_ascii(self, prefix="", encoding=None):
        assert encoding
        if not isinstance(prefix, bytes):
            prefix = prefix.encode('ascii')
        return to_ascii(self.to_seed(), prefix, encoding)

    def to_seed(self, prefix=""):
        if not isinstance(prefix, bytes):
            prefix = prefix.encode('ascii')
        return prefix+self.sk_s[:32]

    def __eq__(self, them):
        if not isinstance(them, object): return False
        return (them.__class__ == self.__class__
                and them.sk_s == self.sk_s)

    def get_verifying_key(self):
        return VerifyingKey(self.vk_s)

    def sign(self, msg, prefix="", encoding=None):
        assert isinstance(msg, bytes)
        if not isinstance(prefix, bytes):
            prefix = prefix.encode('ascii')
        sig_and_msg = _ed25519.sign(msg, self.sk_s)
        # the response is R+S+msg
        sig_R = sig_and_msg[0:32]
        sig_S = sig_and_msg[32:64]
        msg_out = sig_and_msg[64:]
        sig_out = sig_R + sig_S
        assert msg_out == msg
        if encoding:
            return to_ascii(sig_out, prefix, encoding)
        return prefix+sig_out

class VerifyingKey(object):
    def __init__(self, vk_s, prefix="", encoding=None):
        if not isinstance(prefix, bytes):
            prefix = prefix.encode('ascii')
        if not isinstance(vk_s, bytes):
            vk_s = vk_s.encode('ascii')
        assert isinstance(vk_s, bytes)
        vk_s = remove_prefix(vk_s, prefix)
        if encoding is not None:
            vk_s = from_ascii(vk_s, encoding=encoding)

        assert len(vk_s) == 32
        self.vk_s = vk_s

    def to_bytes(self, prefix=""):
        if not isinstance(prefix, bytes):
            prefix = prefix.encode('ascii')
        return prefix+self.vk_s

    def to_ascii(self, prefix="", encoding=None):
        assert encoding
        if not isinstance(prefix, bytes):
            prefix = prefix.encode('ascii')
        return to_ascii(self.vk_s, prefix, encoding)

    def __eq__(self, them):
        if not isinstance(them, object): return False
        return (them.__class__ == self.__class__
                and them.vk_s == self.vk_s)

    def verify(self, sig, msg, prefix="", encoding=None):
        if not isinstance(sig, bytes):
            sig = sig.encode('ascii')
        if not isinstance(prefix, bytes):
            prefix = prefix.encode('ascii')
        assert isinstance(sig, bytes)
        assert isinstance(msg, bytes)
        if encoding:
            sig = from_ascii(sig, prefix, encoding)
        else:
            sig = remove_prefix(sig, prefix)
        assert len(sig) == 64
        sig_R = sig[:32]
        sig_S = sig[32:]
        sig_and_msg = sig_R + sig_S + msg
        # this might raise BadSignatureError
        msg2 = _ed25519.open(sig_and_msg, self.vk_s)
        assert msg2 == msg

def selftest():
    message = b"crypto libraries should always test themselves at powerup"
    sk = SigningKey(b"priv0-VIsfn5OFGa09Un2MR6Hm7BQ5++xhcQskU2OGXG8jSJl4cWLZrRrVcSN2gVYMGtZT+3354J5jfmqAcuRSD9KIyg",
                    prefix="priv0-", encoding="base64")
    vk = VerifyingKey(b"pub0-eHFi2a0a1XEjdoFWDBrWU/t9+eCeY35qgHLkUg/SiMo",
                      prefix="pub0-", encoding="base64")
    assert sk.get_verifying_key() == vk
    sig = sk.sign(message, prefix="sig0-", encoding="base64")
    assert sig == b"sig0-E/QrwtSF52x8+q0l4ahA7eJbRKc777ClKNg217Q0z4fiYMCdmAOI+rTLVkiFhX6k3D+wQQfKdJYMxaTUFfv1DQ", sig
    vk.verify(sig, message, prefix="sig0-", encoding="base64")

selftest()
