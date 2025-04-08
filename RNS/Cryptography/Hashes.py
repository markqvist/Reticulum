# MIT License
#
# Copyright (c) 2022-2025 Mark Qvist / unsigned.io
#
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

import importlib.util
if importlib.util.find_spec('hashlib') != None:
    import hashlib
else:
    hashlib = None

if hasattr(hashlib, "sha512"):
    from hashlib import sha512 as ext_sha512
else:
    from .SHA512 import sha512 as ext_sha512

if hasattr(hashlib, "sha256"):
    from hashlib import sha256 as ext_sha256
else:
    from .SHA256 import sha256 as ext_sha256

"""
The SHA primitives are abstracted here to allow platform-
aware hardware acceleration in the future. Currently only
uses Python's internal SHA-256 implementation. All SHA-256
calls in RNS end up here.
"""

def sha256(data):
    digest = ext_sha256()
    digest.update(data)

    return digest.digest()

def sha512(data):
    digest = ext_sha512()
    digest.update(data)

    return digest.digest()
