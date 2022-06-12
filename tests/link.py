import unittest

import subprocess
import shlex
import threading
import time
import RNS
import os

APP_NAME = "rns_unit_tests"

fixed_keys = [
    ("f8953ffaf607627e615603ff1530c82c434cf87c07179dd7689ea776f30b964cfb7ba6164af00c5111a45e69e57d885e1285f8dbfe3a21e95ae17cf676b0f8b7", "650b5d76b6bec0390d1f"),
    ("d85d036245436a3c33d3228affae06721f8203bc364ee0ee7556368ac62add650ebf8f926abf628da9d92baaa12db89bd6516ee92ec29765f3afafcb8622d697", "1469e89450c361b253ae"),
    ("8893e2bfd30fc08455997caf7abb7a6341716768dbbf9a91cc1455bd7eeaf74cdc10ec72a4d4179696040bac620ee97ebc861e2443e5270537ae766d91b58181", "e5fe93ee4acba095b3b9"),
    ("b82c7a4f047561d974de7e38538281d7f005d3663615f30d9663bad35a716063c931672cd452175d55bcdd70bb7aa35a9706872a97963dc52029938ea7341b39", "1333b911fa8ebb167269"),
    ("08bb35f92b06a0832991165a0d9b4fd91af7b7765ce4572aa6222070b11b767092b61b0fd18b3a59cae6deb9db6d4bfb1c7fcfe076cfd66eea7ddd5f877543b9", "d13712efc45ef87674fb"),
]

def targets_job(caller):
    cmd = "python -c \"from tests.link import targets; targets()\""
    print("Opening subprocess for "+str(cmd)+"...", RNS.LOG_VERBOSE)
    ppath = os.getcwd()

    try:
        caller.process = subprocess.Popen(shlex.split(cmd), cwd=ppath, stdout=subprocess.PIPE)
    except Exception as e:
        raise e
        caller.pipe_is_open = False

c_rns = None
def init_rns(caller=None):
    global c_rns
    if c_rns == None:
        targets_job(caller)
        time.sleep(2)
        print("Starting local RNS instance...")
        c_rns = RNS.Reticulum("./tests/rnsconfig")
        c_rns.m_proc = caller.process
        print("Done starting local RNS instance...")

def close_rns():
    global c_rns
    if c_rns != None:
        c_rns.m_proc.kill()

class TestLink(unittest.TestCase):
    def setUp(self):
        pass

    @classmethod
    def tearDownClass(cls):
        close_rns()

    def test_0_establish(self):
        init_rns(self)
        print("")

        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")
        self.assertEqual(dest.hash, bytes.fromhex("be0c90339fce3db5b4e5"))
        
        l1 = RNS.Link(dest)
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)

    def test_1_packets(self):
        init_rns(self)
        print("")

        # TODO: Load this from public bytes only
        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")
        self.assertEqual(dest.hash, bytes.fromhex("be0c90339fce3db5b4e5"))
        
        l1 = RNS.Link(dest)
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        b = 0
        pr_t = 0
        receipts = []
        if RNS.Cryptography.backend() == "internal":
            num_packets = 50
        else:
            num_packets = 500

        packet_size = RNS.Link.MDU
        pstart = time.time()
        print("Sending "+str(num_packets)+" link packets of "+str(packet_size)+" bytes...")
        for i in range(0, num_packets):
            b += packet_size
            data = os.urandom(packet_size)
            start = time.time()
            p = RNS.Packet(l1, data)
            receipts.append(p.send())
            pr_t += time.time() - start

        print("Sent "+self.size_str(b)+", "+self.size_str(b/pr_t, "b")+"ps")
        print("Checking receipts...", end=" ")

        all_ok = False
        receipt_timeout = time.time() + 35
        while not all_ok and time.time() < receipt_timeout:
            for r in receipts:
                all_ok = True
                if not r.status == RNS.PacketReceipt.DELIVERED:
                    all_ok = False
                    break

        pduration = time.time()-pstart

        n_failed = 0
        for r in receipts:
            if not r.status == RNS.PacketReceipt.DELIVERED:
                n_failed += 1

        if n_failed > 0:
            ns = "s" if n_failed != 1 else ""
            print("Failed to receive proof for "+str(n_failed)+" packet"+ns)
            
        self.assertEqual(all_ok, True)
        print("OK!")
        print("Single packet and proof round-trip throughput is "+self.size_str(b/pduration, "b")+"ps")

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)

    def test_2_micro_resource(self):
        init_rns(self)
        print("")
        print("Micro resource test")

        # TODO: Load this from public bytes only
        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")
        self.assertEqual(dest.hash, bytes.fromhex("be0c90339fce3db5b4e5"))
        
        l1 = RNS.Link(dest)
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        resource_timeout = 120
        resource_size = 128
        data = os.urandom(resource_size)
        print("Sending "+self.size_str(resource_size)+" resource...")
        resource = RNS.Resource(data, l1, timeout=resource_timeout)
        start = time.time()

        while resource.status < RNS.Resource.COMPLETE:
            time.sleep(0.01)

        t = time.time() - start
        self.assertEqual(resource.status, RNS.Resource.COMPLETE)
        print("Resource completed at "+self.size_str(resource_size/t, "b")+"ps")

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)

    def test_3_small_resource(self):
        init_rns(self)
        print("")
        print("Small resource test")

        # TODO: Load this from public bytes only
        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")
        self.assertEqual(dest.hash, bytes.fromhex("be0c90339fce3db5b4e5"))
        
        l1 = RNS.Link(dest)
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        resource_timeout = 120
        resource_size = 1000*1000
        data = os.urandom(resource_size)
        print("Sending "+self.size_str(resource_size)+" resource...")
        resource = RNS.Resource(data, l1, timeout=resource_timeout)
        start = time.time()

        while resource.status < RNS.Resource.COMPLETE:
            time.sleep(0.01)

        t = time.time() - start
        self.assertEqual(resource.status, RNS.Resource.COMPLETE)
        print("Resource completed at "+self.size_str(resource_size/t, "b")+"ps")

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)


    def test_4_medium_resource(self):
        if RNS.Cryptography.backend() == "internal":
            print("Skipping medium resource test...")
            return
        
        init_rns(self)
        print("")
        print("Medium resource test")

        # TODO: Load this from public bytes only
        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")
        self.assertEqual(dest.hash, bytes.fromhex("be0c90339fce3db5b4e5"))
        
        l1 = RNS.Link(dest)
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        resource_timeout = 120
        resource_size = 5*1000*1000
        data = os.urandom(resource_size)
        print("Sending "+self.size_str(resource_size)+" resource...")
        resource = RNS.Resource(data, l1, timeout=resource_timeout)
        start = time.time()

        while resource.status < RNS.Resource.COMPLETE:
            time.sleep(0.01)

        t = time.time() - start
        self.assertEqual(resource.status, RNS.Resource.COMPLETE)
        print("Resource completed at "+self.size_str(resource_size/t, "b")+"ps")

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)

    def test_5_large_resource(self):
        if RNS.Cryptography.backend() == "internal":
            print("Skipping large resource test...")
            return

        init_rns(self)
        print("")
        print("Large resource test")

        # TODO: Load this from public bytes only
        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")
        self.assertEqual(dest.hash, bytes.fromhex("be0c90339fce3db5b4e5"))
        
        l1 = RNS.Link(dest)
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        resource_timeout = 120
        resource_size = 35*1000*1000
        data = os.urandom(resource_size)
        print("Sending "+self.size_str(resource_size)+" resource...")
        resource = RNS.Resource(data, l1, timeout=resource_timeout)
        start = time.time()

        while resource.status < RNS.Resource.COMPLETE:
            time.sleep(0.01)

        t = time.time() - start
        self.assertEqual(resource.status, RNS.Resource.COMPLETE)
        print("Resource completed at "+self.size_str(resource_size/t, "b")+"ps")

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)


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
    unittest.main(verbosity=1)


def targets():
    def resource_started(resource):
        print("Resource started")

    def resource_concluded(resource):
        print("Resource concluded")

        if hasattr(resource.link.attached_interface, "rxptime"):
            rx_pr = (resource.link.attached_interface.rxb*8)/resource.link.attached_interface.rxptime
            print("Average RX proccessing rate: "+size_str(rx_pr, "b")+"ps")

    def link_established(link):
        print("Link established")
        link.set_resource_strategy(RNS.Link.ACCEPT_ALL)
        link.set_resource_started_callback(resource_started)
        link.set_resource_concluded_callback(resource_concluded)

    m_rns = RNS.Reticulum("./tests/rnsconfig")
    id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
    d1 = RNS.Destination(id1, RNS.Destination.IN, RNS.Destination.SINGLE, APP_NAME, "link", "establish")
    d1.set_proof_strategy(RNS.Destination.PROVE_ALL)
    d1.set_link_established_callback(link_established)

    while True:
        time.sleep(1)

def targets_profiling():
    targets()

def profile_resource():
    import cProfile
    import pstats
    from pstats import SortKey
    cProfile.runctx("entry()", {"entry": resource_profiling, "size_str": size_str}, {}, "profile-resource.data")
    p = pstats.Stats("profile-resource.data")
    # p.strip_dirs().sort_stats(SortKey.TIME, SortKey.CUMULATIVE).print_stats()

def profile_targets():
    import cProfile
    import pstats
    from pstats import SortKey
    cProfile.runctx("entry()", {"entry": targets_profiling, "size_str": size_str}, {}, "profile-targets.data")
    p = pstats.Stats("profile-targets.data")
    p.strip_dirs().sort_stats(SortKey.TIME, SortKey.CUMULATIVE).print_stats()


def resource_profiling():
    init_rns()
    print("")

    # TODO: Load this from public bytes only
    id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))

    dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")

    l1 = RNS.Link(dest)
    time.sleep(0.5)

    resource_timeout = 120
    resource_size = 5*1000*1000
    data = os.urandom(resource_size)
    print("Sending "+size_str(resource_size)+" resource...")
    resource = RNS.Resource(data, l1, timeout=resource_timeout)
    start = time.time()

    time.sleep(1)

    while resource.status < RNS.Resource.COMPLETE:
        time.sleep(0.01)

    t = time.time() - start
    print("Resource completed at "+size_str(resource_size/t, "b")+"ps")

    if hasattr(resource.link.attached_interface, "rxptime"):
        rx_pr = (resource.link.attached_interface.rxb*8)/resource.link.attached_interface.rxptime
        print("Average RX proccessing rate: "+size_str(rx_pr, "b")+"ps")

    l1.teardown()
    time.sleep(0.5)

def size_str(num, suffix='B'):
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