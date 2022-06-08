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

from . import eddsa

class BadSignatureError(Exception):
    pass

SECRETKEYBYTES = 64
PUBLICKEYBYTES = 32
SIGNATUREKEYBYTES = 64

def publickey(seed32):
    assert len(seed32) == 32
    vk32 = eddsa.publickey(seed32)
    return vk32, seed32+vk32

def sign(msg, skvk):
    assert len(skvk) == 64
    sk = skvk[:32]
    vk = skvk[32:]
    sig = eddsa.signature(msg, sk, vk)
    return sig+msg

def open(sigmsg, vk):
    assert len(vk) == 32
    sig = sigmsg[:64]
    msg = sigmsg[64:]
    try:
        valid = eddsa.checkvalid(sig, msg, vk)
    except ValueError as e:
        raise BadSignatureError(e)
    except Exception as e:
        if str(e) == "decoding point that is not on curve":
            raise BadSignatureError(e)
        raise
    if not valid:
        raise BadSignatureError()
    return msg