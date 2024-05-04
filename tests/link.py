import unittest

import subprocess
import shlex
import threading
import time
import random
from unittest import skipIf
import RNS
import os
from tests.channel import MessageTest
from RNS.Channel import MessageBase
from RNS.Buffer import StreamDataMessage
from RNS.Interfaces.LocalInterface import LocalClientInterface
from math import ceil

APP_NAME = "rns_unit_tests"

fixed_keys = [
    ("f8953ffaf607627e615603ff1530c82c434cf87c07179dd7689ea776f30b964cfb7ba6164af00c5111a45e69e57d885e1285f8dbfe3a21e95ae17cf676b0f8b7", "650b5d76b6bec0390d1f8cfca5bd33f9"),
    ("d85d036245436a3c33d3228affae06721f8203bc364ee0ee7556368ac62add650ebf8f926abf628da9d92baaa12db89bd6516ee92ec29765f3afafcb8622d697", "1469e89450c361b253aefb0c606b6111"),
    ("8893e2bfd30fc08455997caf7abb7a6341716768dbbf9a91cc1455bd7eeaf74cdc10ec72a4d4179696040bac620ee97ebc861e2443e5270537ae766d91b58181", "e5fe93ee4acba095b3b9b6541515ed3e"),
    ("b82c7a4f047561d974de7e38538281d7f005d3663615f30d9663bad35a716063c931672cd452175d55bcdd70bb7aa35a9706872a97963dc52029938ea7341b39", "1333b911fa8ebb16726996adbe3c6262"),
    ("08bb35f92b06a0832991165a0d9b4fd91af7b7765ce4572aa6222070b11b767092b61b0fd18b3a59cae6deb9db6d4bfb1c7fcfe076cfd66eea7ddd5f877543b9", "d13712efc45ef87674fb5ac26c37c912"),
]

BUFFER_TEST_TARGET = 32000

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
        if caller != None:
            targets_job(caller)
            time.sleep(2)
        print("Starting local RNS instance...")
        c_rns = RNS.Reticulum("./tests/rnsconfig")
        if caller != None:
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

    @skipIf(os.getenv('SKIP_NORMAL_TESTS') != None, "Skipping")
    def test_0_valid_announce(self):
        init_rns(self)
        print("")

        fid = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[3][0]))
        dst = RNS.Destination(fid, RNS.Destination.IN, RNS.Destination.SINGLE, "test", "announce")
        ap  = dst.announce(send=False)
        ap.pack()
        self.assertEqual(RNS.Identity.validate_announce(ap), True)

    @skipIf(os.getenv('SKIP_NORMAL_TESTS') != None, "Skipping")
    def test_1_invalid_announce(self):
        init_rns(self)
        print("")

        fid = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[4][0]))
        dst = RNS.Destination(fid, RNS.Destination.IN, RNS.Destination.SINGLE, "test", "announce")
        ap  = dst.announce(send=False)
        fake_dst = bytes.fromhex("1333b911fa8ebb16726996adbe3c6262")
        pre_len = len(ap.data)
        ap.data = fake_dst+ap.data[16:]
        self.assertEqual(pre_len, len(ap.data))
        ap.pack()
        ap.send()
        self.assertEqual(RNS.Identity.validate_announce(ap), False)

    @skipIf(os.getenv('SKIP_NORMAL_TESTS') != None, "Skipping")
    def test_2_establish(self):
        init_rns(self)
        print("")

        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        RNS.Transport.request_path(bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        time.sleep(0.2)

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")

        self.assertEqual(dest.hash, bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        
        l1 = RNS.Link(dest)
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)

    @skipIf(os.getenv('SKIP_NORMAL_TESTS') != None, "Skipping")
    def test_3_packets(self):
        init_rns(self)
        print("")

        # TODO: Load this from public bytes only
        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        RNS.Transport.request_path(bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        time.sleep(0.2)

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")

        self.assertEqual(dest.hash, bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        
        l1 = RNS.Link(dest)
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        b = 0
        pr_t = 0
        receipts = []
        if RNS.Cryptography.backend() == "internal" or RNS.Reticulum.MTU > 500:
            num_packets = 50
        else:
            num_packets = 500

        packet_size = RNS.Link.MDU
        pstart = time.time()
        print("Sending "+str(num_packets)+" link packets of "+str(packet_size)+" bytes...")
        for i in range(0, num_packets):
            time.sleep(0.003)
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

    @skipIf(os.getenv('SKIP_NORMAL_TESTS') != None, "Skipping")
    def test_4_micro_resource(self):
        init_rns(self)
        print("")
        print("Micro resource test")

        # TODO: Load this from public bytes only
        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        RNS.Transport.request_path(bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        time.sleep(0.2)

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")

        self.assertEqual(dest.hash, bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        
        l1 = RNS.Link(dest)
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        resource_timeout = 120
        resource_size = 128
        data = os.urandom(resource_size)
        print("Sending "+self.size_str(resource_size)+" resource...")
        resource = RNS.Resource(data, l1, timeout=resource_timeout)
        start = time.time()

        # This is a hack, don't do it. Use the callbacks instead.
        while resource.status < RNS.Resource.COMPLETE:
            time.sleep(0.01)

        t = time.time() - start
        self.assertEqual(resource.status, RNS.Resource.COMPLETE)
        print("Resource completed at "+self.size_str(resource_size/t, "b")+"ps")

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)

    @skipIf(os.getenv('SKIP_NORMAL_TESTS') != None, "Skipping")
    def test_5_mini_resource(self):
        init_rns(self)
        print("")
        print("Mini resource test")

        # TODO: Load this from public bytes only
        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        RNS.Transport.request_path(bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        time.sleep(0.2)

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")

        self.assertEqual(dest.hash, bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        
        l1 = RNS.Link(dest)
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        resource_timeout = 120
        resource_size = 256*1000
        data = os.urandom(resource_size)
        print("Sending "+self.size_str(resource_size)+" resource...")
        resource = RNS.Resource(data, l1, timeout=resource_timeout)
        start = time.time()

        # This is a hack, don't do it. Use the callbacks instead.
        while resource.status < RNS.Resource.COMPLETE:
            time.sleep(0.01)

        t = time.time() - start
        self.assertEqual(resource.status, RNS.Resource.COMPLETE)
        print("Resource completed at "+self.size_str(resource_size/t, "b")+"ps")

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)

    @skipIf(os.getenv('SKIP_NORMAL_TESTS') != None, "Skipping")
    def test_6_small_resource(self):
        init_rns(self)
        print("")
        print("Small resource test")

        # TODO: Load this from public bytes only
        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        RNS.Transport.request_path(bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        time.sleep(0.2)

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")
        self.assertEqual(dest.hash, bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        
        l1 = RNS.Link(dest)
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        resource_timeout = 120
        resource_size = 1000*1000
        data = os.urandom(resource_size)
        print("Sending "+self.size_str(resource_size)+" resource...")
        resource = RNS.Resource(data, l1, timeout=resource_timeout)
        start = time.time()

        # This is a hack, don't do it. Use the callbacks instead.
        while resource.status < RNS.Resource.COMPLETE:
            time.sleep(0.01)

        t = time.time() - start
        self.assertEqual(resource.status, RNS.Resource.COMPLETE)
        print("Resource completed at "+self.size_str(resource_size/t, "b")+"ps")

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)


    @skipIf(os.getenv('SKIP_NORMAL_TESTS') != None, "Skipping")
    def test_7_medium_resource(self):
        if RNS.Cryptography.backend() == "internal":
            print("Skipping medium resource test...")
            return
        
        init_rns(self)
        print("")
        print("Medium resource test")

        # TODO: Load this from public bytes only
        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        RNS.Transport.request_path(bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        time.sleep(0.2)

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")
        self.assertEqual(dest.hash, bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        
        l1 = RNS.Link(dest)
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        resource_timeout = 120
        resource_size = 5*1000*1000
        data = os.urandom(resource_size)
        print("Sending "+self.size_str(resource_size)+" resource...")
        resource = RNS.Resource(data, l1, timeout=resource_timeout)
        start = time.time()

        # This is a hack, don't do it. Use the callbacks instead.
        while resource.status < RNS.Resource.COMPLETE:
            time.sleep(0.01)

        t = time.time() - start
        self.assertEqual(resource.status, RNS.Resource.COMPLETE)
        print("Resource completed at "+self.size_str(resource_size/t, "b")+"ps")

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)

    large_resource_status = None
    def lr_callback(self, resource):
        TestLink.large_resource_status = resource.status

    @skipIf(os.getenv('SKIP_NORMAL_TESTS') != None, "Skipping")
    def test_9_large_resource(self):
        if RNS.Cryptography.backend() == "internal":
            print("Skipping large resource test...")
            return

        init_rns(self)
        print("")
        print("Large resource test")

        # TODO: Load this from public bytes only
        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        RNS.Transport.request_path(bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        time.sleep(0.2)

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")
        self.assertEqual(dest.hash, bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        
        l1 = RNS.Link(dest)
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        resource_timeout = 120
        resource_size = 50*1000*1000
        data = os.urandom(resource_size)
        print("Sending "+self.size_str(resource_size)+" resource...")
        resource = RNS.Resource(data, l1, timeout=resource_timeout, callback=self.lr_callback)
        start = time.time()

        TestLink.large_resource_status = resource.status
        while TestLink.large_resource_status < RNS.Resource.COMPLETE:
            time.sleep(0.01)

        t = time.time() - start
        self.assertEqual(TestLink.large_resource_status, RNS.Resource.COMPLETE)
        print("Resource completed at "+self.size_str(resource_size/t, "b")+"ps")

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)

    #@skipIf(os.getenv('SKIP_NORMAL_TESTS') != None, "Skipping")
    def test_10_channel_round_trip(self):
        global c_rns
        init_rns(self)
        print("")
        print("Channel round trip test")

        # TODO: Load this from public bytes only
        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        RNS.Transport.request_path(bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        time.sleep(0.2)

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")

        self.assertEqual(dest.hash, bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))

        l1 = RNS.Link(dest)
        time.sleep(1)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)

        received = []

        def handle_message(message: MessageBase):
            received.append(message)

        test_message = MessageTest()
        test_message.data = "Hello"

        channel = l1.get_channel()
        channel.register_message_type(MessageTest)
        channel.add_message_handler(handle_message)
        channel.send(test_message)

        time.sleep(0.5)

        self.assertEqual(1, len(received))

        rx_message = received[0]

        self.assertIsInstance(rx_message, MessageTest)
        self.assertEqual("Hello back", rx_message.data)
        self.assertEqual(test_message.id, rx_message.id)
        self.assertNotEqual(test_message.not_serialized, rx_message.not_serialized)
        self.assertEqual(0, len(l1._channel._rx_ring))

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)
        self.assertEqual(0, len(l1._channel._rx_ring))

    # @skipIf(os.getenv('SKIP_NORMAL_TESTS') != None, "Skipping")
    def test_11_buffer_round_trip(self):
        global c_rns
        init_rns(self)
        print("")
        print("Buffer round trip test")

        # TODO: Load this from public bytes only
        id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
        self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

        RNS.Transport.request_path(bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
        time.sleep(0.2)

        dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")

        self.assertEqual(dest.hash, bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))

        l1 = RNS.Link(dest)
        time.sleep(1)
        self.assertEqual(l1.status, RNS.Link.ACTIVE)
        buffer = None

        received = []
        def handle_data(ready_bytes: int):
            data = buffer.read(ready_bytes)
            received.append(data)

        channel = l1.get_channel()
        buffer = RNS.Buffer.create_bidirectional_buffer(0, 0, channel, handle_data)

        buffer.write("Hi there".encode("utf-8"))
        buffer.flush()

        time.sleep(0.5)

        self.assertEqual(1 , len(received))

        rx_message = received[0].decode("utf-8")

        self.assertEqual("Hi there back at you", rx_message)

        l1.teardown()
        time.sleep(0.5)
        self.assertEqual(l1.status, RNS.Link.CLOSED)

    # @skipIf(os.getenv('SKIP_NORMAL_TESTS') != None and os.getenv('RUN_SLOW_TESTS') == None, "Skipping")
    def test_12_buffer_round_trip_big(self, local_bitrate = None):
        global c_rns, buffer_read_target
        init_rns(self)
        print("")
        print("Buffer round trip test")

        local_interface = next(filter(lambda iface: isinstance(iface, LocalClientInterface), RNS.Transport.interfaces), None)
        self.assertIsNotNone(local_interface)
        original_bitrate = local_interface.bitrate

        try:
            if local_bitrate is not None:
                local_interface.bitrate = local_bitrate
                local_interface._force_bitrate = True
                print("Forcing local bitrate of " + str(local_bitrate) + " bps (" + str(round(local_bitrate/8, 0)) + " B/s)")

            # TODO: Load this from public bytes only
            id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
            self.assertEqual(id1.hash, bytes.fromhex(fixed_keys[0][1]))

            RNS.Transport.request_path(bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))
            time.sleep(0.2)

            dest = RNS.Destination(id1, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "link", "establish")

            self.assertEqual(dest.hash, bytes.fromhex("fb48da0e82e6e01ba0c014513f74540d"))

            l1 = RNS.Link(dest)
            # delay a reasonable time for link to come up at current bitrate
            link_sleep = max(RNS.Link.MDU * 3 / local_interface.bitrate * 8, 2)
            timeout_at = time.time() + link_sleep
            print("Waiting " + str(round(link_sleep, 1)) + " sec for link to come up")
            while l1.status != RNS.Link.ACTIVE and time.time() < timeout_at:
                time.sleep(0.01)

            self.assertEqual(l1.status, RNS.Link.ACTIVE)

            buffer = None
            received = []

            def handle_data(ready_bytes: int):
                global received_bytes
                data = buffer.read(ready_bytes)
                received.append(data)

            channel = l1.get_channel()
            buffer = RNS.Buffer.create_bidirectional_buffer(0, 0, channel, handle_data)

            # try to make the message big enough to split across packets, but
            # small enough to make the test complete in a reasonable amount of time
            # seed_text = "0123456789"
            # message = seed_text*ceil(min(max(local_interface.bitrate / 8,
            #                                  StreamDataMessage.MAX_DATA_LEN * 2 / len(seed_text)),
            #                              1000))

            if local_interface.bitrate < 1000:
                target_bytes = 3000
            else:
                target_bytes = BUFFER_TEST_TARGET
            
            random.seed(154889)
            message = random.randbytes(target_bytes)
            buffer_read_target = len(message)
            
            # the return message will have an appendage string " back at you"
            # for every StreamDataMessage that arrives. To verify, we need
            # to insert that string every MAX_DATA_LEN and also at the end.
            expected_rx_message = b""
            for i in range(0, len(message)):
                if i > 0 and (i % StreamDataMessage.MAX_DATA_LEN) == 0:
                    expected_rx_message += " back at you".encode("utf-8")
                expected_rx_message += bytes([message[i]])
            expected_rx_message += " back at you".encode("utf-8")

            # since the segments will be received at max length for a
            # StreamDataMessage, the appended text will end up in a
            # separate packet.
            print("Sending " + str(len(message)) + " bytes, receiving " + str(len(expected_rx_message)) + " bytes, ")
            
            buffer.write(message)
            buffer.flush()

            timeout = time.time() + 4
            while not time.time() > timeout:
                time.sleep(1)
                print(f"Received {len(received)} chunks so far")
            time.sleep(1)

            data = bytearray()
            for rx in received:
                data.extend(rx)
            rx_message = data

            print(f"Received {len(received)} chunks, totalling {len(rx_message)} bytes")

            self.assertEqual(len(expected_rx_message), len(rx_message))
            for i in range(0, len(expected_rx_message)):
                self.assertEqual(expected_rx_message[i], rx_message[i])
            self.assertEqual(expected_rx_message, rx_message)

            l1.teardown()
            time.sleep(0.5)
            self.assertEqual(l1.status, RNS.Link.CLOSED)
        finally:
            local_interface.bitrate = original_bitrate
            local_interface._force_bitrate = False

    # Run with
    #  RUN_SLOW_TESTS=1 python tests/link.py TestLink.test_13_buffer_round_trip_big_slow
    # Or
    #  make RUN_SLOW_TESTS=1 test
    @skipIf(os.getenv('RUN_SLOW_TESTS') == None, "Not running slow tests")
    def test_13_buffer_round_trip_big_slow(self):
        self.test_12_buffer_round_trip_big(local_bitrate=410)

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

buffer_read_len = 0
def targets(yp=False):
    if yp:
        import yappi

    def resource_started(resource):
        print("Resource started")
        if yp:
            yappi.start()

    def resource_concluded(resource):
        print("Resource concluded")
        if yp:
            try:
                yappi.stop()
                yappi.get_func_stats().save("receiver_main_calls.data", type="pstat")
                threads = yappi.get_thread_stats()
                for thread in threads:
                    print(
                        "Function stats for (%s) (%d)" % (thread.name, thread.id)
                    )  # it is the Thread.__class__.__name__
                    yappi.get_func_stats(ctx_id=thread.id).save("receiver_thread_"+str(thread.id)+".data", type="pstat")
            except Exception as e:
                print("Error: "+str(e))


        if hasattr(resource.link.attached_interface, "rxptime"):
            rx_pr = (resource.link.attached_interface.rxb*8)/resource.link.attached_interface.rxptime
            print("Average RX proccessing rate: "+size_str(rx_pr, "b")+"ps")

    def link_established(link):
        print("Link established")
        link.set_resource_strategy(RNS.Link.ACCEPT_ALL)
        link.set_resource_started_callback(resource_started)
        link.set_resource_concluded_callback(resource_concluded)
        channel = link.get_channel()

        def handle_message(message):
            if isinstance(message, MessageTest):
                message.data = message.data + " back"
                channel.send(message)

        channel.register_message_type(MessageTest)
        channel.add_message_handler(handle_message)

        buffer = None

        response_data = []
        def handle_buffer(ready_bytes: int):
            global buffer_read_len, BUFFER_TEST_TARGET
            data = buffer.read(ready_bytes)
            buffer_read_len += len(data)
            response_data.append(data)

            if data == "Hi there".encode("utf-8"):
                RNS.log("Sending response")
                for data in response_data:
                    buffer.write(data + " back at you".encode("utf-8"))
                    buffer.flush()
                    buffer_read_len = 0

            if buffer_read_len == BUFFER_TEST_TARGET:
                RNS.log("Sending response")
                for data in response_data:
                    buffer.write(data + " back at you".encode("utf-8"))
                    buffer.flush()
                    buffer_read_len = 0

        buffer = RNS.Buffer.create_bidirectional_buffer(0, 0, channel, handle_buffer)

    m_rns = RNS.Reticulum("./tests/rnsconfig", logdest=RNS.LOG_FILE, loglevel=RNS.LOG_EXTREME)
    id1 = RNS.Identity.from_bytes(bytes.fromhex(fixed_keys[0][0]))
    d1 = RNS.Destination(id1, RNS.Destination.IN, RNS.Destination.SINGLE, APP_NAME, "link", "establish")
    d1.set_proof_strategy(RNS.Destination.PROVE_ALL)
    d1.set_link_established_callback(link_established)

    while True:
        time.sleep(1)

def targets_profiling(yp=False):
    targets(yp)

def profile_resource():
    # import cProfile
    # import pstats
    # from pstats import SortKey
    # cProfile.runctx("entry()", {"entry": resource_profiling, "size_str": size_str}, {}, "profile-resource.data")
    # p = pstats.Stats("profile-resource.data")

    resource_profiling()

def profile_targets():
    
    targets_profiling(yp=True)
    # cProfile.runctx("entry()", {"entry": targets_profiling, "size_str": size_str}, {}, "profile-targets.data")
    # p = pstats.Stats("profile-targets.data")
    # p.strip_dirs().sort_stats(SortKey.TIME, SortKey.CUMULATIVE).print_stats()


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

    import yappi
    yappi.start()
    
    resource = RNS.Resource(data, l1, timeout=resource_timeout)
    start = time.time()

    time.sleep(1)

    while resource.status < RNS.Resource.COMPLETE:
        time.sleep(0.01)

    t = time.time() - start
    print("Resource completed at "+size_str(resource_size/t, "b")+"ps")

    yappi.get_func_stats().save("sender_main_calls.data", type="pstat")
    threads = yappi.get_thread_stats()
    for thread in threads:
        print(
            "Function stats for (%s) (%d)" % (thread.name, thread.id)
        )  # it is the Thread.__class__.__name__
        yappi.get_func_stats(ctx_id=thread.id).save("sender_thread_"+str(thread.id)+".data", type="pstat")

    # t_pstats = yappi.convert2pstats(tstats)
    # t_pstats.save("resource_tstat.data", type="pstat")

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