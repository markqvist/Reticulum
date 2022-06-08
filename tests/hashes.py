import hashlib
import random
import RNS
import os
import time
import unittest

class TestSHA256(unittest.TestCase):
    def setUp(self):
        self.f = RNS.Cryptography.sha256

    def test_empty(self):
        self.assertEqual(
            self.f(''.encode("utf-8")),
            bytes.fromhex("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"))

    def test_less_than_block_length(self):
        self.assertEqual(
            self.f('abc'.encode("utf-8")),
            bytes.fromhex("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"))

    def test_block_length(self):
        self.assertEqual(
            self.f('a'.encode("utf-8")*64),
            bytes.fromhex("ffe054fe7ae0cb6dc65c3af9b61d5209f439851db43d0ba5997337df154668eb"))

    def test_several_blocks(self):
        self.assertEqual(
            self.f('a'.encode("utf-8")*1000000),
            bytes.fromhex("cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"))

    def test_random_blocks(self):
        max_rounds = 5000

        b = 0
        i = 0
        ok = True
        start = time.time()
        print("")
        while ok and i < max_rounds:
            i += 1
            rlen = random.randint(0, 1024*16)
            rdat = os.urandom(rlen)
            b += rlen
            msg = rdat
            ok = RNS.Cryptography.sha256(msg) == hashlib.sha256(msg).digest()
            # t = RNS.Cryptography.sha256(msg)
            # t = hashlib.sha256(msg).digest()
            if (i%1000 == 0):
                gbytes = round(b/1000000000,3)
                mbps = round((b*8/1000000)/(time.time()-start), 2)
                print(str(i)+" rounds OK, total data: "+str(gbytes)+"GB, "+str(mbps)+"mbps")

        if not ok:
            print("Failed at round "+str(i))
        else:
            print("SHA-256 test OK")

        self.assertEqual(ok, True)


class TestSHA512(unittest.TestCase):
    def setUp(self):
        self.f = RNS.Cryptography.sha512

    def test_empty(self):
        self.assertEqual(
            self.f(''.encode("utf-8")),
            bytes.fromhex(
                'cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce'+
                '47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e'))

    def test_less_than_block_length(self):
        self.assertEqual(self.f('abc'.encode("utf-8")),
            bytes.fromhex(
                'ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a'+
                '2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f'))

    def test_block_length(self):
        self.assertEqual(self.f('a'.encode("utf-8")*128),
            bytes.fromhex(
                'b73d1929aa615934e61a871596b3f3b33359f42b8175602e89f7e06e5f658a24'+
                '3667807ed300314b95cacdd579f3e33abdfbe351909519a846d465c59582f321'))

    def test_several_blocks(self):
        self.assertEqual(self.f('a'.encode("utf-8")*1000000),
            bytes.fromhex(
                'e718483d0ce769644e2e42c7bc15b4638e1f98b13b2044285632a803afa973eb'+
                'de0ff244877ea60a4cb0432ce577c31beb009c5c2c49aa2e4eadb217ad8cc09b'))

    def test_random_blocks(self):
        max_rounds = 5000

        b = 0
        i = 0
        ok = True
        start = time.time()
        print("")
        while ok and i < max_rounds:
            i += 1
            rlen = random.randint(0, 1024*16)
            rdat = os.urandom(rlen)
            b += rlen
            msg = rdat
            ok = RNS.Cryptography.sha512(msg) == hashlib.sha512(msg).digest()
            # t = RNS.Cryptography.sha512(msg)
            # t = hashlib.sha512(msg).digest()
            if (i%1000 == 0):
                gbytes = round(b/1000000000,3)
                mbps = round((b*8/1000000)/(time.time()-start), 2)
                print(str(i)+" rounds OK, total data: "+str(gbytes)+"GB, "+str(mbps)+"mbps")

        if not ok:
            print("Failed at round "+str(i))
        else:
            print("SHA-512 test OK")

        self.assertEqual(ok, True)


if __name__ == '__main__':
    unittest.main(verbosity=2)