# MIT License
#
# Copyright (c) 2016-2023 Mark Qvist / unsigned.io and contributors.
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
    """
    An abstract transport layer interface used by Channel.

    DEPRECATED: This was created for testing; eventually
    Channel will use Link or a LinkBase interface
    directly.
    """
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
    """
    ChannelException type codes
    """
    ME_NO_MSG_TYPE      = 0
    ME_INVALID_MSG_TYPE = 1
    ME_NOT_REGISTERED   = 2
    ME_LINK_NOT_READY   = 3
    ME_ALREADY_SENT     = 4
    ME_TOO_BIG          = 5


class ChannelException(Exception):
    """
    An exception thrown by Channel, with a type code.
    """
    def __init__(self, ce_type: CEType, *args):
        super().__init__(args)
        self.type = ce_type


class MessageState(enum.IntEnum):
    """
    Set of possible states for a Message
    """
    MSGSTATE_NEW       = 0
    MSGSTATE_SENT      = 1
    MSGSTATE_DELIVERED = 2
    MSGSTATE_FAILED    = 3


class MessageBase(abc.ABC):
    """
    Base type for any messages sent or received on a Channel.
    Subclasses must define the two abstract methods as well as
    the ``MSGTYPE`` class variable.
    """
    # MSGTYPE must be unique within all classes sent over a
    # channel. Additionally, MSGTYPE > 0xf000 are reserved.
    MSGTYPE = None
    """
    Defines a unique identifier for a message class.
    
    * Must be unique within all classes registered with a ``Channel``
    * Must be less than ``0xf000``. Values greater than or equal to ``0xf000`` are reserved.
    """

    @abstractmethod
    def pack(self) -> bytes:
        """
        Create and return the binary representation of the message

        :return: binary representation of message
        """
        raise NotImplemented()

    @abstractmethod
    def unpack(self, raw: bytes):
        """
        Populate message from binary representation

        :param raw: binary representation
        """
        raise NotImplemented()


MessageCallbackType = NewType("MessageCallbackType", Callable[[MessageBase], bool])


class Envelope:
    """
    Internal wrapper used to transport messages over a channel and
    track its state within the channel framework.
    """
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
    """
    Provides reliable delivery of messages over
    a link.

    ``Channel`` differs from ``Request`` and
    ``Resource`` in some important ways:

     **Continuous**
        Messages can be sent or received as long as
        the ``Link`` is open.
     **Bi-directional**
        Messages can be sent in either direction on
        the ``Link``; neither end is the client or
        server.
     **Size-constrained**
        Messages must be encoded into a single packet.

    ``Channel`` is similar to ``Packet``, except that it
    provides reliable delivery (automatic retries) as well
    as a structure for exchanging several types of
    messages over the ``Link``.

    ``Channel`` is not instantiated directly, but rather
    obtained from a ``Link`` with ``get_channel()``.
    """
    def __init__(self, outlet: ChannelOutletBase):
        """

        @param outlet:
        """
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
        self._shutdown()
        return False

    def register_message_type(self, message_class: Type[MessageBase]):
        """
        Register a message class for reception over a ``Channel``.

        Message classes must extend ``MessageBase``.

        :param message_class: Class to register
        """
        self._register_message_type(message_class, is_system_type=False)

    def _register_message_type(self, message_class: Type[MessageBase], *, is_system_type: bool = False):
        with self._lock:
            if not issubclass(message_class, MessageBase):
                raise ChannelException(CEType.ME_INVALID_MSG_TYPE,
                                       f"{message_class} is not a subclass of {MessageBase}.")
            if message_class.MSGTYPE is None:
                raise ChannelException(CEType.ME_INVALID_MSG_TYPE,
                                       f"{message_class} has invalid MSGTYPE class attribute.")
            if message_class.MSGTYPE >= 0xf000 and not is_system_type:
                raise ChannelException(CEType.ME_INVALID_MSG_TYPE,
                                       f"{message_class} has system-reserved message type.")
            try:
                message_class()
            except Exception as ex:
                raise ChannelException(CEType.ME_INVALID_MSG_TYPE,
                                       f"{message_class} raised an exception when constructed with no arguments: {ex}")

            self._message_factories[message_class.MSGTYPE] = message_class

    def add_message_handler(self, callback: MessageCallbackType):
        """
        Add a handler for incoming messages. A handler
        has the following signature:

        ``(message: MessageBase) -> bool``

        Handlers are processed in the order they are
        added. If any handler returns True, processing
        of the message stops; handlers after the
        returning handler will not be called.

        :param callback: Function to call
        """
        with self._lock:
            if callback not in self._message_callbacks:
                self._message_callbacks.append(callback)

    def remove_message_handler(self, callback: MessageCallbackType):
        """
        Remove a handler added with ``add_message_handler``.

        :param callback: handler to remove
        """
        with self._lock:
            self._message_callbacks.remove(callback)

    def _shutdown(self):
        with self._lock:
            self._message_callbacks.clear()
            self._clear_rings()

    def _clear_rings(self):
        with self._lock:
            for envelope in self._tx_ring:
                if envelope.packet is not None:
                    self._outlet.set_packet_timeout_callback(envelope.packet, None)
                    self._outlet.set_packet_delivered_callback(envelope.packet, None)
            self._tx_ring.clear()
            self._rx_ring.clear()

    def _emplace_envelope(self, envelope: Envelope, ring: collections.deque[Envelope]) -> bool:
        with self._lock:
            i = 0
            for existing in ring:
                if existing.sequence > envelope.sequence \
                   and not existing.sequence // 2 > envelope.sequence:  # account for overflow
                    ring.insert(i, envelope)
                    return True
                if existing.sequence == envelope.sequence:
                    RNS.log(f"Envelope: Emplacement of duplicate envelope sequence.", RNS.LOG_EXTREME)
                    return False
                i += 1
            envelope.tracked = True
            ring.append(envelope)
            return True

    def _prune_rx_ring(self):
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

    def _receive(self, raw: bytes):
        try:
            envelope = Envelope(outlet=self._outlet, raw=raw)
            with self._lock:
                message = envelope.unpack(self._message_factories)
                is_new = self._emplace_envelope(envelope, self._rx_ring)
                self._prune_rx_ring()
            if not is_new:
                RNS.log("Channel: Duplicate message received", RNS.LOG_DEBUG)
                return
            RNS.log(f"Message received: {message}", RNS.LOG_DEBUG)
            threading.Thread(target=self._run_callbacks, name="Message Callback", args=[message], daemon=True).start()
        except Exception as ex:
            RNS.log(f"Channel: Error receiving data: {ex}")

    def is_ready_to_send(self) -> bool:
        """
        Check if ``Channel`` is ready to send.

        :return: True if ready
        """
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
                self._shutdown()  # start on separate thread?
                self._outlet.timed_out()
                return True
            envelope.tries += 1
            self._outlet.resend(envelope.packet)
            return False

        self._packet_tx_op(packet, retry_envelope)

    def send(self, message: MessageBase) -> Envelope:
        """
        Send a message. If a message send is attempted and
        ``Channel`` is not ready, an exception is thrown.

        :param message: an instance of a ``MessageBase`` subclass
        """
        envelope: Envelope | None = None
        with self._lock:
            if not self.is_ready_to_send():
                raise ChannelException(CEType.ME_LINK_NOT_READY, f"Link is not ready")
            envelope = Envelope(self._outlet, message=message, sequence=self._next_sequence)
            self._next_sequence = (self._next_sequence + 1) % 0x10000
            self._emplace_envelope(envelope, self._tx_ring)
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
        """
        Maximum Data Unit: the number of bytes available
        for a message to consume in a single send. This
        value is adjusted from the ``Link`` MDU to accommodate
        message header information.

        :return: number of bytes available
        """
        return self._outlet.mdu - 6  # sizeof(msgtype) + sizeof(length) + sizeof(sequence)


class LinkChannelOutlet(ChannelOutletBase):
    """
    An implementation of ChannelOutletBase for RNS.Link.
    Allows Channel to send packets over an RNS Link with
    Packets.

    :param link: RNS Link to wrap
    """
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

        if packet and packet.receipt:
            packet.receipt.set_timeout_callback(inner if callback else None)

    def set_packet_delivered_callback(self, packet: RNS.Packet, callback: Callable[[RNS.Packet], None] | None):
        def inner(receipt: RNS.PacketReceipt):
            callback(packet)

        if packet and packet.receipt:
            packet.receipt.set_delivery_callback(inner if callback else None)

    def get_packet_id(self, packet: RNS.Packet) -> any:
        return packet.get_hash()
