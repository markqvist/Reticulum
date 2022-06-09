# MIT License

# Copyright (c) 2021 Or Gur Arie

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from .utils import *


class AES:
    # AES-128 block size
    block_size = 16
    # AES-128 encrypts messages with 10 rounds
    _rounds = 10


    # initiate the AES objecy
    def __init__(self, key):
        """
        Initializes the object with a given key.
        """
        # make sure key length is right
        assert len(key) == AES.block_size

        # ExpandKey
        self._round_keys = self._expand_key(key)


    # will perform the AES ExpandKey phase
    def _expand_key(self, master_key):
        """
        Expands and returns a list of key matrices for the given master_key.
        """

        # Initialize round keys with raw key material.
        key_columns = bytes2matrix(master_key)
        iteration_size = len(master_key) // 4

        # Each iteration has exactly as many columns as the key material.
        i = 1
        while len(key_columns) < (self._rounds + 1) * 4:
            # Copy previous word.
            word = list(key_columns[-1])

            # Perform schedule_core once every "row".
            if len(key_columns) % iteration_size == 0:
                # Circular shift.
                word.append(word.pop(0))
                # Map to S-BOX.
                word = [s_box[b] for b in word]
                # XOR with first byte of R-CON, since the others bytes of R-CON are 0.
                word[0] ^= r_con[i]
                i += 1
            elif len(master_key) == 32 and len(key_columns) % iteration_size == 4:
                # Run word through S-box in the fourth iteration when using a
                # 256-bit key.
                word = [s_box[b] for b in word]

            # XOR with equivalent word from previous iteration.
            word = bytes(i^j for i, j in zip(word, key_columns[-iteration_size]))
            key_columns.append(word)

        # Group key words in 4x4 byte matrices.
        return [key_columns[4*i : 4*(i+1)] for i in range(len(key_columns) // 4)]


    # encrypt a single block of data with AES
    def _encrypt_block(self, plaintext):
        """
        Encrypts a single block of 16 byte long plaintext.
        """
        # length of a single block
        assert len(plaintext) == AES.block_size

        # perform on a matrix
        state = bytes2matrix(plaintext)

        # AddRoundKey
        add_round_key(state, self._round_keys[0])

        # 9 main rounds
        for i in range(1, self._rounds):
            # SubBytes
            sub_bytes(state)
            # ShiftRows
            shift_rows(state)
            # MixCols
            mix_columns(state)
            # AddRoundKey
            add_round_key(state, self._round_keys[i])

        # last round, w/t AddRoundKey step
        sub_bytes(state)
        shift_rows(state)
        add_round_key(state, self._round_keys[-1])

        # return the encrypted matrix as bytes
        return matrix2bytes(state)


    # decrypt a single block of data with AES
    def _decrypt_block(self, ciphertext):
        """
        Decrypts a single block of 16 byte long ciphertext.
        """
        # length of a single block
        assert len(ciphertext) == AES.block_size

        # perform on a matrix
        state = bytes2matrix(ciphertext)

        # in reverse order, last round is first
        add_round_key(state, self._round_keys[-1])
        inv_shift_rows(state)
        inv_sub_bytes(state)

        for i in range(self._rounds - 1, 0, -1):
            # nain rounds
            add_round_key(state, self._round_keys[i])
            inv_mix_columns(state)
            inv_shift_rows(state)
            inv_sub_bytes(state)

        # initial AddRoundKey phase
        add_round_key(state, self._round_keys[0])

        # return bytes
        return matrix2bytes(state)


    # will encrypt the entire data 
    def encrypt(self, plaintext, iv):
        """
        Encrypts `plaintext` using CBC mode and PKCS#7 padding, with the given
        initialization vector (iv).
        """
        # iv length must be same as block size
        assert len(iv) == AES.block_size

        assert len(plaintext) % AES.block_size == 0

        ciphertext_blocks = []

        previous = iv
        for plaintext_block in split_blocks(plaintext):
            # in CBC mode every block is XOR'd with the previous block
            xorred = xor_bytes(plaintext_block, previous)

            # encrypt current block
            block = self._encrypt_block(xorred)
            previous = block

            # append to ciphertext
            ciphertext_blocks.append(block)

        # return as bytes
        return b''.join(ciphertext_blocks)


    # will decrypt the entire data 
    def decrypt(self, ciphertext, iv):
        """
        Decrypts `ciphertext` using CBC mode and PKCS#7 padding, with the given
        initialization vector (iv).
        """
        # iv length must be same as block size
        assert len(iv) == AES.block_size

        plaintext_blocks = []

        previous = iv
        for ciphertext_block in split_blocks(ciphertext):
            # in CBC mode every block is XOR'd with the previous block
            xorred = xor_bytes(previous, self._decrypt_block(ciphertext_block))
            
            # append plaintext
            plaintext_blocks.append(xorred)
            previous = ciphertext_block

        return b''.join(plaintext_blocks)


def test():
    # modules and classes requiered for test only
    import os
    class bcolors:
        OK = '\033[92m' #GREEN
        WARNING = '\033[93m' #YELLOW
        FAIL = '\033[91m' #RED
        RESET = '\033[0m' #RESET COLOR

    # will test AES class by performing an encryption / decryption
    print("AES Tests")
    print("=========")

    # generate a secret key and print details
    key = os.urandom(AES.block_size)
    _aes = AES(key)
    print(f"Algorithm: AES-CBC-{AES.block_size*8}")
    print(f"Secret Key: {key.hex()}")
    print()

    # test single block encryption / decryption
    iv = os.urandom(AES.block_size)

    single_block_text = b"SingleBlock Text"
    print("Single Block Tests")
    print("------------------")
    print(f"iv: {iv.hex()}")
    
    print(f"plain text: '{single_block_text.decode()}'")
    ciphertext_block = _aes._encrypt_block(single_block_text)
    plaintext_block = _aes._decrypt_block(ciphertext_block)
    print(f"Ciphertext Hex: {ciphertext_block.hex()}")
    print(f"Plaintext: {plaintext_block.decode()}")
    assert plaintext_block == single_block_text
    print(bcolors.OK + "Single Block Test Passed Successfully" + bcolors.RESET)
    print()

    # test a less than a block length phrase
    iv = os.urandom(AES.block_size)

    short_text = b"Just Text"
    print("Short Text Tests")
    print("----------------")
    print(f"iv: {iv.hex()}")
    print(f"plain text: '{short_text.decode()}'")
    ciphertext_short = _aes.encrypt(short_text, iv)
    plaintext_short = _aes.decrypt(ciphertext_short, iv)
    print(f"Ciphertext Hex: {ciphertext_short.hex()}")
    print(f"Plaintext: {plaintext_short.decode()}")
    assert short_text == plaintext_short
    print(bcolors.OK + "Short Text Test Passed Successfully" + bcolors.RESET)
    print()

    # test an arbitrary length phrase
    iv = os.urandom(AES.block_size)

    text = b"This Text is longer than one block"
    print("Arbitrary Length Tests")
    print("----------------------")
    print(f"iv: {iv.hex()}")
    print(f"plain text: '{text.decode()}'")
    ciphertext = _aes.encrypt(text, iv)
    plaintext = _aes.decrypt(ciphertext, iv)
    print(f"Ciphertext Hex: {ciphertext.hex()}")
    print(f"Plaintext: {plaintext.decode()}")
    assert text == plaintext
    print(bcolors.OK + "Arbitrary Length Text Test Passed Successfully" + bcolors.RESET)
    print()


if __name__ == "__main__":
    # test AES class
    test()    
