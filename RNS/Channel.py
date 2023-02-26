from __future__ import annotations
import collections
import enum
import threading
import time
from types import TracebackType
from typing import Type, Callable, TypeVar, Generic, NewType
import abc
import contextlib
import struct
import RNS
from abc import ABC, abstractmethod
TPacket = TypeVar("TPacket")


class ChannelOutletBase(ABC, Generic[TPacket]):
    @abstractmethod
    def send(self, raw: bytes) -> TPacket:
        raise NotImplemented()

    @abstractmethod
    def resend(self, packet: TPacket) -> TPacket:
        raise NotImplemented()

    @property
    @abstractmethod
    def mdu(self):
        raise NotImplemented()

    @property
    @abstractmethod
    def rtt(self):
        raise NotImplemented()

    @property
    @abstractmethod
    def is_usable(self):
        raise NotImplemented()

    @abstractmethod
    def get_packet_state(self, packet: TPacket) -> MessageState:
        raise NotImplemented()

    @abstractmethod
    def timed_out(self):
        raise NotImplemented()

    @abstractmethod
    def __str__(self):
        raise NotImplemented()

    @abstractmethod
    def set_packet_timeout_callback(self, packet: TPacket, callback: Callable[[TPacket], None] | None,
                                    timeout: float | None = None):
        raise NotImplemented()

    @abstractmethod
    def set_packet_delivered_callback(self, packet: TPacket, callback: Callable[[TPacket], None] | None):
        raise NotImplemented()

    @abstractmethod
    def get_packet_id(self, packet: TPacket) -> any:
        raise NotImplemented()


class CEType(enum.IntEnum):
    ME_NO_MSG_TYPE      = 0
    ME_INVALID_MSG_TYPE = 1
    ME_NOT_REGISTERED   = 2
    ME_LINK_NOT_READY   = 3
    ME_ALREADY_SENT     = 4
    ME_TOO_BIG          = 5


class ChannelException(Exception):
    def __init__(self, ce_type: CEType, *args):
        super().__init__(args)
        self.type = ce_type


class MessageState(enum.IntEnum):
    MSGSTATE_NEW       = 0
    MSGSTATE_SENT      = 1
    MSGSTATE_DELIVERED = 2
    MSGSTATE_FAILED    = 3


class MessageBase(abc.ABC):
    MSGTYPE = None

    @abstractmethod
    def pack(self) -> bytes:
        raise NotImplemented()

    @abstractmethod
    def unpack(self, raw):
        raise NotImplemented()


MessageCallbackType = NewType("MessageCallbackType", Callable[[MessageBase], bool])


class Envelope:
    def unpack(self, message_factories: dict[int, Type]) -> MessageBase:
        msgtype, self.sequence, length = struct.unpack(">HHH", self.raw[:6])
        raw = self.raw[6:]
        ctor = message_factories.get(msgtype, None)
        if ctor is None:
            raise ChannelException(CEType.ME_NOT_REGISTERED, f"Unable to find constructor for Channel MSGTYPE {hex(msgtype)}")
        message = ctor()
        message.unpack(raw)
        return message

    def pack(self) -> bytes:
        if self.message.__class__.MSGTYPE is None:
            raise ChannelException(CEType.ME_NO_MSG_TYPE, f"{self.message.__class__} lacks MSGTYPE")
        data = self.message.pack()
        self.raw = struct.pack(">HHH", self.message.MSGTYPE, self.sequence, len(data)) + data
        return self.raw

    def __init__(self, outlet: ChannelOutletBase, message: MessageBase = None, raw: bytes = None, sequence: int = None):
        self.ts = time.time()
        self.id = id(self)
        self.message = message
        self.raw = raw
        self.packet: TPacket = None
        self.sequence = sequence
        self.outlet = outlet
        self.tries = 0
        self.tracked = False


class Channel(contextlib.AbstractContextManager):
    def __init__(self, outlet: ChannelOutletBase):
        self._outlet = outlet
        self._lock = threading.RLock()
        self._tx_ring: collections.deque[Envelope] = collections.deque()
        self._rx_ring: collections.deque[Envelope] = collections.deque()
        self._message_callbacks: [MessageCallbackType] = []
        self._next_sequence = 0
        self._message_factories: dict[int, Type[MessageBase]] = {}
        self._max_tries = 5

    def __enter__(self) -> Channel:
        return self

    def __exit__(self, __exc_type: Type[BaseException] | None, __exc_value: BaseException | None,
                 __traceback: TracebackType | None) -> bool | None:
        self.shutdown()
        return False

    def register_message_type(self, message_class: Type[MessageBase], *, is_system_type: bool = False):
        with self._lock:
            if not issubclass(message_class, MessageBase):
                raise ChannelException(CEType.ME_INVALID_MSG_TYPE,
                                       f"{message_class} is not a subclass of {MessageBase}.")
            if message_class.MSGTYPE is None:
                raise ChannelException(CEType.ME_INVALID_MSG_TYPE,
                                       f"{message_class} has invalid MSGTYPE class attribute.")
            if message_class.MSGTYPE >= 0xff00 and not is_system_type:
                raise ChannelException(CEType.ME_INVALID_MSG_TYPE,
                                       f"{message_class} has system-reserved message type.")
            try:
                message_class()
            except Exception as ex:
                raise ChannelException(CEType.ME_INVALID_MSG_TYPE,
                                       f"{message_class} raised an exception when constructed with no arguments: {ex}")

            self._message_factories[message_class.MSGTYPE] = message_class

    def add_message_handler(self, callback: MessageCallbackType):
        with self._lock:
            if callback not in self._message_callbacks:
                self._message_callbacks.append(callback)

    def remove_message_handler(self, callback: MessageCallbackType):
        with self._lock:
            self._message_callbacks.remove(callback)

    def shutdown(self):
        with self._lock:
            self._message_callbacks.clear()
            self.clear_rings()

    def clear_rings(self):
        with self._lock:
            for envelope in self._tx_ring:
                if envelope.packet is not None:
                    self._outlet.set_packet_timeout_callback(envelope.packet, None)
                    self._outlet.set_packet_delivered_callback(envelope.packet, None)
            self._tx_ring.clear()
            self._rx_ring.clear()

    def emplace_envelope(self, envelope: Envelope, ring: collections.deque[Envelope]) -> bool:
        with self._lock:
            i = 0
            for env in ring:
                if env.sequence < envelope.sequence:
                    ring.insert(i, envelope)
                    return True
                if env.sequence == envelope.sequence:
                    RNS.log(f"Envelope: Emplacement of duplicate envelope sequence.", RNS.LOG_EXTREME)
                    return False
                i += 1
            envelope.tracked = True
            ring.append(envelope)
            return True

    def prune_rx_ring(self):
        with self._lock:
            # Implementation for fixed window = 1
            stale = list(sorted(self._rx_ring, key=lambda env: env.sequence, reverse=True))[1:]
            for env in stale:
                env.tracked = False
                self._rx_ring.remove(env)

    def _run_callbacks(self, message: MessageBase):
        with self._lock:
            cbs = self._message_callbacks.copy()

        for cb in cbs:
            try:
                if cb(message):
                    return
            except Exception as ex:
                RNS.log(f"Channel: Error running message callback: {ex}", RNS.LOG_ERROR)

    def receive(self, raw: bytes):
        try:
            envelope = Envelope(outlet=self._outlet, raw=raw)
            with self._lock:
                message = envelope.unpack(self._message_factories)
                is_new = self.emplace_envelope(envelope, self._rx_ring)
                self.prune_rx_ring()
            if not is_new:
                RNS.log("Channel: Duplicate message received", RNS.LOG_DEBUG)
                return
            RNS.log(f"Message received: {message}", RNS.LOG_DEBUG)
            threading.Thread(target=self._run_callbacks, name="Message Callback", args=[message], daemon=True).start()
        except Exception as ex:
            RNS.log(f"Channel: Error receiving data: {ex}")

    def is_ready_to_send(self) -> bool:
        if not self._outlet.is_usable:
            RNS.log("Channel: Link is not usable.", RNS.LOG_EXTREME)
            return False

        with self._lock:
            for envelope in self._tx_ring:
                if envelope.outlet == self._outlet and (not envelope.packet
                                                        or self._outlet.get_packet_state(envelope.packet) == MessageState.MSGSTATE_SENT):
                    RNS.log("Channel: Link has a pending message.", RNS.LOG_EXTREME)
                    return False
        return True

    def _packet_tx_op(self, packet: TPacket, op: Callable[[TPacket], bool]):
        with self._lock:
            envelope = next(filter(lambda e: self._outlet.get_packet_id(e.packet) == self._outlet.get_packet_id(packet),
                                   self._tx_ring), None)
            if envelope and op(envelope):
                envelope.tracked = False
                if envelope in self._tx_ring:
                    self._tx_ring.remove(envelope)
                else:
                    RNS.log("Channel: Envelope not found in TX ring", RNS.LOG_DEBUG)
        if not envelope:
            RNS.log("Channel: Spurious message received.", RNS.LOG_EXTREME)

    def _packet_delivered(self, packet: TPacket):
        self._packet_tx_op(packet, lambda env: True)

    def _packet_timeout(self, packet: TPacket):
        def retry_envelope(envelope: Envelope) -> bool:
            if envelope.tries >= self._max_tries:
                RNS.log("Channel: Retry count exceeded, tearing down Link.", RNS.LOG_ERROR)
                self.shutdown()  # start on separate thread?
                self._outlet.timed_out()
                return True
            envelope.tries += 1
            self._outlet.resend(envelope.packet)
            return False

        self._packet_tx_op(packet, retry_envelope)

    def send(self, message: MessageBase) -> Envelope:
        envelope: Envelope | None = None
        with self._lock:
            if not self.is_ready_to_send():
                raise ChannelException(CEType.ME_LINK_NOT_READY, f"Link is not ready")
            envelope = Envelope(self._outlet, message=message, sequence=self._next_sequence)
            self._next_sequence = (self._next_sequence + 1) % 0x10000
            self.emplace_envelope(envelope, self._tx_ring)
        if envelope is None:
            raise BlockingIOError()

        envelope.pack()
        if len(envelope.raw) > self._outlet.mdu:
            raise ChannelException(CEType.ME_TOO_BIG, f"Packed message too big for packet: {len(envelope.raw)} > {self._outlet.mdu}")
        envelope.packet = self._outlet.send(envelope.raw)
        envelope.tries += 1
        self._outlet.set_packet_delivered_callback(envelope.packet, self._packet_delivered)
        self._outlet.set_packet_timeout_callback(envelope.packet, self._packet_timeout)
        return envelope

    @property
    def MDU(self):
        return self._outlet.mdu - 6  # sizeof(msgtype) + sizeof(length) + sizeof(sequence)


class LinkChannelOutlet(ChannelOutletBase):
    def __init__(self, link: RNS.Link):
        self.link = link

    def send(self, raw: bytes) -> RNS.Packet:
        packet = RNS.Packet(self.link, raw, context=RNS.Packet.CHANNEL)
        packet.send()
        return packet

    def resend(self, packet: RNS.Packet) -> RNS.Packet:
        if not packet.resend():
            RNS.log("Failed to resend packet", RNS.LOG_ERROR)
        return packet

    @property
    def mdu(self):
        return self.link.MDU

    @property
    def rtt(self):
        return self.link.rtt

    @property
    def is_usable(self):
        return True  # had issues looking at Link.status

    def get_packet_state(self, packet: TPacket) -> MessageState:
        status = packet.receipt.get_status()
        if status == RNS.PacketReceipt.SENT:
            return MessageState.MSGSTATE_SENT
        if status == RNS.PacketReceipt.DELIVERED:
            return MessageState.MSGSTATE_DELIVERED
        if status == RNS.PacketReceipt.FAILED:
            return MessageState.MSGSTATE_FAILED
        else:
            raise Exception(f"Unexpected receipt state: {status}")

    def timed_out(self):
        self.link.teardown()

    def __str__(self):
        return f"{self.__class__.__name__}({self.link})"

    def set_packet_timeout_callback(self, packet: RNS.Packet, callback: Callable[[RNS.Packet], None] | None,
                                    timeout: float | None = None):
        if timeout:
            packet.receipt.set_timeout(timeout)

        def inner(receipt: RNS.PacketReceipt):
            callback(packet)

        packet.receipt.set_timeout_callback(inner if callback else None)

    def set_packet_delivered_callback(self, packet: RNS.Packet, callback: Callable[[RNS.Packet], None] | None):
        def inner(receipt: RNS.PacketReceipt):
            callback(packet)

        packet.receipt.set_delivery_callback(inner if callback else None)

    def get_packet_id(self, packet: RNS.Packet) -> any:
        return packet.get_hash()
