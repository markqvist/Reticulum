# MIT License
#
# Copyright (c) 2016-2022 Mark Qvist / unsigned.io
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

import RNS
import time
import threading

class Interface:
    IN  = False
    OUT = False
    FWD = False
    RPT = False
    name = None

    # Interface mode definitions
    MODE_FULL           = 0x01
    MODE_POINT_TO_POINT = 0x02
    MODE_ACCESS_POINT   = 0x03
    MODE_ROAMING        = 0x04
    MODE_BOUNDARY       = 0x05
    MODE_GATEWAY        = 0x06

    # Which interface modes a Transport Node
    # should actively discover paths for.
    DISCOVER_PATHS_FOR  = [MODE_ACCESS_POINT, MODE_GATEWAY]

    def __init__(self):
        self.rxb = 0
        self.txb = 0
        self.online = False

    def get_hash(self):
        return RNS.Identity.full_hash(str(self).encode("utf-8"))

    def process_announce_queue(self):
        if not hasattr(self, "announce_cap"):
            self.announce_cap = RNS.Reticulum.ANNOUNCE_CAP

        if hasattr(self, "announce_queue"):
            try:
                now = time.time()
                stale = []
                for a in self.announce_queue:
                    if now > a["time"]+RNS.Reticulum.QUEUED_ANNOUNCE_LIFE:
                        stale.append(a)

                for s in stale:
                    if s in self.announce_queue:
                        self.announce_queue.remove(s)

                if len(self.announce_queue) > 0:
                    min_hops = min(entry["hops"] for entry in self.announce_queue)
                    entries = list(filter(lambda e: e["hops"] == min_hops, self.announce_queue))
                    entries.sort(key=lambda e: e["time"])
                    selected = entries[0]

                    now       = time.time()
                    tx_time   = (len(selected["raw"])*8) / self.bitrate
                    wait_time = (tx_time / self.announce_cap)
                    self.announce_allowed_at = now + wait_time

                    self.processOutgoing(selected["raw"])

                    if selected in self.announce_queue:
                        self.announce_queue.remove(selected)

                    if len(self.announce_queue) > 0:
                        timer = threading.Timer(wait_time, self.process_announce_queue)
                        timer.start()

            except Exception as e:
                self.announce_queue = []
                RNS.log("Error while processing announce queue on "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)
                RNS.log("The announce queue for this interface has been cleared.", RNS.LOG_ERROR)

    def detach(self):
        pass