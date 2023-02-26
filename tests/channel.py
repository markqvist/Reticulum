from __future__ import annotations
import threading
import RNS
from RNS.Channel import MessageState, ChannelOutletBase, Channel, MessageBase
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
        self.packet_callback: Callable[[ChannelOutletBase, bytes], None] | None = None

    def send(self, raw: bytes) -> Packet:
        packet = Packet(raw)
        packet.send()
        self.packets.append(packet)
        return packet

    def resend(self, packet: Packet) -> Packet:
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


class ProtocolHarness(contextlib.AbstractContextManager):
    def __init__(self, rtt: float):
        self.outlet = ChannelOutletTest(mdu=500, rtt=rtt)
        self.channel = Channel(self.outlet)

    def cleanup(self):
        self.channel.shutdown()

    def __exit__(self, __exc_type: typing.Type[BaseException], __exc_value: BaseException,
                 __traceback: types.TracebackType) -> bool:
        # self._log.debug(f"__exit__({__exc_type}, {__exc_value}, {__traceback})")
        self.cleanup()
        return False


class TestChannel(unittest.TestCase):
    def setUp(self) -> None:
        self.rtt = 0.001
        self.retry_interval = self.rtt * 150
        Packet.timeout = self.retry_interval
        self.h = ProtocolHarness(self.rtt)

    def tearDown(self) -> None:
        self.h.cleanup()

    def test_send_one_retry(self):
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

        time.sleep(self.retry_interval * 1.5)

        self.assertEqual(1, len(self.h.outlet.packets))
        self.assertEqual(2, envelope.tries)
        self.assertEqual(2, packet.tries)
        self.assertEqual(1, packet.instances)

        time.sleep(self.retry_interval)

        self.assertEqual(1, len(self.h.outlet.packets))
        self.assertEqual(self.h.outlet.packets[0], packet)
        self.assertEqual(3, envelope.tries)
        self.assertEqual(3, packet.tries)
        self.assertEqual(1, packet.instances)
        self.assertEqual(MessageState.MSGSTATE_SENT, packet.state)

        packet.delivered()

        self.assertEqual(MessageState.MSGSTATE_DELIVERED, packet.state)

        time.sleep(self.retry_interval)

        self.assertEqual(1, len(self.h.outlet.packets))
        self.assertEqual(3, envelope.tries)
        self.assertEqual(3, packet.tries)
        self.assertEqual(0, packet.instances)
        self.assertFalse(envelope.tracked)

    def test_send_timeout(self):
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

        time.sleep(self.retry_interval * 7.5)

        self.assertEqual(1, len(self.h.outlet.packets))
        self.assertEqual(5, envelope.tries)
        self.assertEqual(5, packet.tries)
        self.assertEqual(0, packet.instances)
        self.assertEqual(MessageState.MSGSTATE_FAILED, packet.state)
        self.assertFalse(envelope.tracked)

    def eat_own_dog_food(self, message: MessageBase, checker: typing.Callable[[MessageBase], None]):
        decoded: [MessageBase] = []

        def handle_message(message: MessageBase):
            decoded.append(message)

        self.h.channel.set_message_callback(handle_message)
        self.assertEqual(len(self.h.outlet.packets), 0)

        envelope = self.h.channel.send(message)
        time.sleep(self.retry_interval * 0.5)

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

        time.sleep(self.retry_interval * 2)

        self.assertEqual(1, len(self.h.outlet.packets))
        self.assertEqual(1, envelope.tries)
        self.assertEqual(1, packet.tries)
        self.assertEqual(0, packet.instances)
        self.assertFalse(envelope.tracked)

        self.assertEqual(len(self.h.outlet.packets), 1)
        self.assertEqual(MessageState.MSGSTATE_DELIVERED, packet.state)
        self.assertFalse(envelope.tracked)
        self.assertEqual(0, len(decoded))

        self.h.channel.receive(packet.raw)

        self.assertEqual(1, len(decoded))

        rx_message = decoded[0]

        self.assertIsNotNone(rx_message)
        self.assertIsInstance(rx_message, message.__class__)
        checker(rx_message)

    def test_send_receive_message_test(self):
        message = MessageTest()

        def check(rx_message: MessageBase):
            self.assertIsInstance(rx_message, message.__class__)
            self.assertEqual(message.id, rx_message.id)
            self.assertEqual(message.data, rx_message.data)
            self.assertNotEqual(message.not_serialized, rx_message.not_serialized)

        self.eat_own_dog_food(message, check)


if __name__ == '__main__':
    unittest.main(verbosity=2)
