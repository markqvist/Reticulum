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

import RNS.Cryptography.Provider as cp
import RNS.vendor.platformutils as pu

if cp.PROVIDER == cp.PROVIDER_INTERNAL:
    from .aes import AES128
    from .aes import AES256
    
elif cp.PROVIDER == cp.PROVIDER_PYCA:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    if pu.cryptography_old_api(): from cryptography.hazmat.backends import default_backend


class AES_128_CBC:
    @staticmethod
    def encrypt(plaintext, key, iv):
        if len(key) != 16: raise ValueError(f"Invalid key length {len(key)*8} for {self}")
        if cp.PROVIDER == cp.PROVIDER_INTERNAL:
            cipher = AES128(key)
            return cipher.encrypt(plaintext, iv)

        elif cp.PROVIDER == cp.PROVIDER_PYCA:
            if not pu.cryptography_old_api():
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            else:
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())

            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(plaintext) + encryptor.finalize()
            return ciphertext

    @staticmethod
    def decrypt(ciphertext, key, iv):
        if len(key) != 16: raise ValueError(f"Invalid key length {len(key)*8} for {self}")
        if cp.PROVIDER == cp.PROVIDER_INTERNAL:
            cipher = AES128(key)
            return cipher.decrypt(ciphertext, iv)

        elif cp.PROVIDER == cp.PROVIDER_PYCA:
            if not pu.cryptography_old_api():
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            else:
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())

            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext

class AES_256_CBC:
    @staticmethod
    def encrypt(plaintext, key, iv):
        if len(key) != 32: raise ValueError(f"Invalid key length {len(key)*8} for {self}")
        if cp.PROVIDER == cp.PROVIDER_INTERNAL:
            cipher = AES256(key)
            return cipher.encrypt_cbc(plaintext, iv)

        elif cp.PROVIDER == cp.PROVIDER_PYCA:
            if not pu.cryptography_old_api():
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            else:
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(plaintext) + encryptor.finalize()
            return ciphertext

    @staticmethod
    def decrypt(ciphertext, key, iv):
        if len(key) != 32: raise ValueError(f"Invalid key length {len(key)*8} for {self}")
        if cp.PROVIDER == cp.PROVIDER_INTERNAL:
            cipher = AES256(key)
            return cipher.decrypt_cbc(ciphertext, iv)

        elif cp.PROVIDER == cp.PROVIDER_PYCA:
            if not pu.cryptography_old_api():
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            else:
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())

            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext
