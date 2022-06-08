from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

# These proxy classes exist to create a uniform API accross
# cryptography primitive providers.

class X25519PrivateKeyProxy:
    def __init__(self, real):
        self.real = real

    @classmethod
    def generate(cls):
        return cls(X25519PrivateKey.generate())

    @classmethod
    def from_private_bytes(cls, data):
        return cls(X25519PrivateKey.from_private_bytes(data))

    def private_bytes(self):
        return self.real.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )

    def public_key(self):
        return X25519PublicKeyProxy(self.real.public_key())

    def exchange(self, peer_public_key):
        return self.real.exchange(peer_public_key.real)


class X25519PublicKeyProxy:
    def __init__(self, real):
        self.real = real

    @classmethod
    def from_public_bytes(cls, data):
        return cls(X25519PublicKey.from_public_bytes(data))

    def public_bytes(self):
        return self.real.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )


class Ed25519PrivateKeyProxy:
    def __init__(self, real):
        self.real = real

    @classmethod
    def generate(cls):
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_private_bytes(cls, data):
        return cls(Ed25519PrivateKey.from_private_bytes(data))

    def private_bytes(self):
        return self.real.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

    def public_key(self):
        return Ed25519PublicKeyProxy(self.real.public_key())

    def sign(self, message):
        return self.real.sign(message)


class Ed25519PublicKeyProxy:
    def __init__(self, real):
        self.real = real

    @classmethod
    def from_public_bytes(cls, data):
        return cls(Ed25519PublicKey.from_public_bytes(data))

    def public_bytes(self):
        return self.real.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

    def verify(self, signature, message):
        self.real.verify(signature, message)