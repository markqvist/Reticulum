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
import bz2
import sys
import time
import threading
from threading import RLock
import struct
from RNS.Channel import Channel, MessageBase, SystemMessageTypes
import RNS
from io import RawIOBase, BufferedRWPair, BufferedReader, BufferedWriter
from typing import Callable
from contextlib import AbstractContextManager

class StreamDataMessage(MessageBase):
    MSGTYPE = SystemMessageTypes.SMT_STREAM_DATA
    """
    Message type for ``Channel``. ``StreamDataMessage``
    uses a system-reserved message type.
    """

    STREAM_ID_MAX = 0x3fff  # 16383
    """
    The stream id is limited to 2 bytes - 2 bit
    """

    MAX_DATA_LEN = RNS.Link.MDU - 2 - 6  # 2 for stream data message header, 6 for channel envelope
    """
    When the Buffer package is imported, this value is
    calculcated based on the value of OVERHEAD
    """

    def __init__(self, stream_id: int = None, data: bytes = None, eof: bool = False, compressed: bool = False):
        """
        This class is used to encapsulate binary stream
        data to be sent over a ``Channel``.

        :param stream_id: id of stream relative to receiver
        :param data: binary data
        :param eof: set to True if signalling End of File
        """
        super().__init__()
        if stream_id is not None and stream_id > self.STREAM_ID_MAX:
            raise ValueError("stream_id must be 0-16383")
        self.stream_id = stream_id
        self.compressed = compressed
        self.data = data or bytes()
        self.eof = eof

    def pack(self) -> bytes:
        if self.stream_id is None:
            raise ValueError("stream_id")

        header_val = (0x3fff & self.stream_id) | (0x8000 if self.eof else 0x0000) | (0x4000 if self.compressed > 0 else 0x0000)
        return bytes(struct.pack(">H", header_val) + (self.data if self.data else bytes()))

    def unpack(self, raw):
        self.stream_id = struct.unpack(">H", raw[:2])[0]
        self.eof = (0x8000 & self.stream_id) > 0
        self.compressed = (0x4000 & self.stream_id) > 0
        self.stream_id = self.stream_id & 0x3fff
        self.data = raw[2:]

        if self.compressed:
            self.data = bz2.decompress(self.data)


class RawChannelReader(RawIOBase, AbstractContextManager):
    """
    An implementation of RawIOBase that receives
    binary stream data sent over a ``Channel``.

      This class generally need not be instantiated directly.
      Use :func:`RNS.Buffer.create_reader`,
      :func:`RNS.Buffer.create_writer`, and
      :func:`RNS.Buffer.create_bidirectional_buffer` functions
      to create buffered streams with optional callbacks.

      For additional information on the API of this
      object, see the Python documentation for
      ``RawIOBase``.
    """
    def __init__(self, stream_id: int, channel: Channel):
        """
        Create a raw channel reader.

        :param stream_id: local stream id to receive at
        :param channel: ``Channel`` object to receive from
        """
        self._stream_id = stream_id
        self._channel = channel
        self._lock = RLock()
        self._buffer = bytearray()
        self._eof = False
        self._channel._register_message_type(StreamDataMessage, is_system_type=True)
        self._channel.add_message_handler(self._handle_message)
        self._listeners: [Callable[[int], None]] = []

    def add_ready_callback(self, cb: Callable[[int], None]):
        """
        Add a function to be called when new data is available.
        The function should have the signature ``(ready_bytes: int) -> None``

        :param cb: function to call
        """
        with self._lock:
            self._listeners.append(cb)

    def remove_ready_callback(self, cb: Callable[[int], None]):
        """
        Remove a function added with :func:`RNS.RawChannelReader.add_ready_callback()`

        :param cb: function to remove
        """
        with self._lock:
            self._listeners.remove(cb)

    def _handle_message(self, message: MessageBase):
        if isinstance(message, StreamDataMessage):
            if message.stream_id == self._stream_id:
                with self._lock:
                    if message.data is not None:
                        self._buffer.extend(message.data)
                    if message.eof:
                        self._eof = True
                    for listener in self._listeners:
                        try:
                            threading.Thread(target=listener, name="Message Callback", args=[len(self._buffer)], daemon=True).start()
                        except Exception as ex:
                            RNS.log("Error calling RawChannelReader(" + str(self._stream_id) + ") callback: " + str(ex), RNS.LOG_ERROR)
                    return True
        return False

    def _read(self, __size: int) -> bytes | None:
        with self._lock:
            result = self._buffer[:__size]
            self._buffer = self._buffer[__size:]
            return result if len(result) > 0 or self._eof else None

    def readinto(self, __buffer: bytearray) -> int | None:
        ready = self._read(len(__buffer))
        if ready is not None:
            __buffer[:len(ready)] = ready
        return len(ready) if ready is not None else None

    def writable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def readable(self) -> bool:
        return True

    def close(self):
        with self._lock:
            self._channel.remove_message_handler(self._handle_message)
            self._listeners.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class RawChannelWriter(RawIOBase, AbstractContextManager):
    """
    An implementation of RawIOBase that receives
    binary stream data sent over a channel.

      This class generally need not be instantiated directly.
      Use :func:`RNS.Buffer.create_reader`,
      :func:`RNS.Buffer.create_writer`, and
      :func:`RNS.Buffer.create_bidirectional_buffer` functions
      to create buffered streams with optional callbacks.

      For additional information on the API of this
      object, see the Python documentation for
      ``RawIOBase``.
    """

    MAX_CHUNK_LEN     = 1024*16
    COMPRESSION_TRIES = 4

    def __init__(self, stream_id: int, channel: Channel):
        """
        Create a raw channel writer.

        :param stream_id: remote stream id to sent do
        :param channel: ``Channel`` object to send on
        """
        self._stream_id = stream_id
        self._channel = channel
        self._eof = False

    def write(self, __b: bytes) -> int | None:
        try:
            comp_tries = RawChannelWriter.COMPRESSION_TRIES
            comp_try = 1
            comp_success = False
            chunk_len = len(__b)
            if chunk_len > RawChannelWriter.MAX_CHUNK_LEN:
                chunk_len = RawChannelWriter.MAX_CHUNK_LEN
                __b = __b[:RawChannelWriter.MAX_CHUNK_LEN]
            chunk_segment = None
            while chunk_len > 32 and comp_try < comp_tries:
                chunk_segment_length = int(chunk_len/comp_try)
                compressed_chunk = bz2.compress(__b[:chunk_segment_length])
                compressed_length = len(compressed_chunk)
                if compressed_length < StreamDataMessage.MAX_DATA_LEN and compressed_length < chunk_segment_length:
                    comp_success = True
                    break
                else:
                    comp_try += 1

            if comp_success:
                chunk = compressed_chunk
                processed_length = chunk_segment_length
            else:
                chunk = bytes(__b[:StreamDataMessage.MAX_DATA_LEN])
                processed_length = len(chunk)

            message = StreamDataMessage(self._stream_id, chunk, self._eof, comp_success)
            
            self._channel.send(message)
            return processed_length

        except RNS.Channel.ChannelException as cex:
            if cex.type != RNS.Channel.CEType.ME_LINK_NOT_READY:
                raise
        return 0

    def close(self):
        try:
            link_rtt = self._channel._outlet.link.rtt
            timeout = time.time() + (link_rtt * len(self._channel._tx_ring) * 1)
        except Exception as e:
            timeout = time.time() + 15

        while time.time() < timeout and not self._channel.is_ready_to_send():
            time.sleep(0.05)

        self._eof = True
        self.write(bytes())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def seekable(self) -> bool:
        return False

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

class Buffer:
    """
    Static functions for creating buffered streams that send
    and receive over a ``Channel``.

    These functions use ``BufferedReader``, ``BufferedWriter``,
    and ``BufferedRWPair`` to add buffering to
    ``RawChannelReader`` and ``RawChannelWriter``.
    """
    @staticmethod
    def create_reader(stream_id: int, channel: Channel,
                      ready_callback: Callable[[int], None] | None = None) -> BufferedReader:
        """
        Create a buffered reader that reads binary data sent
        over a ``Channel``, with an optional callback when
        new data is available.

        Callback signature: ``(ready_bytes: int) -> None``

        For more information on the reader-specific functions
        of this object, see the Python documentation for
        ``BufferedReader``

        :param stream_id: the local stream id to receive from
        :param channel: the channel to receive on
        :param ready_callback: function to call when new data is available
        :return: a BufferedReader object
        """
        reader = RawChannelReader(stream_id, channel)
        if ready_callback:
            reader.add_ready_callback(ready_callback)
        return BufferedReader(reader)

    @staticmethod
    def create_writer(stream_id: int, channel: Channel) -> BufferedWriter:
        """
        Create a buffered writer that writes binary data over
        a ``Channel``.

        For more information on the writer-specific functions
        of this object, see the Python documentation for
        ``BufferedWriter``

        :param stream_id: the remote stream id to send to
        :param channel: the channel to send on
        :return: a BufferedWriter object
        """
        writer = RawChannelWriter(stream_id, channel)
        return BufferedWriter(writer)

    @staticmethod
    def create_bidirectional_buffer(receive_stream_id: int, send_stream_id: int, channel: Channel,
                                    ready_callback: Callable[[int], None] | None = None) -> BufferedRWPair:
        """
        Create a buffered reader/writer pair that reads and
        writes binary data over a ``Channel``, with an
        optional callback when new data is available.

        Callback signature: ``(ready_bytes: int) -> None``

        For more information on the reader-specific functions
        of this object, see the Python documentation for
        ``BufferedRWPair``

        :param receive_stream_id: the local stream id to receive at
        :param send_stream_id:  the remote stream id to send to
        :param channel: the channel to send and receive on
        :param ready_callback: function to call when new data is available
        :return: a BufferedRWPair object
        """
        reader = RawChannelReader(receive_stream_id, channel)
        if ready_callback:
            reader.add_ready_callback(ready_callback)
        writer = RawChannelWriter(send_stream_id, channel)
        return BufferedRWPair(reader, writer)
