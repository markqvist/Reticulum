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
