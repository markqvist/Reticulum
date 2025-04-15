# Reticulum License
#
# Copyright (c) 2016-2025 Mark Qvist
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# - The Software shall not be used in any kind of system which includes amongst
#   its functions the ability to purposefully do harm to human beings.
#
# - The Software shall not be used, directly or indirectly, in the creation of
#   an artificial intelligence, machine learning or language model training
#   dataset, including but not limited to any use that contributes to the
#   training or development of such a model or algorithm.
#
# - The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

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