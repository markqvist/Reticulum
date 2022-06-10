import unittest

import time
import RNS
import os

signed_message = "e51a008b8b8ba855993d8892a40daad84a6fb69a7138e1b5f69b427fe03449826ab6ccb81f0d72b4725e8d55c814d3e8e151b495cf5b59702f197ec366d935ad04a98ca519d6964f96ea09910b020351d1cdff3befbad323a2a28a6ec7ced4d0d67f02c525f93b321d9b076d704408475bd2d123cd51916f7e49039246ac56add37ef87e32d7f9853ac44a7f77d26fedc83e4e67a45742b751c2599309f5eda6efa0dafd957f61af1f0e86c4d6c5052e0e5fa577db99846f2b7a0204c31cef4013ca51cb307506c9209fd18d0195a7c9ae628af1a1d9ee7a4cf30037ed190a9fdcaa4ce5bb7bea19803cb5b5cea8c21fdb98d8f73ff5aaad87f5f6c3b7bcfe8974e5b063cc1113d77b9e96bec1c9d10ed37b780c3f7349a34092bb3968daeced40eb0b5130c0d11595e30b9671896385d04289d067f671599386536eed8430a72e186fb95023d5ac5dd442443bfabfe13a84a38d060af73bf20f921f38a768672fdbcb1dfece7458166e2e15948d6b4fa81f42db48747d283c670f576a0b410b31a70d2594823d0e29135a488cb0408c9e5bc1e197ff99aef471924231ccc8e3eddc82dbcea4801f14c5fc7a389a26a52cc93cfe0770953ef595ff410b7033a6ed5c975dd922b3f48f9dffcfb412eeed5758f3aa51de7eb47cd2cb"
sig_from_key_0 = "3020ef58f861591826a61c3d2d4a25b949cdb3094085ba6b1177a6f2a05f3cdd24d1095d6fdd078f0b2826e80b261c93c1ff97fbfd4857f25706d57dd073590c"

encrypted_message = "71884a271ead43558fcf1e331c5aebcd43498f16da16f8056b0893ce6b15d521eaa4f31639cd34da1b57995944076c4f14f300f2d2612111d21a3429a9966ac1da68545c00c7887d8b26f6c1ab9defa020b9519849ca41b7904199882802b6542771df85144a79890289d3c02daef6c26652c5ce9de231a2"
fixed_token = "d8d92fb6c576e906b04d65ca5fee1465ba5abb3a4c8dbcdf0496722824ba4605800000000062a113183257a03a695091e1696b3f331f1dcedc0ffbb044c70c0b881bfddbc0831374a95743be3f42160d5b324bcd521abc5607eec9c54bbda576b1bd76281c43010e932cc4b01b6391b0ff77d0c34b8359b01095e612d7be1c6fd318c21d7dd24ddb1a008a6f5a8513d57881974d4e8799f4d2c4c813abba860969721ceaa477e499e64e725a6fd082df4d2895ca363e92c66eb1bbce4248ddd86c95b50644b365318b9b757d2f535ed235cf7ae2b37e69cf4d"

fixed_keys = [
    ("f8953ffaf607627e615603ff1530c82c434cf87c07179dd7689ea776f30b964cfb7ba6164af00c5111a45e69e57d885e1285f8dbfe3a21e95ae17cf676b0f8b7", "650b5d76b6bec0390d1f"),
    ("d85d036245436a3c33d3228affae06721f8203bc364ee0ee7556368ac62add650ebf8f926abf628da9d92baaa12db89bd6516ee92ec29765f3afafcb8622d697", "1469e89450c361b253ae"),
    ("8893e2bfd30fc08455997caf7abb7a6341716768dbbf9a91cc1455bd7eeaf74cdc10ec72a4d4179696040bac620ee97ebc861e2443e5270537ae766d91b58181", "e5fe93ee4acba095b3b9"),
    ("b82c7a4f047561d974de7e38538281d7f005d3663615f30d9663bad35a716063c931672cd452175d55bcdd70bb7aa35a9706872a97963dc52029938ea7341b39", "1333b911fa8ebb167269"),
    ("08bb35f92b06a0832991165a0d9b4fd91af7b7765ce4572aa6222070b11b767092b61b0fd18b3a59cae6deb9db6d4bfb1c7fcfe076cfd66eea7ddd5f877543b9", "d13712efc45ef87674fb"),
]

class TestIdentity(unittest.TestCase):

    def test_0_create_from_bytes(self):
        for entry in fixed_keys:
            key, id_hash = entry
            i = RNS.Identity.from_bytes(bytes.fromhex(key))
            self.assertEqual(i.hash, bytes.fromhex(id_hash))
            self.assertEqual(i.get_private_key(), bytes.fromhex(key))

    def test_1_sign(self):
        print("")

        # Test known signature
        fid = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        sig = fid.sign(signed_message.encode("utf-8"))

        self.assertEqual(sig, bytes.fromhex(sig_from_key_0))

        # Test signature time jitter
        id1 = RNS.Identity()
        id2 = RNS.Identity(create_keys=False)
        id2.load_public_key(id1.get_public_key())

        if RNS.Cryptography.backend() == "internal":
            rounds = 2000
        else:
            rounds = 20000

        times = []
        for i in range(1, rounds):
            msg = os.urandom(512)
            start = time.time()
            signature = id1.sign(msg)
            t = time.time() - start
            times.append(t)

        import statistics
        tmin  = min(times)*1000
        tmax  = max(times)*1000
        tmean  = (sum(times)/len(times))*1000
        tmed = statistics.median(times)*1000
        tmdev = tmax - tmin
        mpct = (tmax/tmed)*100
        print("Random messages:")
        print("  Signature timing min/avg/med/max/mdev: "+str(round(tmin, 3))+"/"+str(round(tmean, 3))+"/"+str(round(tmed, 3))+"/"+str(round(tmax, 3))+"/"+str(round(tmdev, 3)))
        print("  Max deviation from median: "+str(round(mpct, 1))+"%")
        print()

        id1 = RNS.Identity()
        id2 = RNS.Identity(create_keys=False)
        id2.load_public_key(id1.get_public_key())

        times = []
        for i in range(1, rounds):
            msg = bytes([0x00])*512
            start = time.time()
            signature = id1.sign(msg)
            t = time.time() - start
            times.append(t)

        tmin  = min(times)*1000
        tmax  = max(times)*1000
        tmean  = (sum(times)/len(times))*1000
        tmed = statistics.median(times)*1000
        tmdev = tmax - tmin
        mpct = (tmax/tmed)*100
        print("All 0xff messages:")
        print("  Signature timing min/avg/med/max/mdev: "+str(round(tmin, 3))+"/"+str(round(tmean, 3))+"/"+str(round(tmed, 3))+"/"+str(round(tmax, 3))+"/"+str(round(tmdev, 3)))
        print("  Max deviation from median: "+str(round(mpct, 1))+"%")
        print()

        id1 = RNS.Identity()
        id2 = RNS.Identity(create_keys=False)
        id2.load_public_key(id1.get_public_key())

        times = []
        for i in range(1, rounds):
            msg = bytes([0xff])*512
            start = time.time()
            signature = id1.sign(msg)
            t = time.time() - start
            times.append(t)

        tmin  = min(times)*1000
        tmax  = max(times)*1000
        tmean  = (sum(times)/len(times))*1000
        tmed = statistics.median(times)*1000
        tmdev = tmax - tmin
        mpct = (tmax/tmed)*100
        print("All 0x00 messages:")
        print("  Signature timing min/avg/med/max/mdev: "+str(round(tmin, 3))+"/"+str(round(tmean, 3))+"/"+str(round(tmed, 3))+"/"+str(round(tmax, 3))+"/"+str(round(tmdev, 3)))
        print("  Max deviation from median: "+str(round(mpct, 1))+"%")
        print()

        b = 0
        t = 0
        for i in range(1, 500):
            mlen = i % (RNS.Reticulum.MTU//2) + (RNS.Reticulum.MTU//2)
            msg = os.urandom(mlen)
            b += mlen
            id1 = RNS.Identity()
            id2 = RNS.Identity(create_keys=False)
            id2.load_public_key(id1.get_public_key())

            start = time.time()
            signature = id1.sign(msg)
            self.assertEqual(True, id2.validate(signature, msg))
            t += time.time() - start

        print("Sign/validate chunks < MTU: "+self.size_str(b/t, "b")+"ps")

        for i in range(1, 500):
            mlen = 16*1024
            msg = os.urandom(mlen)
            b += mlen
            id1 = RNS.Identity()
            id2 = RNS.Identity(create_keys=False)
            id2.load_public_key(id1.get_public_key())

            start = time.time()
            signature = id1.sign(msg)
            self.assertEqual(True, id2.validate(signature, msg))
            t += time.time() - start

        print("Sign/validate 16KB chunks: "+self.size_str(b/t, "b")+"ps")


    def test_2_encrypt(self):
        print("")

        # Test decryption of known token
        fid = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(fid.hash, bytes.fromhex(fixed_keys[0][1]))
        plaintext = fid.decrypt(bytes.fromhex(fixed_token))
        self.assertEqual(plaintext, bytes.fromhex(encrypted_message))

        # Test encrypt and decrypt of random chunks
        print("Testing random small chunk encrypt/decrypt")
        b = 0
        e_t = 0
        d_t = 0
        for i in range(1, 500):
            mlen = i % (RNS.Reticulum.MTU//2) + (RNS.Reticulum.MTU//2)
            msg = os.urandom(mlen)
            b += mlen
            id1 = RNS.Identity()
            id2 = RNS.Identity(create_keys=False)
            id2.load_public_key(id1.get_public_key())

            e_start = time.time()
            token = id2.encrypt(msg)
            e_t += time.time() - e_start

            d_start = time.time()
            decrypted = id1.decrypt(token)
            self.assertEqual(msg, decrypted)
            d_t += time.time() - d_start

        print("Encrypt chunks < MTU: "+self.size_str(b/e_t, "b")+"ps")
        print("Decrypt chunks < MTU: "+self.size_str(b/d_t, "b")+"ps")
        print("")

        # Test encrypt and decrypt of large chunks
        print("Testing large chunk encrypt/decrypt")
        mlen = 8*1000*1000
        if RNS.Cryptography.backend() == "internal":
            lb = 1
        else:
            lb = 8
        
        for i in range(1, lb):
            msg = os.urandom(mlen)
            b += mlen
            id1 = RNS.Identity()
            id2 = RNS.Identity(create_keys=False)
            id2.load_public_key(id1.get_public_key())

            e_start = time.time()
            token = id2.encrypt(msg)
            e_t += time.time() - e_start

            d_start = time.time()
            self.assertEqual(msg, id1.decrypt(token))
            d_t += time.time() - d_start

        print("Encrypt "+self.size_str(mlen)+" chunks: "+self.size_str(b/e_t, "b")+"ps")
        print("Decrypt "+self.size_str(mlen)+" chunks: "+self.size_str(b/d_t, "b")+"ps")

    def size_str(self, num, suffix='B'):
        units = ['','K','M','G','T','P','E','Z']
        last_unit = 'Y'

        if suffix == 'b':
            num *= 8
            units = ['','K','M','G','T','P','E','Z']
            last_unit = 'Y'

        for unit in units:
            if abs(num) < 1000.0:
                if unit == "":
                    return "%.0f %s%s" % (num, unit, suffix)
                else:
                    return "%.2f %s%s" % (num, unit, suffix)
            num /= 1000.0

        return "%.2f%s%s" % (num, last_unit, suffix)

if __name__ == '__main__':
    unittest.main(verbosity=2)
