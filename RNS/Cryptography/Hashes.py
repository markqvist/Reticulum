import hashlib


def sha256(data):
    """
    The SHA-256 primitive is abstracted here to allow platform-
    aware hardware acceleration in the future. Currently only
    uses Python's internal SHA-256 implementation. All SHA-256
    calls in RNS end up here.
    """
    digest = hashlib.sha256()
    digest.update(data)

    return digest.digest()