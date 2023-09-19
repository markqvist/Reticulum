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

class SystemMessageTypes(enum.IntEnum):
    SMT_STREAM_DATA = 0xff00

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
        self.unpacked = True
        self.message = message

        return message

    def pack(self) -> bytes:
        if self.message.__class__.MSGTYPE is None:
            raise ChannelException(CEType.ME_NO_MSG_TYPE, f"{self.message.__class__} lacks MSGTYPE")
        data = self.message.pack()
        self.raw = struct.pack(">HHH", self.message.MSGTYPE, self.sequence, len(data)) + data
        self.packed = True
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
        self.unpacked = False
        self.packed = False
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

    # The initial window size at channel setup
    WINDOW     = 2

    # Absolute minimum window size
    WINDOW_MIN = 2
    WINDOW_MIN_LIMIT_SLOW    = 2
    WINDOW_MIN_LIMIT_MEDIUM  = 5
    WINDOW_MIN_LIMIT_FAST    = 16

    # The maximum window size for transfers on slow links
    WINDOW_MAX_SLOW      = 5

    # The maximum window size for transfers on mid-speed links
    WINDOW_MAX_MEDIUM    = 12

    # The maximum window size for transfers on fast links
    WINDOW_MAX_FAST      = 48
    
    # For calculating maps and guard segments, this
    # must be set to the global maximum window.
    WINDOW_MAX           = WINDOW_MAX_FAST
    
    # If the fast rate is sustained for this many request
    # rounds, the fast link window size will be allowed.
    FAST_RATE_THRESHOLD  = 10

    # If the RTT rate is higher than this value,
    # the max window size for fast links will be used.
    RTT_FAST            = 0.18
    RTT_MEDIUM          = 0.75
    RTT_SLOW            = 1.45

    # The minimum allowed flexibility of the window size.
    # The difference between window_max and window_min
    # will never be smaller than this value.
    WINDOW_FLEXIBILITY   = 4

    SEQ_MAX     = 0xFFFF
    SEQ_MODULUS = SEQ_MAX+1

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
        self._next_rx_sequence = 0
        self._message_factories: dict[int, Type[MessageBase]] = {}
        self._max_tries = 5
        self.fast_rate_rounds    = 0
        self.medium_rate_rounds  = 0

        if self._outlet.rtt > Channel.RTT_SLOW:
            self.window              = 1
            self.window_max          = 1
            self.window_min          = 1
            self.window_flexibility  = 1
        else:
            self.window              = Channel.WINDOW
            self.window_max          = Channel.WINDOW_MAX_SLOW
            self.window_min          = Channel.WINDOW_MIN
            self.window_flexibility  = Channel.WINDOW_FLEXIBILITY

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
            if callback in self._message_callbacks:
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

                if envelope.sequence == existing.sequence:
                    RNS.log(f"Envelope: Emplacement of duplicate envelope with sequence "+str(envelope.sequence), RNS.LOG_EXTREME)
                    return False
                
                if envelope.sequence < existing.sequence and not (self._next_rx_sequence - envelope.sequence) > (Channel.SEQ_MAX//2):
                    ring.insert(i, envelope)

                    envelope.tracked = True
                    return True
                
                i += 1
            
            envelope.tracked = True
            ring.append(envelope)

            return True

    def _run_callbacks(self, message: MessageBase):
        cbs = self._message_callbacks.copy()

        for cb in cbs:
            try:
                if cb(message):
                    return
            except Exception as e:
                RNS.log("Channel "+str(self)+" experienced an error while running a message callback. The contained exception was: "+str(e), RNS.LOG_ERROR)

    def _receive(self, raw: bytes):
        try:
            envelope = Envelope(outlet=self._outlet, raw=raw)
            with self._lock:
                message = envelope.unpack(self._message_factories)

                if envelope.sequence < self._next_rx_sequence:
                    window_overflow = (self._next_rx_sequence+Channel.WINDOW_MAX) % Channel.SEQ_MODULUS
                    if window_overflow < self._next_rx_sequence:
                        if envelope.sequence > window_overflow:
                            RNS.log("Invalid packet sequence ("+str(envelope.sequence)+") received on channel "+str(self), RNS.LOG_EXTREME)
                            return
                    else:
                        RNS.log("Invalid packet sequence ("+str(envelope.sequence)+") received on channel "+str(self), RNS.LOG_EXTREME)
                        return

                is_new = self._emplace_envelope(envelope, self._rx_ring)

            if not is_new:
                RNS.log("Duplicate message received on channel "+str(self), RNS.LOG_EXTREME)
                return
            else:
                with self._lock:
                    contigous = []
                    for e in self._rx_ring:
                        if e.sequence == self._next_rx_sequence:
                            contigous.append(e)
                            self._next_rx_sequence = (self._next_rx_sequence + 1) % Channel.SEQ_MODULUS
                            if self._next_rx_sequence == 0:
                                for e in self._rx_ring:
                                    if e.sequence == self._next_rx_sequence:
                                        contigous.append(e)
                                        self._next_rx_sequence = (self._next_rx_sequence + 1) % Channel.SEQ_MODULUS

                    for e in contigous:
                        if not e.unpacked:
                            m = e.unpack(self._message_factories)
                        else:
                            m = e.message
                            
                        self._rx_ring.remove(e)
                        self._run_callbacks(m)

        except Exception as e:
            RNS.log("An error ocurred while receiving data on "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

    def is_ready_to_send(self) -> bool:
        """
        Check if ``Channel`` is ready to send.

        :return: True if ready
        """
        if not self._outlet.is_usable:
            return False

        with self._lock:
            outstanding = 0
            for envelope in self._tx_ring:
                if envelope.outlet == self._outlet: 
                    if not envelope.packet or not self._outlet.get_packet_state(envelope.packet) == MessageState.MSGSTATE_DELIVERED:
                        outstanding += 1

            if outstanding >= self.window:
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

                    if self.window < self.window_max:
                        self.window += 1

                        # TODO: Remove at some point
                        # RNS.log("Increased "+str(self)+" window to "+str(self.window), RNS.LOG_DEBUG)

                    if self._outlet.rtt != 0:
                        if self._outlet.rtt > Channel.RTT_FAST:
                            self.fast_rate_rounds = 0

                            if self._outlet.rtt > Channel.RTT_MEDIUM:
                                self.medium_rate_rounds = 0

                            else:
                                self.medium_rate_rounds += 1
                                if self.window_max < Channel.WINDOW_MAX_MEDIUM and self.medium_rate_rounds == Channel.FAST_RATE_THRESHOLD:
                                    self.window_max = Channel.WINDOW_MAX_MEDIUM
                                    self.window_min = Channel.WINDOW_MIN_LIMIT_MEDIUM
                                    # TODO: Remove at some point
                                    # RNS.log("Increased "+str(self)+" max window to "+str(self.window_max), RNS.LOG_DEBUG)
                                    # RNS.log("Increased "+str(self)+" min window to "+str(self.window_min), RNS.LOG_DEBUG)
                            
                        else:
                            self.fast_rate_rounds += 1
                            if self.window_max < Channel.WINDOW_MAX_FAST and self.fast_rate_rounds == Channel.FAST_RATE_THRESHOLD:
                                self.window_max = Channel.WINDOW_MAX_FAST
                                self.window_min = Channel.WINDOW_MIN_LIMIT_FAST
                                # TODO: Remove at some point
                                # RNS.log("Increased "+str(self)+" max window to "+str(self.window_max), RNS.LOG_DEBUG)
                                # RNS.log("Increased "+str(self)+" min window to "+str(self.window_min), RNS.LOG_DEBUG)


                else:
                    RNS.log("Envelope not found in TX ring for "+str(self), RNS.LOG_EXTREME)
        if not envelope:
            RNS.log("Spurious message received on "+str(self), RNS.LOG_EXTREME)

    def _packet_delivered(self, packet: TPacket):
        self._packet_tx_op(packet, lambda env: True)

    def _update_packet_timeouts(self):
        for envelope in self._tx_ring:
            updated_timeout = self._get_packet_timeout_time(envelope.tries)
            if envelope.packet and hasattr(envelope.packet, "receipt") and envelope.packet.receipt and envelope.packet.receipt.timeout:
                if updated_timeout > envelope.packet.receipt.timeout:
                    envelope.packet.receipt.set_timeout(updated_timeout)

    def _get_packet_timeout_time(self, tries: int) -> float:
        to = pow(1.5, tries - 1) * max(self._outlet.rtt*2.5, 0.025) * (len(self._tx_ring)+1.5)
        return to

    def _packet_timeout(self, packet: TPacket):
        def retry_envelope(envelope: Envelope) -> bool:
            if envelope.tries >= self._max_tries:
                RNS.log("Retry count exceeded on "+str(self)+", tearing down Link.", RNS.LOG_ERROR)
                self._shutdown()  # start on separate thread?
                self._outlet.timed_out()
                return True

            envelope.tries += 1
            self._outlet.resend(envelope.packet)
            self._outlet.set_packet_delivered_callback(envelope.packet, self._packet_delivered)
            self._outlet.set_packet_timeout_callback(envelope.packet, self._packet_timeout, self._get_packet_timeout_time(envelope.tries))
            self._update_packet_timeouts()

            if self.window > self.window_min:
                self.window -= 1
                # TODO: Remove at some point
                # RNS.log("Decreased "+str(self)+" window to "+str(self.window), RNS.LOG_DEBUG)

                if self.window_max > (self.window_min+self.window_flexibility):
                    self.window_max -= 1
                    # TODO: Remove at some point
                    # RNS.log("Decreased "+str(self)+" max window to "+str(self.window_max), RNS.LOG_DEBUG)

                # TODO: Remove at some point
                # RNS.log("Decreased "+str(self)+" window to "+str(self.window), RNS.LOG_EXTREME)

            return False

        if self._outlet.get_packet_state(packet) != MessageState.MSGSTATE_DELIVERED:
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
            self._next_sequence = (self._next_sequence + 1) % Channel.SEQ_MODULUS
            self._emplace_envelope(envelope, self._tx_ring)

        if envelope is None:
            raise BlockingIOError()

        envelope.pack()
        if len(envelope.raw) > self._outlet.mdu:
            raise ChannelException(CEType.ME_TOO_BIG, f"Packed message too big for packet: {len(envelope.raw)} > {self._outlet.mdu}")
        
        envelope.packet = self._outlet.send(envelope.raw)
        envelope.tries += 1
        self._outlet.set_packet_delivered_callback(envelope.packet, self._packet_delivered)
        self._outlet.set_packet_timeout_callback(envelope.packet, self._packet_timeout, self._get_packet_timeout_time(envelope.tries))
        self._update_packet_timeouts()

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
        if self.link.status == RNS.Link.ACTIVE:
            packet.send()
        return packet

    def resend(self, packet: RNS.Packet) -> RNS.Packet:
        receipt = packet.resend()
        if not receipt:
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
        if packet.receipt == None:
            return MessageState.MSGSTATE_FAILED

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
        if timeout and packet.receipt:
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
        if packet and hasattr(packet, "get_hash") and callable(packet.get_hash):
            return packet.get_hash()
        else:
            return None
