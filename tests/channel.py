from __future__ import annotations
import threading
import RNS
from RNS.Channel import MessageState, ChannelOutletBase, Channel, MessageBase
import RNS.Buffer
from RNS.vendor import umsgpack
from typing import Callable
import contextlib
import typing
import types
import time
import uuid
import unittest


class Packet:
    timeout = 1.0

    def __init__(self, raw: bytes):
        self.state = MessageState.MSGSTATE_NEW
        self.raw = raw
        self.packet_id = uuid.uuid4()
        self.tries = 0
        self.timeout_id = None
        self.lock = threading.RLock()
        self.instances = 0
        self.timeout_callback: Callable[[Packet], None] | None = None
        self.delivered_callback: Callable[[Packet], None] | None = None

    def set_timeout(self, callback: Callable[[Packet], None] | None, timeout: float):
        with self.lock:
            if timeout is not None:
                self.timeout = timeout
            self.timeout_callback = callback


    def send(self):
        self.tries += 1
        self.state = MessageState.MSGSTATE_SENT

        def elapsed(timeout: float, timeout_id: uuid.uuid4):
            with self.lock:
                self.instances += 1
            try:
                time.sleep(timeout)
                with self.lock:
                    if self.timeout_id == timeout_id:
                        self.timeout_id = None
                        self.state = MessageState.MSGSTATE_FAILED
                        if self.timeout_callback:
                            self.timeout_callback(self)
            finally:
                with self.lock:
                    self.instances -= 1

        self.timeout_id = uuid.uuid4()
        threading.Thread(target=elapsed, name="Packet Timeout", args=[self.timeout, self.timeout_id],
                         daemon=True).start()

    def clear_timeout(self):
        self.timeout_id = None

    def set_delivered_callback(self, callback: Callable[[Packet], None]):
        self.delivered_callback = callback
        
    def delivered(self):
        with self.lock:
            self.state = MessageState.MSGSTATE_DELIVERED
            self.timeout_id = None
        if self.delivered_callback:
            self.delivered_callback(self)


class ChannelOutletTest(ChannelOutletBase):
    def get_packet_state(self, packet: Packet) -> MessageState:
        return packet.state

    def set_packet_timeout_callback(self, packet: Packet, callback: Callable[[Packet], None] | None,
                                    timeout: float | None = None):
        packet.set_timeout(callback, timeout)

    def set_packet_delivered_callback(self, packet: Packet, callback: Callable[[Packet], None] | None):
        packet.set_delivered_callback(callback)

    def get_packet_id(self, packet: Packet) -> any:
        return packet.packet_id

    def __init__(self, mdu: int, rtt: float):
        self.link_id = uuid.uuid4()
        self.timeout_callbacks = 0
        self._mdu = mdu
        self._rtt = rtt
        self._usable = True
        self.packets = []
        self.lock = threading.RLock()
        self.packet_callback: Callable[[ChannelOutletBase, bytes], None] | None = None

    def send(self, raw: bytes) -> Packet:
        with self.lock:
            packet = Packet(raw)
            packet.send()
            self.packets.append(packet)
            return packet

    def resend(self, packet: Packet) -> Packet:
        with self.lock:
            packet.send()
            return packet

    @property
    def mdu(self):
        return self._mdu

    @property
    def rtt(self):
        return self._rtt

    @property
    def is_usable(self):
        return self._usable

    def timed_out(self):
        self.timeout_callbacks += 1

    def __str__(self):
        return str(self.link_id)


class MessageTest(MessageBase):
    MSGTYPE = 0xabcd

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.data = "test"
        self.not_serialized = str(uuid.uuid4())

    def pack(self) -> bytes:
        return umsgpack.packb((self.id, self.data))

    def unpack(self, raw):
        self.id, self.data = umsgpack.unpackb(raw)


class SystemMessage(MessageBase):
    MSGTYPE = 0xf000

    def pack(self) -> bytes:
        return bytes()

    def unpack(self, raw):
        pass


class ProtocolHarness(contextlib.AbstractContextManager):
    def __init__(self, rtt: float):
        self.outlet = ChannelOutletTest(mdu=500, rtt=rtt)
        self.channel = Channel(self.outlet)
        Packet.timeout = self.channel._get_packet_timeout_time(1)

    def cleanup(self):
        self.channel._shutdown()

    def __exit__(self, __exc_type: typing.Type[BaseException], __exc_value: BaseException,
                 __traceback: types.TracebackType) -> bool:
        # self._log.debug(f"__exit__({__exc_type}, {__exc_value}, {__traceback})")
        self.cleanup()
        return False


class TestChannel(unittest.TestCase):
    def setUp(self) -> None:
        print("")
        self.rtt = 0.01
        self.h = ProtocolHarness(self.rtt)

    def tearDown(self) -> None:
        self.h.cleanup()

    def test_send_one_retry(self):
        print("Channel test one retry")
        message = MessageTest()

        self.assertEqual(0, len(self.h.outlet.packets))

        envelope = self.h.channel.send(message)

        self.assertIsNotNone(envelope)
        self.assertIsNotNone(envelope.raw)
        self.assertEqual(1, len(self.h.outlet.packets))
        self.assertIsNotNone(envelope.packet)
        self.assertTrue(envelope in self.h.channel._tx_ring)
        self.assertTrue(envelope.tracked)

        packet = self.h.outlet.packets[0]

        self.assertEqual(envelope.packet, packet)
        self.assertEqual(1, envelope.tries)
        self.assertEqual(1, packet.tries)
        self.assertEqual(1, packet.instances)
        self.assertEqual(MessageState.MSGSTATE_SENT, packet.state)
        self.assertEqual(envelope.raw, packet.raw)

        time.sleep(self.h.channel._get_packet_timeout_time(1) * 1.1)

        self.assertEqual(1, len(self.h.outlet.packets))
        self.assertEqual(2, envelope.tries)
        self.assertEqual(2, packet.tries)
        self.assertEqual(1, packet.instances)

        time.sleep(self.h.channel._get_packet_timeout_time(2) * 1.1)

        self.assertEqual(1, len(self.h.outlet.packets))
        self.assertEqual(self.h.outlet.packets[0], packet)
        self.assertEqual(3, envelope.tries)
        self.assertEqual(3, packet.tries)
        self.assertEqual(1, packet.instances)
        self.assertEqual(MessageState.MSGSTATE_SENT, packet.state)

        packet.delivered()

        self.assertEqual(MessageState.MSGSTATE_DELIVERED, packet.state)

        time.sleep(self.h.channel._get_packet_timeout_time(3) * 1.1)

        self.assertEqual(1, len(self.h.outlet.packets))
        self.assertEqual(3, envelope.tries)
        self.assertEqual(3, packet.tries)
        self.assertEqual(0, packet.instances)
        self.assertFalse(envelope.tracked)

    def test_send_timeout(self):
        print("Channel test retry count exceeded")
        message = MessageTest()

        self.assertEqual(0, len(self.h.outlet.packets))

        envelope = self.h.channel.send(message)

        self.assertIsNotNone(envelope)
        self.assertIsNotNone(envelope.raw)
        self.assertEqual(1, len(self.h.outlet.packets))
        self.assertIsNotNone(envelope.packet)
        self.assertTrue(envelope in self.h.channel._tx_ring)
        self.assertTrue(envelope.tracked)

        packet = self.h.outlet.packets[0]

        self.assertEqual(envelope.packet, packet)
        self.assertEqual(1, envelope.tries)
        self.assertEqual(1, packet.tries)
        self.assertEqual(1, packet.instances)
        self.assertEqual(MessageState.MSGSTATE_SENT, packet.state)
        self.assertEqual(envelope.raw, packet.raw)

        time.sleep(self.h.channel._get_packet_timeout_time(1))
        time.sleep(self.h.channel._get_packet_timeout_time(2))
        time.sleep(self.h.channel._get_packet_timeout_time(3))
        time.sleep(self.h.channel._get_packet_timeout_time(4))
        time.sleep(self.h.channel._get_packet_timeout_time(5) * 1.1)

        self.assertEqual(1, len(self.h.outlet.packets))
        self.assertEqual(5, envelope.tries)
        self.assertEqual(5, packet.tries)
        self.assertEqual(0, packet.instances)
        self.assertEqual(MessageState.MSGSTATE_FAILED, packet.state)
        self.assertFalse(envelope.tracked)

    def test_multiple_handler(self):
        print("Channel test multiple handler short circuit")

        handler1_called = 0
        handler1_return = True
        handler2_called = 0

        def handler1(msg: MessageBase):
            nonlocal handler1_called, handler1_return
            self.assertIsInstance(msg, MessageTest)
            handler1_called += 1
            return handler1_return

        def handler2(msg: MessageBase):
            nonlocal handler2_called
            self.assertIsInstance(msg, MessageTest)
            handler2_called += 1

        message = MessageTest()
        self.h.channel.register_message_type(MessageTest)
        self.h.channel.add_message_handler(handler1)
        self.h.channel.add_message_handler(handler2)
        envelope = RNS.Channel.Envelope(self.h.outlet, message, sequence=0)
        raw = envelope.pack()
        self.h.channel._receive(raw)

        time.sleep(0.5)

        self.assertEqual(1, handler1_called)
        self.assertEqual(0, handler2_called)

        handler1_return = False
        envelope = RNS.Channel.Envelope(self.h.outlet, message, sequence=1)
        raw = envelope.pack()
        self.h.channel._receive(raw)

        time.sleep(0.5)

        self.assertEqual(2, handler1_called)
        self.assertEqual(1, handler2_called)

    def test_system_message_check(self):
        print("Channel test register system message")
        with self.assertRaises(RNS.Channel.ChannelException):
            self.h.channel.register_message_type(SystemMessage)
        self.h.channel._register_message_type(SystemMessage, is_system_type=True)


    def eat_own_dog_food(self, message: MessageBase, checker: typing.Callable[[MessageBase], None]):
        decoded: [MessageBase] = []

        def handle_message(message: MessageBase):
            decoded.append(message)

        self.h.channel.register_message_type(message.__class__)
        self.h.channel.add_message_handler(handle_message)
        self.assertEqual(len(self.h.outlet.packets), 0)

        envelope = self.h.channel.send(message)
        time.sleep(self.h.channel._get_packet_timeout_time(1) * 0.5)

        self.assertIsNotNone(envelope)
        self.assertIsNotNone(envelope.raw)
        self.assertEqual(1, len(self.h.outlet.packets))
        self.assertIsNotNone(envelope.packet)
        self.assertTrue(envelope in self.h.channel._tx_ring)
        self.assertTrue(envelope.tracked)

        packet = self.h.outlet.packets[0]

        self.assertEqual(envelope.packet, packet)
        self.assertEqual(1, envelope.tries)
        self.assertEqual(1, packet.tries)
        self.assertEqual(1, packet.instances)
        self.assertEqual(MessageState.MSGSTATE_SENT, packet.state)
        self.assertEqual(envelope.raw, packet.raw)

        packet.delivered()

        self.assertEqual(MessageState.MSGSTATE_DELIVERED, packet.state)

        time.sleep(self.h.channel._get_packet_timeout_time(1))

        self.assertEqual(1, len(self.h.outlet.packets))
        self.assertEqual(1, envelope.tries)
        self.assertEqual(1, packet.tries)
        self.assertEqual(0, packet.instances)
        self.assertFalse(envelope.tracked)

        self.assertEqual(len(self.h.outlet.packets), 1)
        self.assertEqual(MessageState.MSGSTATE_DELIVERED, packet.state)
        self.assertFalse(envelope.tracked)
        self.assertEqual(0, len(decoded))

        self.h.channel._receive(packet.raw)

        time.sleep(0.5)

        self.assertEqual(1, len(decoded))

        rx_message = decoded[0]

        self.assertIsNotNone(rx_message)
        self.assertIsInstance(rx_message, message.__class__)
        checker(rx_message)

    def test_send_receive_message_test(self):
        print("Channel test send and receive message")
        message = MessageTest()

        def check(rx_message: MessageBase):
            self.assertIsInstance(rx_message, message.__class__)
            self.assertEqual(message.id, rx_message.id)
            self.assertEqual(message.data, rx_message.data)
            self.assertNotEqual(message.not_serialized, rx_message.not_serialized)

        self.eat_own_dog_food(message, check)

    def test_buffer_small_bidirectional(self):
        data = "Hello\n"
        with RNS.Buffer.create_bidirectional_buffer(0, 0, self.h.channel) as buffer:
            count = buffer.write(data.encode("utf-8"))
            buffer.flush()

            self.assertEqual(len(data), count)
            self.assertEqual(1, len(self.h.outlet.packets))

            packet = self.h.outlet.packets[0]
            self.h.channel._receive(packet.raw)
            time.sleep(0.2)
            result = buffer.readline()

            self.assertIsNotNone(result)
            self.assertEqual(len(result), len(data))

            decoded = result.decode("utf-8")

            self.assertEqual(data, decoded)

    def test_buffer_big(self):
        writer = RNS.Buffer.create_writer(15, self.h.channel)
        reader = RNS.Buffer.create_reader(15, self.h.channel)
        data = "01234556789"*1024*5  # 50 KB
        count = 0
        write_finished = False

        def write_thread():
            nonlocal count, write_finished
            count = writer.write(data.encode("utf-8"))
            writer.flush()
            writer.close()
            write_finished = True
        threading.Thread(target=write_thread, name="Write Thread", daemon=True).start()

        while not write_finished or next(filter(lambda x: x.state != MessageState.MSGSTATE_DELIVERED,
                                                self.h.outlet.packets), None) is not None:
            with self.h.outlet.lock:
                for packet in self.h.outlet.packets:
                    if packet.state != MessageState.MSGSTATE_DELIVERED:
                        self.h.channel._receive(packet.raw)
                        packet.delivered()
            time.sleep(0.0001)

        self.assertEqual(len(data), count)

        read_finished = False
        result = bytes()

        def read_thread():
            nonlocal read_finished, result
            result = reader.read()
            read_finished = True
        threading.Thread(target=read_thread, name="Read Thread", daemon=True).start()

        timeout_at = time.time() + 7
        while not read_finished and time.time() < timeout_at:
            time.sleep(0.001)

        self.assertTrue(read_finished)
        self.assertEqual(len(data), len(result))

        decoded = result.decode("utf-8")

        self.assertSequenceEqual(data, decoded)

    def test_buffer_small_with_callback(self):
        callbacks = 0
        last_cb_value = None

        def callback(ready: int):
            nonlocal callbacks, last_cb_value
            callbacks += 1
            last_cb_value = ready

        data = "Hello\n"
        with RNS.RawChannelWriter(0, self.h.channel) as writer, RNS.RawChannelReader(0, self.h.channel) as reader:
            reader.add_ready_callback(callback)
            count = writer.write(data.encode("utf-8"))
            writer.flush()

            self.assertEqual(len(data), count)
            self.assertEqual(1, len(self.h.outlet.packets))

            packet = self.h.outlet.packets[0]
            self.h.channel._receive(packet.raw)
            packet.delivered()

            self.assertEqual(1, callbacks)
            self.assertEqual(len(data), last_cb_value)

            result = reader.readline()

            self.assertIsNotNone(result)
            self.assertEqual(len(result), len(data))

            decoded = result.decode("utf-8")

            self.assertEqual(data, decoded)
            self.assertEqual(1, len(self.h.outlet.packets))

            result = reader.read(1)

            self.assertIsNone(result)
            self.assertTrue(self.h.channel.is_ready_to_send())

            writer.close()

            self.assertEqual(2, len(self.h.outlet.packets))

            packet = self.h.outlet.packets[1]
            self.h.channel._receive(packet.raw)
            packet.delivered()

            result = reader.read(1)

            self.assertIsNotNone(result)
            self.assertTrue(len(result) == 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
