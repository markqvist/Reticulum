# MIT License
#
# Copyright (c) 2016-2023 Mark Qvist / unsigned.io
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
from collections import deque

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

    # Which interface modes a Transport Node should
    # actively discover paths for.
    DISCOVER_PATHS_FOR  = [MODE_ACCESS_POINT, MODE_GATEWAY, MODE_ROAMING]

    # How many samples to use for announce
    # frequency calculations
    IA_FREQ_SAMPLES     = 6
    OA_FREQ_SAMPLES     = 6

    # Maximum amount of ingress limited announces
    # to hold at any given time.
    MAX_HELD_ANNOUNCES  = 256

    # How long a spawned interface will be
    # considered to be newly created. Two
    # hours by default.
    IC_NEW_TIME              = 2*60*60
    IC_BURST_FREQ_NEW        = 3.5
    IC_BURST_FREQ            = 12
    IC_BURST_HOLD            = 1*60
    IC_BURST_PENALTY         = 5*60
    IC_HELD_RELEASE_INTERVAL = 30

    def __init__(self):
        self.rxb = 0
        self.txb = 0
        self.created = time.time()
        self.online = False
        self.bitrate = 1e6

        self.ingress_control = True
        self.ic_max_held_announces = Interface.MAX_HELD_ANNOUNCES
        self.ic_burst_hold = Interface.IC_BURST_HOLD
        self.ic_burst_active = False
        self.ic_burst_activated = 0
        self.ic_held_release = 0
        self.ic_burst_freq_new = Interface.IC_BURST_FREQ_NEW
        self.ic_burst_freq = Interface.IC_BURST_FREQ
        self.ic_new_time = Interface.IC_NEW_TIME
        self.ic_burst_penalty = Interface.IC_BURST_PENALTY
        self.ic_held_release_interval = Interface.IC_HELD_RELEASE_INTERVAL
        self.held_announces = {}

        self.ia_freq_deque = deque(maxlen=Interface.IA_FREQ_SAMPLES)
        self.oa_freq_deque = deque(maxlen=Interface.OA_FREQ_SAMPLES)

    def get_hash(self):
        return RNS.Identity.full_hash(str(self).encode("utf-8"))

    # This is a generic function for determining when an interface
    # should activate ingress limiting. Since this can vary for
    # different interface types, this function should be overwritten
    # in case a particular interface requires a different approach.
    def should_ingress_limit(self):
        if self.ingress_control:
            freq_threshold = self.ic_burst_freq_new if self.age() < self.ic_new_time else self.ic_burst_freq
            ia_freq = self.incoming_announce_frequency()

            if self.ic_burst_active:
                if ia_freq < freq_threshold and time.time() > self.ic_burst_activated+self.ic_burst_hold:
                    self.ic_burst_active = False
                    self.ic_held_release = time.time() + self.ic_burst_penalty
                return True

            else:
                if ia_freq > freq_threshold:
                    self.ic_burst_active = True
                    self.ic_burst_activated = time.time()
                    return True

                else:
                    return False

        else:
            return False

    def age(self):
        return time.time()-self.created

    def hold_announce(self, announce_packet):
        if announce_packet.destination_hash in self.held_announces:
            self.held_announces[announce_packet.destination_hash] = announce_packet
        elif not len(self.held_announces) >= self.ic_max_held_announces:
            self.held_announces[announce_packet.destination_hash] = announce_packet

    def process_held_announces(self):
        try:
            if not self.should_ingress_limit() and len(self.held_announces) > 0 and time.time() > self.ic_held_release:
                freq_threshold = self.ic_burst_freq_new if self.age() < self.ic_new_time else self.ic_burst_freq
                ia_freq = self.incoming_announce_frequency()
                if ia_freq < freq_threshold:
                    selected_announce_packet = None
                    min_hops = RNS.Transport.PATHFINDER_M
                    for destination_hash in self.held_announces:
                        announce_packet = self.held_announces[destination_hash]
                        if announce_packet.hops < min_hops:
                            min_hops = announce_packet.hops
                            selected_announce_packet = announce_packet

                    if selected_announce_packet != None:
                        RNS.log("Releasing held announce packet "+str(selected_announce_packet)+" from "+str(self), RNS.LOG_EXTREME)
                        self.ic_held_release = time.time() + self.ic_held_release_interval
                        self.held_announces.pop(selected_announce_packet.destination_hash)
                        def release():
                            RNS.Transport.inbound(selected_announce_packet.raw, selected_announce_packet.receiving_interface)
                        threading.Thread(target=release, daemon=True).start()
        
        except Exception as e:
            RNS.log("An error occurred while processing held announces for "+str(self), RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)

    def received_announce(self):
        self.ia_freq_deque.append(time.time())
        if hasattr(self, "parent_interface") and self.parent_interface != None:
            self.parent_interface.received_announce(from_spawned=True)

    def sent_announce(self):
        self.oa_freq_deque.append(time.time())
        if hasattr(self, "parent_interface") and self.parent_interface != None:
            self.parent_interface.sent_announce(from_spawned=True)

    def incoming_announce_frequency(self):
        if not len(self.ia_freq_deque) > 1:
            return 0
        else:
            dq_len = len(self.ia_freq_deque)
            delta_sum = 0
            for i in range(1,dq_len):
                delta_sum += self.ia_freq_deque[i]-self.ia_freq_deque[i-1]
            delta_sum += time.time() - self.ia_freq_deque[dq_len-1]
            
            if delta_sum == 0:
                avg = 0
            else:
                avg = 1/(delta_sum/(dq_len))

            return avg

    def outgoing_announce_frequency(self):
        if not len(self.oa_freq_deque) > 1:
            return 0
        else:
            dq_len = len(self.oa_freq_deque)
            delta_sum = 0
            for i in range(1,dq_len):
                delta_sum += self.oa_freq_deque[i]-self.oa_freq_deque[i-1]
            delta_sum += time.time() - self.oa_freq_deque[dq_len-1]
            
            if delta_sum == 0:
                avg = 0
            else:
                avg = 1/(delta_sum/(dq_len))

            return avg

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
                    self.sent_announce()

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