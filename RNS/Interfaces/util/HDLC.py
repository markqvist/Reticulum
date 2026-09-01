# Reticulum License
#
# Copyright (c) 2026 Mark Qvist
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# - The Software shall not be used in any kind of system which includes amongst
#   its functions the ability to purposefully do harm to human beings.
#
# - The Software shall not be used, directly or indirectly, in the creation of
#   an artificial intelligence, machine learning or language model training
#   dataset, including but not limited to any use that contributes to the
#   training or development of such a model or algorithm.
#
# - The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

class HDLC():
    FLAG       = 0x7E
    ESC        = 0x7D
    ESC_MASK   = 0x20

    FLAG_B     = bytes([FLAG])
    ESC_B      = bytes([ESC])
    ESCPD_FLAG = bytes([ESC, FLAG ^ ESC_MASK])
    ESCPD_ESC  = bytes([ESC, ESC  ^ ESC_MASK])

    @staticmethod
    def escape(data):
        data = data.replace(HDLC.ESC_B,  HDLC.ESCPD_ESC)
        data = data.replace(HDLC.FLAG_B, HDLC.ESCPD_FLAG)
        return data

    @staticmethod
    def unescape(frame):
        frame = frame.replace(HDLC.ESCPD_FLAG, HDLC.FLAG_B)
        frame = frame.replace(HDLC.ESCPD_ESC,  HDLC.ESC_B)
        return frame

    @staticmethod
    def frame(data):
        esc         = HDLC.escape(data)
        frame       = bytearray(len(esc)+2)
        frame[0]    = HDLC.FLAG
        frame[1:-1] = esc
        frame[-1]   = HDLC.FLAG
        return frame

class ReceiveBuffer():
    def __init__(self, mtu, min_frame_len, max_frame_len=None, on_frame=None, on_invalid=None):
        self._mtu           = mtu
        self._min_frame_len = min_frame_len
        self._max_frame_len = max_frame_len
        self._on_frame      = on_frame
        self._on_invalid    = on_invalid
        self._buf           = bytearray()
        self._off           = 0

    def mtu(self):
        return self._mtu() if callable(self._mtu) else self._mtu

    def max(self):
        m = self._max_frame_len
        return m() if callable(m) else m

    def feed(self, data):
        if not data: return
        self._buf.extend(data)
        buf = self._buf

        while True:
            frame_start = buf.find(HDLC.FLAG, self._off)
            if frame_start == -1:
                self.reset()
                return

            frame_end = buf.find(HDLC.FLAG, frame_start+1)
            if frame_end == -1:
                if len(buf)-self._off > self.mtu()*2: self.reset()
                return

            frame = HDLC.unescape(bytes(buf[frame_start+1:frame_end]))
            frame_len = len(frame)
            if frame_len > 0:
                max_len = self.max()
                if frame_len > self._min_frame_len and (max_len is None or frame_len <= max_len):
                    if self._on_frame is not None: self._on_frame(frame)
                elif self._on_invalid is not None: self._on_invalid(frame_len)

            self._off = frame_end
            if self._off > 0 and self._off >= len(buf) // 2:
                del buf[:self._off]
                self._off = 0

    # Drops any partial frames from the buffer and
    # resets assembly offset
    def reset(self):
        self._buf.clear()
        self._off = 0

    # Buffered bytes currently unconsumed
    def __len__(self): return len(self._buf)-self._off
