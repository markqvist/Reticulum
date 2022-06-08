import importlib
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
