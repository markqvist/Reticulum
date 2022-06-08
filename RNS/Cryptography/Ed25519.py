import os
from .pure25519 import ed25519_oop as ed25519

class Ed25519PrivateKey:
    def __init__(self, seed):
        self.seed = seed
        self.sk = ed25519.SigningKey(self.seed)
        #self.vk = self.sk.get_verifying_key()

    @classmethod
    def generate(cls):
        return cls.from_private_bytes(os.urandom(32))

    @classmethod
    def from_private_bytes(cls, data):
        return cls(seed=data)

    def private_bytes(self):
        return self.seed

    def public_key(self):
        return Ed25519PublicKey.from_public_bytes(self.sk.vk_s)

    def sign(self, message):
        return self.sk.sign(message)


class Ed25519PublicKey:
    def __init__(self, seed):
        self.seed = seed
        self.vk = ed25519.VerifyingKey(self.seed)

    @classmethod
    def from_public_bytes(cls, data):
        return cls(data)

    def public_bytes(self):
        return self.vk.to_bytes()

    def verify(self, signature, message):
        self.vk.verify(signature, message)
