import hashlib
from math import ceil
from RNS.Cryptography import HMAC

def hkdf(length=None, derive_from=None, salt=None, context=None):
    hash_len = 32

    def hmac_sha256(key, data):
        return HMAC.new(key, data).digest()

    if length == None or length < 1:
        raise ValueError("Invalid output key length")

    if derive_from == "None" or derive_from == "":
        raise ValueError("Cannot derive key from empty input material")

    if salt == None or len(salt) == 0:
        salt = bytes([0] * hash_len)

    if salt == None:
        salt = b""

    if context == None:
        context = b""

    pseudorandom_key = hmac_sha256(salt, derive_from)

    block = b""
    derived = b""

    for i in range(ceil(length / hash_len)):
        block = hmac_sha256(pseudorandom_key, block + context + bytes([i + 1]))
        derived += block

    return derived[:length]