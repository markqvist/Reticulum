# MIT License
#
# Copyright (c) 2022 Mark Qvist / unsigned.io
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

import RNS.Cryptography.Provider as cp
import RNS.vendor.platformutils as pu

if cp.PROVIDER == cp.PROVIDER_INTERNAL:
    from .aes import AES
    
elif cp.PROVIDER == cp.PROVIDER_PYCA:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    if pu.cryptography_old_api():
        from cryptography.hazmat.backends import default_backend


class AES_128_CBC:

    @staticmethod
    def encrypt(plaintext, key, iv):
        if cp.PROVIDER == cp.PROVIDER_INTERNAL:
            cipher = AES(key)
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
        if cp.PROVIDER == cp.PROVIDER_INTERNAL:
            cipher = AES(key)
            return cipher.decrypt(ciphertext, iv)

        elif cp.PROVIDER == cp.PROVIDER_PYCA:
            if not pu.cryptography_old_api():
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            else:
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())

            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext
