import hashlib

"""
The SHA primitives are abstracted here to allow platform-
aware hardware acceleration in the future. Currently only
uses Python's internal SHA-256 implementation. All SHA-256
calls in RNS end up here.
"""

def sha256(data):
    digest = hashlib.sha256()
    digest.update(data)

    return digest.digest()

def sha512(data):
    digest = hashlib.sha512()
    digest.update(data)

    return digest.digest()
