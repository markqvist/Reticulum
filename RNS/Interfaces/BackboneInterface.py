# Reticulum License
#
# Copyright (c) 2016-2025 Mark Qvist
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

from RNS.Interfaces.Interface import Interface
from RNS.Interfaces.util.TransmitBuffer import TransmitBuffer
from RNS.Interfaces.util.HDLC import HDLC, ReceiveBuffer
import threading
import socket
import select
import time
import sys
import os
import RNS

class BackboneInterface(Interface):
    HW_MTU              = 1048576
    BITRATE_GUESS       = 100_000_000
    DEFAULT_IFAC_SIZE   = 16
    AUTOCONFIGURE_MTU   = True

    BLOCK_FAST_FLAPPING = True
    FAST_FLAP_THRESHOLD = 20
    FAST_FLAP_GRACE     = 5
    FAST_FLAP_EXPIRY    = 12*60*60
    fast_flapping_lock  = threading.Lock()
    fast_flapping       = {}

    DP_IC_HIGH_WM_PCT   = 90
    DP_IC_MID_WM_PCT    = 68
    DP_IC_LOW_WM_PCT    = 10
    DP_IC_INTERVAL      = 0.250
    DP_IC_TRIGGER       = 1.5
    DP_IC_RCVBUF        = 32768
    DP_IC_IF_HEADROOM   = 32
    DP_IC_PENALTY       = 1.5
    DP_EC_INTERVAL      = 1.0
    DP_EC_MID_WM        = 128*1024
    DP_EC_HIGH_WM       = 4*1024*1024
    DP_EC_STALL_TICKS   = 3
    DP_EC_MAX_ETA       = 10.0
    DP_EC_RELEASE_ETA   = 5.0 # Gate release hysterisis
    DP_EC_DEAD_TIME     = 12.0

    epoll = None
    listener_filenos = {}
    spawned_interface_filenos = {}

    _job_active     = False
    _ic_job_active  = False
    _ec_job_active  = False
    _job_lock       = threading.Lock()
    _ec_job_lock    = threading.Lock()
    _ic_job_lock    = threading.Lock()
    _dp_ic_lock     = threading.Lock()
    _dp_ic_snapshot = 0

    @staticmethod
    def get_address_for_if(name, bind_port, prefer_ipv6=False):
        from RNS.Interfaces import netinfo
        ifaddr = netinfo.ifaddresses(name)
        if len(ifaddr) < 1:
            raise SystemError(f"No addresses available on specified kernel interface \"{name}\" for BackboneInterface to bind to")

        if (prefer_ipv6 or not netinfo.AF_INET in ifaddr) and netinfo.AF_INET6 in ifaddr:
            bind_ip = ifaddr[netinfo.AF_INET6][0]["addr"]
            if bind_ip.lower().startswith("fe80::"):
                # We'll need to add the interface as scope for link-local addresses
                return BackboneInterface.get_address_for_host(f"{bind_ip}%{name}", bind_port, prefer_ipv6)
            else:
                return BackboneInterface.get_address_for_host(bind_ip, bind_port, prefer_ipv6)
        elif netinfo.AF_INET in ifaddr:
            bind_ip = ifaddr[netinfo.AF_INET][0]["addr"]
            return (bind_ip, bind_port)
        else:
            raise SystemError(f"No addresses available on specified kernel interface \"{name}\" for BackboneInterface to bind to")

    @staticmethod
    def get_address_for_host(name, bind_port, prefer_ipv6=False):
        address_infos = socket.getaddrinfo(name, bind_port, proto=socket.IPPROTO_TCP)
        address_info  = address_infos[0]
        for entry in address_infos:
            if prefer_ipv6 and entry[0] == socket.AF_INET6:
                address_info = entry; break
            elif not prefer_ipv6 and entry[0] == socket.AF_INET:
                address_info = entry; break

        if address_info[0] == socket.AF_INET6:
            return (name, bind_port, address_info[4][2], address_info[4][3])
        elif address_info[0] == socket.AF_INET:
            return (name, bind_port)
        else:
            raise SystemError(f"No suitable kernel interface available for address \"{name}\" for BackboneInterface to bind to")


    @property
    def clients(self):
        return len(self.spawned_interfaces)

    def __init__(self, owner, configuration):
        if not RNS.vendor.platformutils.is_linux() and not RNS.vendor.platformutils.is_android():
            raise OSError("BackboneInterface is only supported on Linux-based operating systems")

        super().__init__()

        c              = Interface.get_config_obj(configuration)
        name           = c["name"]
        device         = c["device"] if "device" in c else None
        port           = int(c["port"]) if "port" in c else None
        bindip         = c["listen_ip"] if "listen_ip" in c else None
        bindport       = int(c["listen_port"]) if "listen_port" in c else None
        prefer_ipv6    = c.as_bool("prefer_ipv6") if "prefer_ipv6" in c else False
        flap_block     = c.as_bool("block_fast_flapping") if "block_fast_flapping" in c else BackboneInterface.BLOCK_FAST_FLAPPING
        flap_threshold = c.as_float("fast_flapping_threshold") if "fast_flapping_threshold" in c else BackboneInterface.FAST_FLAP_THRESHOLD
        flap_grace     = c.as_int("fast_flapping_grace") if "fast_flapping_grace" in c else BackboneInterface.FAST_FLAP_GRACE
        flap_expiry    = c.as_float("fast_flapping_block_time")*60 if "fast_flapping_block_time" in c else BackboneInterface.FAST_FLAP_EXPIRY

        if port != None: bindport = port

        self.HW_MTU = BackboneInterface.HW_MTU
        self.online = False
        self.IN  = True
        self.OUT = False
        self.name = name
        self.detached = False
        self.mode = RNS.Interfaces.Interface.Interface.MODE_FULL
        self.spawned_interfaces = []
        self.supports_discovery = True
        self.block_fast_flapping = flap_block
        self.fast_flap_threshold = flap_threshold
        self.fast_flap_grace = flap_grace
        self.fast_flap_expiry = flap_expiry

        if bindport == None: raise SystemError(f"No TCP port configured for interface \"{name}\"")
        else:                self.bind_port = bindport

        bind_address = None
        if device != None:
            bind_address = self.get_address_for_if(device, self.bind_port, prefer_ipv6)
        else:
            if bindip == None:
                raise SystemError(f"No TCP bind IP configured for interface \"{name}\"")
            bind_address = self.get_address_for_host(bindip, self.bind_port, prefer_ipv6)

        if bind_address != None:
            self.receives = True
            self.bind_ip = bind_address[0]
            self.owner = owner

            if len(bind_address) == 2  : BackboneInterface.add_listener(self, bind_address, socket_type=socket.AF_INET)
            elif len(bind_address) == 4: BackboneInterface.add_listener(self, bind_address, socket_type=socket.AF_INET6)

            self.bitrate = self.BITRATE_GUESS
            self.online = True

        else:
            raise SystemError("Insufficient parameters to create listener")

    __ic_burst_stats_throttle = 0.95
    __last_ic_burst_count_check = 0
    __last_ic_burst_count_state = 0
    @property
    def ic_burst_count(self):
        if time.time() > self.__last_ic_burst_count_check + self.__ic_burst_stats_throttle:
            self.__last_ic_burst_count_state = len([i.ic_burst_active for i in self.spawned_interfaces if i.ic_burst_active])
            self.__last_ic_burst_count_check = time.time()

        return self.__last_ic_burst_count_state

    __last_ic_pr_burst_count_check = 0
    __last_ic_pr_burst_count_state = 0
    @property
    def ic_pr_burst_count(self):
        if time.time() > self.__last_ic_pr_burst_count_check + self.__ic_burst_stats_throttle:
            self.__last_ic_pr_burst_count_state = len([i.ic_pr_burst_active for i in self.spawned_interfaces if i.ic_pr_burst_active])
            self.__last_ic_pr_burst_count_check = time.time()

        return self.__last_ic_pr_burst_count_state

    __last_ic_burst_check = 0
    __last_ic_burst_state = False
    @property
    def ic_burst_active(self):
        if time.time() > self.__last_ic_burst_check + self.__ic_burst_stats_throttle:
            self.__last_ic_burst_state = any(i.ic_burst_active for i in self.spawned_interfaces)
            self.__last_ic_burst_check = time.time()

        return self.__last_ic_burst_state

    @ic_burst_active.setter
    def ic_burst_active(self, value): pass
    
    __ic_burst_activated_check = 0
    __ic_burst_activated       = 0
    @property
    def ic_burst_activated(self):
        if time.time() > self.__ic_burst_activated_check + self.__ic_burst_stats_throttle:
            activated = [i.ic_burst_activated for i in self.spawned_interfaces if i.ic_burst_active]
            if activated: self.__ic_burst_activated = min(activated)
            self.__ic_burst_activated_check = time.time()

        return self.__ic_burst_activated

    @ic_burst_activated.setter
    def ic_burst_activated(self, value): pass


    __last_ic_pr_burst_check = 0
    __last_ic_pr_burst_state = False
    @property
    def ic_pr_burst_active(self):
        if time.time() > self.__last_ic_pr_burst_check + self.__ic_burst_stats_throttle:
            self.__last_ic_pr_burst_state = any(i.ic_pr_burst_active for i in self.spawned_interfaces)
            self.__last_ic_pr_burst_check = time.time()

        return self.__last_ic_pr_burst_state

    @ic_pr_burst_active.setter
    def ic_pr_burst_active(self, value): pass
    
    __ic_pr_burst_activated_check = 0
    __ic_pr_burst_activated       = 0
    @property
    def ic_pr_burst_activated(self):
        if time.time() > self.__ic_pr_burst_activated_check + self.__ic_burst_stats_throttle:
            activated = [i.ic_pr_burst_activated for i in self.spawned_interfaces if i.ic_pr_burst_active]
            if activated: self.__ic_pr_burst_activated = min(activated)
            self.__ic_pr_burst_activated_check = time.time()

        return self.__ic_pr_burst_activated

    @ic_pr_burst_activated.setter
    def ic_pr_burst_activated(self, value): pass

    @staticmethod
    def start():
        if not BackboneInterface._job_active:    threading.Thread(target=BackboneInterface.__job, daemon=True).start()
        if not BackboneInterface._ic_job_active: threading.Thread(target=BackboneInterface.__dp_ic_job, daemon=True).start()
        if not BackboneInterface._ec_job_active: threading.Thread(target=BackboneInterface.__dp_ec_job, daemon=True).start()

    @staticmethod
    def ensure_epoll():
        if not BackboneInterface.epoll: BackboneInterface.epoll = select.epoll()

    @staticmethod
    def add_listener(interface, bind_address, socket_type=socket.AF_INET):
        BackboneInterface.ensure_epoll()
        if socket_type == socket.AF_INET:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(bind_address)
        elif socket_type == socket.AF_INET6:
            server_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(bind_address)
        elif socket_type == socket.AF_UNIX:
            server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server_socket.bind(bind_address)
        else: raise TypeError(f"Invalid socket type {socket_type} for {interface}")

        server_socket.listen(1)
        server_socket.setblocking(0)
        BackboneInterface.listener_filenos[server_socket.fileno()] = (interface, server_socket)
        BackboneInterface.epoll.register(server_socket.fileno(), select.EPOLLIN)
        BackboneInterface.start()

    @staticmethod
    def add_client_socket(client_socket, interface):
        BackboneInterface.ensure_epoll()
        BackboneInterface.spawned_interface_filenos[client_socket.fileno()] = interface
        BackboneInterface.register_in(client_socket.fileno())
        BackboneInterface.start()

    @staticmethod
    def register_in(fileno):
        if fileno < 0:
            RNS.log(f"Attempt to register invalid file descriptor {fileno}", RNS.LOG_WARNING)
            return

        try: BackboneInterface.epoll.register(fileno, select.EPOLLIN | select.EPOLLHUP)
        except Exception as e:
            RNS.log(f"An error occurred while registering EPOLLIN for file descriptor {fileno}: {e}", RNS.LOG_WARNING)

    @staticmethod
    def deregister_fileno(fileno):
        if fileno < 0:
            RNS.log(f"Attempt to deregister invalid file descriptor {fileno}", RNS.LOG_DEBUG)
            return

        try: BackboneInterface.epoll.unregister(fileno)
        except Exception as e:
            if   str(e).endswith("No such file or directory"): pass
            elif str(e).endswith("Bad file descriptor"):       pass
            else: RNS.log(f"An error occurred while deregistering file descriptor {fileno}: {e}", RNS.LOG_DEBUG)

    @staticmethod
    def deregister_listeners():
        for fileno in BackboneInterface.listener_filenos:
            owner_interface, server_socket = BackboneInterface.listener_filenos[fileno]
            fileno = server_socket.fileno()
            BackboneInterface.deregister_fileno(fileno)
            server_socket.close()

        BackboneInterface.listener_filenos.clear()

    @staticmethod
    def tx_ready(interface):
        if interface.socket:
            fileno = interface.socket.fileno()
            if fileno in BackboneInterface.spawned_interface_filenos:
                try:
                    events = select.EPOLLOUT | select.EPOLLHUP
                    if not interface.dp_ingress_gated: events |= select.EPOLLIN
                    BackboneInterface.epoll.modify(fileno, events)
                except Exception as e:
                    if   str(e).endswith("No such file or directory"): pass
                    elif str(e).endswith("Bad file descriptor"):       pass
                    else: RNS.log(f"Error occurred on {interface} while modifying socket EPOLL state: {e}", RNS.LOG_WARNING)
                    raise e

    @staticmethod
    def __throttle_ingress(interface, hold=None):
        if interface.dp_ingress_gated: return False
        try:
            fileno = interface.socket.fileno()
            if fileno in BackboneInterface.spawned_interface_filenos:
                interface.dp_ingress_gated = True
                interface.dp_ingress_tcount += 1
                events = select.EPOLLHUP
                if interface.transmit_buffer.sendable > 0: events |= select.EPOLLOUT
                BackboneInterface.epoll.modify(fileno, events)
                if hold: interface.dp_ingress_hold = time.time() + hold
                RNS.log(f"Ingress throttled on {interface}", RNS.LOG_NOTICE) if RNS.sl(RNS.LOG_NOTICE) else None
                return True

        except Exception as e: RNS.log(f"Error throttling {interface}: {e}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
        return False

    @staticmethod
    def __release_ingress(interface):
        if not interface.dp_ingress_gated: return False
        try:
            fileno = interface.socket.fileno()
            if fileno in BackboneInterface.spawned_interface_filenos:
                events = select.EPOLLIN | select.EPOLLHUP
                if interface.transmit_buffer.sendable > 0: events |= select.EPOLLOUT
                BackboneInterface.epoll.modify(fileno, events)
                interface.dp_ingress_gated = False
                RNS.log(f"Released ingress throttle on {interface}", RNS.LOG_NOTICE) if RNS.sl(RNS.LOG_NOTICE) else None
                return True

        except Exception as e: RNS.log(f"Error releasing throttle on {interface}: {e}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
        return False

    @staticmethod
    def _throttle_immediate(q_depth):
        with BackboneInterface._dp_ic_lock:
            st = time.time()
            interfaces = list(BackboneInterface.spawned_interface_filenos.values())
            producers = [iface for iface in interfaces if iface.dp_ingress_packets > 0]

            if producers:
                producers.sort(key=lambda p: p.dp_ingress_packets, reverse=True)
                selected = producers[0]

                now   = time.time()
                span  = now - BackboneInterface._dp_ic_snapshot
                total = sum(iface.dp_ingress_packets for iface in producers)
                avail = sum(iface.dp_ingress_bytes for iface in interfaces) / span
                share = selected.dp_ingress_packets / total
                rate  = selected.dp_ingress_packets / span
                speed = selected.dp_ingress_bytes   / span
                data  = selected.dp_ingress_bytes
                pkts  = selected.dp_ingress_packets
                alloc = 1/((max(len(interfaces), BackboneInterface.DP_IC_IF_HEADROOM))*BackboneInterface.DP_IC_PENALTY)
                hold = (avail/(avail*alloc))*span

                if BackboneInterface.__throttle_ingress(selected, hold=hold):
                    taken = time.time()-st
                    if RNS.sl(RNS.LOG_DEBUG):
                        RNS.log(f"Throttled producer with {pkts} packets at {RNS.prettysize(rate, suffix='pps')} / {RNS.prettyspeed(speed*8)}, {round(share*100.0, 2)}% ingress share", RNS.LOG_DEBUG)
                        RNS.log(f"Available ingress budget {RNS.prettyspeed(avail*8)}, hard-allocated {round(alloc*100.0, 2)}% ({RNS.prettyspeed(avail*alloc*8)}), handled in {RNS.prettyshorttime(taken, compact=True, tight=True)}", RNS.LOG_DEBUG)
                        RNS.log(f"Holding for {RNS.prettyshorttime(hold, compact=True, tight=True)}, throttling handled in {RNS.prettyshorttime(taken, compact=True, tight=True)} at depth {q_depth}", RNS.LOG_DEBUG)

    @staticmethod
    def _dp_ec_evaluate(interface, now):
        tb = interface.transmit_buffer
        drained = tb._tx_sent - interface._dp_ec_prev_sent
        interface._dp_ec_prev_sent = tb._tx_sent

        sendable = tb.sendable
        buffered = len(tb)

        if buffered == 0 or sendable == 0:
            interface._dp_ec_zero_ticks = 0
            interface._dp_ec_last_drain = now
            interface.tx_stalled = False
            return False

        if now - interface._dp_ec_last_drain >= BackboneInterface.DP_EC_DEAD_TIME:
            RNS.log(f"No egress control drain progress for {RNS.prettyshorttime(BackboneInterface.DP_EC_DEAD_TIME, compact=True)} on {interface}, tearing down", RNS.LOG_NOTICE)
            try:
                if hasattr(interface, "socket") and interface.socket:
                    fileno = interface.socket.fileno()
                    BackboneInterface.deregister_fileno(fileno)
                    if fileno in BackboneInterface.spawned_interface_filenos: BackboneInterface.spawned_interface_filenos.pop(fileno)
                    try: interface.socket.close()
                    except Exception as e: RNS.log(f"Egress control could not close socket for {interface}: {e}", RNS.LOG_ERROR)
            except Exception as e: RNS.log(f"Egress control cleanup error for {interface}: {e}", RNS.LOG_ERROR)

            interface.receive(b"")
            return True

        if drained > 0:
            interface._dp_ec_last_drain = now
            interface._dp_ec_zero_ticks = 0
            drain_rate = drained / BackboneInterface.DP_EC_INTERVAL
            clear_eta  = buffered / drain_rate if drain_rate > 0 else float("inf")

            if buffered > BackboneInterface.DP_EC_MID_WM and clear_eta > BackboneInterface.DP_EC_MAX_ETA:
                if not interface.tx_stalled: RNS.log(f"Egress control drain ETA of {RNS.prettyshorttime(clear_eta, compact=True)} exceeds maximum on {interface}, gating outbound", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                interface.tx_stalled = True

            elif clear_eta < BackboneInterface.DP_EC_RELEASE_ETA or buffered <= BackboneInterface.DP_EC_MID_WM:
                if interface.tx_stalled: RNS.log(f"Egress control drain recovered on {interface}, resuming outbound", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                interface.tx_stalled = False

        else:
            # No drain progress on this tick
            if buffered > BackboneInterface.DP_EC_MID_WM:
                interface._dp_ec_zero_ticks += 1
                if interface._dp_ec_zero_ticks >= BackboneInterface.DP_EC_STALL_TICKS:
                    if not interface.tx_stalled: RNS.log(f"No egress control drain progress on {interface}, gating outbound", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                    interface.tx_stalled = True
            else:
                interface._dp_ec_zero_ticks = 0
                interface.tx_stalled = False

        return False

    @staticmethod
    def __dp_ec_job():
        with BackboneInterface._ec_job_lock:
            if BackboneInterface._ec_job_active: return
            else:
                BackboneInterface._ec_job_active = True
                RNS.log(f"Started dataplane egress control", RNS.LOG_DEBUG)
                try:
                    while True:
                        time.sleep(BackboneInterface.DP_EC_INTERVAL)
                        now = time.time()
                        try: interfaces = list(BackboneInterface.spawned_interface_filenos.values())
                        except RuntimeError as e:
                            RNS.log(f"Deferring egress control evaluation due to error: {e}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                            continue

                        for interface in interfaces:
                            if interface.detached: continue
                            if isinstance(interface, RNS.Interfaces.LocalInterface.LocalClientInterface): continue
                            BackboneInterface._dp_ec_evaluate(interface, now)

                except Exception as e:
                    RNS.log(f"BackboneInterface egress control error: {e}", RNS.LOG_ERROR)
                    RNS.trace_exception(e)

    @staticmethod
    def __dp_ic_job():
        with BackboneInterface._ic_job_lock:
            if BackboneInterface._ic_job_active: return
            else:
                BackboneInterface._ic_job_active = True
                RNS.log(f"Started dataplane ingress control: High/mid/low water marks are {BackboneInterface.DP_IC_HIGH_WM}/{BackboneInterface.DP_IC_MID_WM}/{BackboneInterface.DP_IC_LOW_WM} packets", RNS.LOG_DEBUG)
                try:
                    while True:
                        time.sleep(BackboneInterface.DP_IC_INTERVAL)
                        try:
                            if RNS.Transport.inbound_queues != None: q_depth = RNS.Transport.inbound_queues.qsize(RNS.Transport.TC_DATA)
                            else: continue
                        except Exception: continue

                        with BackboneInterface._dp_ic_lock:
                            st = time.time()
                            interfaces = list(BackboneInterface.spawned_interface_filenos.values())

                            if q_depth > BackboneInterface.DP_IC_MID_WM:
                                producers = [iface for iface in interfaces if iface.dp_ingress_packets > 0 and not isinstance(interface, RNS.Interfaces.LocalInterface.LocalClientInterface)]
                                if producers:
                                    producers.sort(key=lambda p: p.dp_ingress_packets, reverse=True)
                                    selected = producers[0]

                                    now   = time.time()
                                    span  = max(now - BackboneInterface._dp_ic_snapshot, 0.001)
                                    total = sum(iface.dp_ingress_packets for iface in producers)
                                    avail = sum(iface.dp_ingress_bytes for iface in interfaces) / span
                                    mean  = total / max(len(producers), 2)
                                    share = selected.dp_ingress_packets / total
                                    rate  = selected.dp_ingress_packets / span
                                    speed = selected.dp_ingress_bytes   / span
                                    data  = selected.dp_ingress_bytes
                                    pkts  = selected.dp_ingress_packets
                                    alloc = 1/((max(len(interfaces), BackboneInterface.DP_IC_IF_HEADROOM))*BackboneInterface.DP_IC_PENALTY)
                                    hold = (avail/max(avail*alloc, 1))*span

                                    if BackboneInterface.__throttle_ingress(selected, hold=hold):
                                        taken = time.time()-st
                                        if RNS.sl(RNS.LOG_DEBUG):
                                            RNS.log(f"Throttled producer with {pkts} packets at {RNS.prettysize(rate, suffix='pps')} / {RNS.prettyspeed(speed*8)}, {round(share*100.0, 2)}% ingress share", RNS.LOG_DEBUG)
                                            RNS.log(f"Available ingress budget {RNS.prettyspeed(avail*8)}, hard-allocated {round(alloc*100.0, 2)}% ({RNS.prettyspeed(avail*alloc*8)}), handled in {RNS.prettyshorttime(taken, compact=True, tight=True)}", RNS.LOG_DEBUG)
                                            RNS.log(f"Holding for {RNS.prettyshorttime(hold, compact=True, tight=True)}, throttling handled in {RNS.prettyshorttime(taken, compact=True, tight=True)}", RNS.LOG_DEBUG)

                            elif q_depth < BackboneInterface.DP_IC_LOW_WM:
                                now = time.time()
                                for iface in interfaces:
                                    if iface.dp_ingress_gated:
                                        if iface.dp_ingress_hold and now < iface.dp_ingress_hold: continue
                                        BackboneInterface.__release_ingress(iface)
                                        break

                            BackboneInterface._dp_ic_snapshot = time.time()
                            for iface in interfaces:
                                iface.dp_ingress_bytes   = 0
                                iface.dp_ingress_packets = 0

                except Exception as e:
                    RNS.log(f"BackboneInterface ingress control error: {e}", RNS.LOG_ERROR)
                    RNS.trace_exception(e)

    @staticmethod
    def __job():
        with BackboneInterface._job_lock:
            if BackboneInterface._job_active: return
            else:
                BackboneInterface._job_active = True
                BackboneInterface.ensure_epoll()
                try:
                    while True:
                        for fileno, event in BackboneInterface.epoll.poll(1):
                            if fileno in BackboneInterface.spawned_interface_filenos:
                                spawned_interface = BackboneInterface.spawned_interface_filenos[fileno]
                                client_socket = spawned_interface.socket
                                socket_valid = client_socket and fileno == client_socket.fileno()
                                if socket_valid and (event & select.EPOLLIN) and not spawned_interface.dp_ingress_gated:
                                    if spawned_interface.dp_ingress_gated: continue
                                    try: received_bytes = client_socket.recv(spawned_interface.HW_MTU)
                                    except Exception as e:
                                        RNS.log(f"Error while reading from {spawned_interface}: {e}", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                        received_bytes = b""

                                    if len(received_bytes):
                                        spawned_interface.dp_ingress_bytes += len(received_bytes)
                                        spawned_interface.receive(received_bytes)
                                    else:
                                        BackboneInterface.deregister_fileno(fileno); client_socket.close()
                                        try:
                                            if fileno in BackboneInterface.spawned_interface_filenos: BackboneInterface.spawned_interface_filenos.pop(fileno)
                                        except Exception as e: RNS.log(f"Error while removing spawned interface file descriptor from BackboneInterface I/O handler: {e}", RNS.LOG_ERROR)

                                        try:
                                            if spawned_interface.parent_interface:
                                                pif = spawned_interface.parent_interface
                                                if pif.spawned_interfaces != None:
                                                    while spawned_interface in pif.spawned_interfaces: pif.spawned_interfaces.remove(spawned_interface)
                                        except Exception as e: RNS.log(f"Error while removing spawned interface from {pif}: {e}", RNS.LOG_ERROR)

                                        spawned_interface.receive(received_bytes)

                                socket_valid_after_read = socket_valid and fileno in BackboneInterface.spawned_interface_filenos
                                if socket_valid_after_read and (event & select.EPOLLOUT):
                                    try: written = spawned_interface.transmit_buffer.drain_to(client_socket)
                                    except Exception as e:
                                        written = 0
                                        if not spawned_interface.detached:
                                            if RNS.sl(RNS.LOG_DEBUG):
                                                if   str(e).endswith("Connection timed out"):     pass
                                                elif str(e).endswith("Connection reset by peer"): pass
                                                elif str(e).endswith("No route to host"):         pass
                                                elif str(e).endswith("Broken pipe"):              pass
                                                else: RNS.log(f"Error while writing to {spawned_interface}: {e}", RNS.LOG_DEBUG)
                                        BackboneInterface.deregister_fileno(fileno)

                                        try:
                                            if fileno in BackboneInterface.spawned_interface_filenos: BackboneInterface.spawned_interface_filenos.pop(fileno)
                                        except Exception as e: RNS.log(f"Error while removing spawned interface file descriptor from BackboneInterface I/O handler: {e}", RNS.LOG_ERROR)
                                        
                                        try:
                                            if spawned_interface.parent_interface:
                                                pif = spawned_interface.parent_interface
                                                if pif.spawned_interfaces != None:
                                                    while spawned_interface in pif.spawned_interfaces: pif.spawned_interfaces.remove(spawned_interface)
                                        except Exception as e: RNS.log(f"Error while removing spawned interface from {pif}: {e}", RNS.LOG_ERROR)

                                        try: client_socket.close()
                                        except Exception as e: RNS.log(f"Error while closing socket for {spawned_interface}: {e}", RNS.LOG_WARNING)
                                        spawned_interface.receive(b"")

                                    try:
                                        if spawned_interface.transmit_buffer.sendable == 0:
                                            events = select.EPOLLHUP
                                            if not spawned_interface.dp_ingress_gated: events |= select.EPOLLIN
                                            BackboneInterface.epoll.modify(fileno, events)
                                    except Exception as e: RNS.log(f"Error while setting EPOLLIN on {spawned_interface}: {e}", RNS.LOG_ERROR)

                                    spawned_interface.txb += written
                                    if spawned_interface.parent_interface: spawned_interface.parent_interface.txb += written
                                
                                elif socket_valid_after_read and (event & select.EPOLLHUP):
                                    BackboneInterface.deregister_fileno(fileno)
                                    try:
                                        if fileno in BackboneInterface.spawned_interface_filenos: BackboneInterface.spawned_interface_filenos.pop(fileno)
                                    except Exception as e: RNS.log(f"Error while removing spawned interface file descriptor from BackboneInterface I/O handler: {e}", RNS.LOG_ERROR)

                                    try:
                                        if spawned_interface.parent_interface:
                                            pif = spawned_interface.parent_interface
                                            if pif.spawned_interfaces != None:
                                                while spawned_interface in pif.spawned_interfaces: pif.spawned_interfaces.remove(spawned_interface)
                                    except Exception as e: RNS.log(f"Error while removing spawned interface from {pif}: {e}", RNS.LOG_ERROR)

                                    try: client_socket.close()
                                    except Exception as e: RNS.log(f"Error while closing socket for {spawned_interface}: {e}", RNS.LOG_ERROR)
                                    spawned_interface.receive(b"")

                            elif fileno in BackboneInterface.listener_filenos:
                                owner_interface, server_socket = BackboneInterface.listener_filenos[fileno]
                                if fileno == server_socket.fileno() and (event & select.EPOLLIN):
                                    try:
                                        client_socket, address = server_socket.accept()
                                        client_socket.setblocking(0)
                                        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BackboneInterface.DP_IC_RCVBUF)
                                        if not owner_interface.incoming_connection(client_socket):
                                            try: client_socket.close()
                                            except Exception as e: RNS.log(f"Error while closing socket for failed incoming connection: {e}", RNS.LOG_WARNING)

                                    except Exception as e:
                                        RNS.log(f"Accepting socket failed for incoming connection: {e}", RNS.LOG_WARNING)
                                        try: client_socket.close()
                                        except Exception as e: RNS.log(f"Error while closing socket for failed incoming socket accept: {e}", RNS.LOG_WARNING)
                                
                                elif fileno == server_socket.fileno() and (event & select.EPOLLHUP):
                                    try: BackboneInterface.deregister_fileno(fileno)
                                    except Exception as e: RNS.log(f"Error while deregistering listener file descriptor {fileno}: {e}", RNS.LOG_ERROR)

                                    try: server_socket.close()
                                    except Exception as e: RNS.log(f"Error while closing listener socket for {server_socket}: {e}", RNS.LOG_WARNING)

                except Exception as e:
                    RNS.log(f"BackboneInterface error: {e}", RNS.LOG_ERROR)
                    RNS.trace_exception(e)

                finally:
                    BackboneInterface.deregister_listeners()
    
    def incoming_connection(self, socket):
        try:
            remote_ip = socket.getpeername()[0]
            remote_port = str(socket.getpeername()[1])
            if self.blocked_ip_count > 0:
                with BackboneInterface.fast_flapping_lock:
                    if remote_ip in BackboneInterface.fast_flapping:
                        now = time.time()
                        ffe = BackboneInterface.fast_flapping[remote_ip]
                        started_flapping = ffe[0]
                        last_flap        = ffe[1]
                        flaps            = ffe[2]
                        if flaps > self.fast_flap_grace:
                            RNS.log(f"Ignoring incoming connection from fast-flapping IP {remote_ip}", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                            return False

            RNS.log("Accepting incoming connection", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
            spawned_configuration = {"name": "Client on "+self.name, "target_host": None, "target_port": None}
            spawned_interface = BackboneClientInterface(self.owner, spawned_configuration, connected_socket=socket)
            spawned_interface.OUT = self.OUT
            spawned_interface.IN  = self.IN

            spawned_interface.ingress_control = self.ingress_control
            spawned_interface.ic_max_held_announces = self.ic_max_held_announces
            spawned_interface.ic_burst_hold = self.ic_burst_hold
            spawned_interface.ic_burst_freq = self.ic_burst_freq
            spawned_interface.ic_burst_freq_new = self.ic_burst_freq_new
            spawned_interface.ic_new_time = self.ic_new_time
            spawned_interface.ic_burst_penalty = self.ic_burst_penalty
            spawned_interface.ic_held_release_interval = self.ic_held_release_interval

            spawned_interface.egress_control = self.egress_control
            spawned_interface.ec_pr_freq = self.ec_pr_freq
            spawned_interface.ic_pr_burst_freq_new = self.ic_pr_burst_freq_new
            spawned_interface.ic_pr_burst_freq = self.ic_pr_burst_freq
            
            spawned_interface.socket = socket
            spawned_interface.target_ip = remote_ip
            spawned_interface.target_port = remote_port
            spawned_interface.parent_interface = self
            spawned_interface.bitrate = self.bitrate
            spawned_interface.optimise_mtu()
            
            spawned_interface.ifac_size = self.ifac_size
            spawned_interface.ifac_netname = self.ifac_netname
            spawned_interface.ifac_netkey = self.ifac_netkey
            if spawned_interface.ifac_netname != None or spawned_interface.ifac_netkey != None:
                ifac_origin = b""
                if spawned_interface.ifac_netname != None: ifac_origin += RNS.Identity.full_hash(spawned_interface.ifac_netname.encode("utf-8"))
                if spawned_interface.ifac_netkey != None:  ifac_origin += RNS.Identity.full_hash(spawned_interface.ifac_netkey.encode("utf-8"))

                ifac_origin_hash = RNS.Identity.full_hash(ifac_origin)
                spawned_interface.ifac_key = RNS.Cryptography.hkdf(length=64, derive_from=ifac_origin_hash,
                                                                   salt=RNS.Reticulum.IFAC_SALT, context=None)
                spawned_interface.ifac_identity = RNS.Identity.from_bytes(spawned_interface.ifac_key)
                spawned_interface.ifac_signature = spawned_interface.ifac_identity.sign(RNS.Identity.full_hash(spawned_interface.ifac_key))

            spawned_interface.announce_rate_target = self.announce_rate_target
            spawned_interface.announce_rate_grace = self.announce_rate_grace
            spawned_interface.announce_rate_penalty = self.announce_rate_penalty
            spawned_interface.mode = self.mode
            spawned_interface.gravity = self.gravity
            spawned_interface.HW_MTU = self.HW_MTU
            RNS.log("Spawned new BackboneClient Interface: "+str(spawned_interface), RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
            RNS.Transport.add_interface(spawned_interface)
            while spawned_interface in self.spawned_interfaces: self.spawned_interfaces.remove(spawned_interface)
            self.spawned_interfaces.append(spawned_interface)
            BackboneInterface.add_client_socket(socket, spawned_interface)
            spawned_interface.spawned_at = time.time()
            spawned_interface.online = True

        except Exception as e:
            RNS.log(f"An error occurred while accepting incoming connection on {self}: {e}", RNS.LOG_ERROR)
            return False

        return True

    def received_announce(self, size=0, from_spawned=False):
        if from_spawned:
            self.ia_freq_deque.append(time.time())
            self.arxb += size

    def sent_announce(self, size=0, from_spawned=False):
        if from_spawned:
            self.oa_freq_deque.append(time.time())
            self.atxb += size

    def received_path_request(self, size=0, from_spawned=False):
        if from_spawned:
            self.ip_freq_deque.append(time.time())
            self.prxb += size

    def sent_path_request(self, size=0, from_spawned=False):
        if from_spawned:
            self.op_freq_deque.append(time.time())
            self.ptxb += size

    def process_outgoing(self, data):
        pass

    def detach(self):
        self.detached = True
        self.online = False
        detached = []
        for fileno in BackboneInterface.listener_filenos:
            owner_interface, listener_socket = BackboneInterface.listener_filenos[fileno]
            if owner_interface == self:
                if hasattr(listener_socket, "shutdown"):
                    if callable(listener_socket.shutdown):
                        try: listener_socket.shutdown(socket.SHUT_RDWR)
                        except Exception as e:
                            if   str(e).endswith("Transport endpoint is not connected"): pass
                            elif str(e).endswith("Bad file descriptor"): pass
                            else: RNS.log("Error while shutting down socket for "+str(self)+": "+str(e), RNS.LOG_ERROR)

    @property
    def blocked_ip_list(self):
        if not self.block_fast_flapping: return []
        else: return [ip for ip in self.fast_flapping if self.fast_flapping[ip][2] > self.fast_flap_grace]

    @property
    def blocked_ip_count(self):
        if not self.block_fast_flapping: return 0
        else:
            count = 0
            expired = []
            now = time.time()
            with BackboneInterface.fast_flapping_lock:
                for remote_ip in BackboneInterface.fast_flapping:
                    ffe              = BackboneInterface.fast_flapping[remote_ip]
                    started_flapping = ffe[0]
                    last_flap        = ffe[1]
                    flaps            = ffe[2]
                    if now - last_flap > self.fast_flap_expiry: expired.append(remote_ip)
                    elif flaps > self.fast_flap_grace: count += 1

                for remote_ip in expired:
                    if remote_ip in BackboneInterface.fast_flapping:
                        try:
                            BackboneInterface.fast_flapping.pop(remote_ip)
                            RNS.log(f"Fast-flapping block expired for {remote_ip}", RNS.LOG_DEBUG)
                        except Exception as e: RNS.log(f"Error while expiring fast-flapping block for {remote_ip}: {e}", RNS.LOG_ERROR)

            return count

    def __str__(self):
        if ":" in self.bind_ip: ip_str = f"[{self.bind_ip}]"
        else:                   ip_str = f"{self.bind_ip}"
        return "BackboneInterface["+self.name+"/"+ip_str+":"+str(self.bind_port)+"]"


class BackboneClientInterface(Interface):
    BITRATE_GUESS = 100_000_000
    DEFAULT_IFAC_SIZE = 16
    AUTOCONFIGURE_MTU = True

    RECONNECT_WAIT = 5
    RECONNECT_MAX_TRIES = None

    # TCP socket options
    TCP_USER_TIMEOUT = 24
    TCP_PROBE_AFTER = 5
    TCP_PROBE_INTERVAL = 2
    TCP_PROBES = 12

    INITIAL_CONNECT_TIMEOUT = 5
    SYNCHRONOUS_START = True

    def __init__(self, owner, configuration, connected_socket=None):
        super().__init__()

        c = Interface.get_config_obj(configuration)
        name = c["name"]
        target_ip = c["target_host"] if "target_host" in c and c["target_host"] != None else None
        target_port = int(c["target_port"]) if "target_port" in c and c["target_host"] != None else None
        i2p_tunneled = c.as_bool("i2p_tunneled") if "i2p_tunneled" in c else False
        connect_timeout = c.as_int("connect_timeout") if "connect_timeout" in c else None
        max_reconnect_tries = c.as_int("max_reconnect_tries") if "max_reconnect_tries" in c else None
        prefer_ipv6  = c.as_bool("prefer_ipv6") if "prefer_ipv6" in c else False
        
        self.HW_MTU           = BackboneInterface.HW_MTU
        self.IN               = True
        self.OUT              = False
        self.socket           = None
        self.parent_interface = None
        self.name             = name
        self.initiator        = False
        self.reconnecting     = False
        self.never_connected  = True
        self.owner            = owner
        self.online           = False
        self.detached         = False
        self.prefer_ipv6      = prefer_ipv6
        self.i2p_tunneled     = i2p_tunneled
        self.mode             = RNS.Interfaces.Interface.Interface.MODE_FULL
        self.bitrate          = BackboneClientInterface.BITRATE_GUESS
        self.transmit_buffer  = TransmitBuffer()
        self.receive_buffer   = ReceiveBuffer(mtu=lambda: self.HW_MTU, min_frame_len=RNS.Reticulum.HEADER_MINSIZE,
                                              max_frame_len=lambda: self.HW_MTU+(getattr(self, "ifac_size", None) or 0),
                                              on_frame=self.process_incoming, on_invalid=self.invalid_frame)
        
        if max_reconnect_tries == None:
            self.max_reconnect_tries = BackboneClientInterface.RECONNECT_MAX_TRIES
        else:
            self.max_reconnect_tries = max_reconnect_tries

        if connected_socket != None:
            self.receives    = True
            self.target_ip   = None
            self.target_port = None
            self.socket      = connected_socket

            self.set_timeouts_linux()
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        elif target_ip != None and target_port != None:
            self.receives    = True
            self.target_ip   = target_ip
            self.target_port = target_port
            self.initiator   = True

            if connect_timeout != None:
                self.connect_timeout = connect_timeout
            else:
                self.connect_timeout = BackboneClientInterface.INITIAL_CONNECT_TIMEOUT
            
            if BackboneClientInterface.SYNCHRONOUS_START:
                self.initial_connect()
            else:
                thread = threading.Thread(target=self.initial_connect)
                thread.daemon = True
                thread.start()
            
    def initial_connect(self):
        if not self.connect(initial=True):
            thread = threading.Thread(target=self.reconnect)
            thread.daemon = True
            thread.start()
        else:
            self.wants_tunnel = True

    def set_timeouts_linux(self):
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT, int(BackboneClientInterface.TCP_USER_TIMEOUT * 1000))
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, int(BackboneClientInterface.TCP_PROBE_AFTER))
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, int(BackboneClientInterface.TCP_PROBE_INTERVAL))
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, int(BackboneClientInterface.TCP_PROBES))

    def detach(self):
        self.online = False
        if self.socket != None:
            if hasattr(self.socket, "close"):
                if callable(self.socket.close):
                    self.detached = True
                    
                    try:
                        if self.socket != None: self.socket.shutdown(socket.SHUT_RDWR)
                    except Exception as e:
                        if   str(e).endswith("Transport endpoint is not connected"): pass
                        elif str(e).endswith("Bad file descriptor"):                 pass
                        else: RNS.log("Error while shutting down socket for "+str(self)+": "+str(e), RNS.LOG_ERROR)

                    try:
                        if self.socket != None: self.socket.close()
                    except Exception as e: RNS.log("Error while closing socket for "+str(self)+": "+str(e), RNS.LOG_ERROR)

                    self.socket = None

    def connect(self, initial=False):
        try:
            if initial:
                RNS.log("Establishing TCP connection for "+str(self)+"...", RNS.LOG_DEBUG)

            address_infos = socket.getaddrinfo(self.target_ip, self.target_port, proto=socket.IPPROTO_TCP)
            address_info  = address_infos[0]
            for entry in address_infos:
                if self.prefer_ipv6 and entry[0] == socket.AF_INET6:
                    address_info = entry; break
                elif not self.prefer_ipv6 and entry[0] == socket.AF_INET:
                    address_info = entry; break

            address_family = address_info[0]
            target_address = address_info[4]

            self.socket = socket.socket(address_family, socket.SOCK_STREAM)
            self.socket.settimeout(BackboneClientInterface.INITIAL_CONNECT_TIMEOUT)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.connect(target_address)
            # TODO: Check missing setblocking(0)
            self.socket.settimeout(None)

            BackboneInterface.add_client_socket(self.socket, self)
            self.online  = True

            if initial:
                RNS.log("TCP connection for "+str(self)+" established", RNS.LOG_DEBUG)
        
        except Exception as e:
            if initial:
                RNS.log("Initial connection for "+str(self)+" could not be established: "+str(e), RNS.LOG_WARNING)
                RNS.log("Leaving unconnected and retrying connection in "+str(BackboneClientInterface.RECONNECT_WAIT)+" seconds.", RNS.LOG_WARNING)
                return False
            
            else:
                raise e

        self.set_timeouts_linux()
        
        self.online  = True
        self.never_connected = False

        return True

    def reconnect(self):
        if self.initiator:
            if not self.reconnecting:
                self.reconnecting = True
                attempts = 0
                while not self.online and not self.detached:
                    time.sleep(BackboneClientInterface.RECONNECT_WAIT)
                    attempts += 1

                    if self.max_reconnect_tries != None and attempts > self.max_reconnect_tries:
                        RNS.log("Max reconnection attempts reached for "+str(self), RNS.LOG_WARNING)
                        self.teardown()
                        break

                    try: self.connect()
                    except Exception as e:
                        RNS.log("Connection attempt for "+str(self)+" failed: "+str(e), RNS.LOG_DEBUG)

                if not self.online: return

                if not self.never_connected:
                    RNS.log("Reconnected socket for "+str(self)+".", RNS.LOG_INFO)

                self.reconnecting = False
                RNS.Transport.synthesize_tunnel(self)

        else:
            RNS.log("Attempt to reconnect on a non-initiator TCP interface. This should not happen.", RNS.LOG_ERROR)
            raise IOError("Attempt to reconnect on a non-initiator TCP interface")

    def process_incoming(self, data):
        if self.online and not self.detached:
            self.rxb += len(data)
            if hasattr(self, "parent_interface") and self.parent_interface != None:
                self.parent_interface.rxb += len(data)

            self.dp_ingress_packets += 1
            self.owner.inbound(data, self)

    def process_outgoing(self, data):
        if self.online and not self.detached:
            try:
                frame = HDLC.frame(data)
                if self.tx_stalled or not self.transmit_buffer.append(frame, self.tx_hwm):
                    self.tx_drops += 1
                    self.tx_dropped_bytes += len(frame)
                    RNS.log(f"Egress control dropping outbound frame of {RNS.prettysize(len(frame))} on {self}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                else: BackboneInterface.tx_ready(self)

            except Exception as e:
                RNS.log("Exception occurred while transmitting via "+str(self)+", tearing down interface", RNS.LOG_ERROR)
                RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                self.teardown()

    def invalid_frame(self, frame_len):
        RNS.log(f"Invalid HDLC frame of {RNS.prettysize(frame_len)} received on {self}, dropping frame", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

    def receive(self, data_in):
        try:
            if len(data_in) > 0: self.receive_buffer.feed(data_in)
            else:
                self.online = False
                if self.initiator and not self.detached:
                    RNS.log("The socket for "+str(self)+" was closed, attempting to reconnect...", RNS.LOG_WARNING)
                    def job(): self.reconnect()
                    threading.Thread(target=job, daemon=True).start()
                else:
                    RNS.log("The socket for remote client "+str(self)+" was closed.", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                    self.teardown()
                
        except Exception as e:
            self.online = False
            RNS.log("An interface error occurred for "+str(self)+", the contained exception was: "+str(e), RNS.LOG_WARNING)

            if self.initiator:
                RNS.log("Attempting to reconnect...", RNS.LOG_WARNING)
                def job(): self.reconnect()
                threading.Thread(target=job, daemon=True).start()
            else: self.teardown()

    def teardown(self):
        if self.initiator and not self.detached:
            RNS.log("The interface "+str(self)+" experienced an unrecoverable error and is being torn down. Restart Reticulum to attempt to open this interface again.", RNS.LOG_ERROR)
            if RNS.Reticulum.panic_on_interface_error: RNS.panic()

        else:
            RNS.log("The interface "+str(self)+" is being torn down.", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
            if self.parent_interface and self.parent_interface.block_fast_flapping and hasattr(self, "spawned_at"):
                connected_time = time.time() - self.spawned_at
                if connected_time < self.parent_interface.fast_flap_threshold:
                    try:
                        now = time.time()
                        remote_id = f"{self.target_ip}"
                        with BackboneInterface.fast_flapping_lock:
                            if remote_id in BackboneInterface.fast_flapping: ffe = BackboneInterface.fast_flapping[remote_id]
                            else:                                            ffe = [now, now, 0]
                        ffe[1]  = now
                        ffe[2] += 1
                        with BackboneInterface.fast_flapping_lock: BackboneInterface.fast_flapping[remote_id] = ffe

                        dt  = now-ffe[0]; fff = ffe[2]/dt if dt > 0 else None
                        freq_str = f" at {RNS.prettyfrequency(fff)}" if fff else ""
                        RNS.log(f"{self} is fast flapping{freq_str}, connection time was {RNS.prettytime(connected_time)}, {ffe[2]} fast flaps", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                        if ffe[2] > self.parent_interface.fast_flap_grace: RNS.log(f"Ignoring further connections from {remote_id} due to fast-flapping", RNS.LOG_WARNING)

                    except Exception as e: RNS.log(f"Error while updating fast-flapping interface statistics: {e}", RNS.LOG_ERROR)

        self.online = False
        self.OUT = False
        self.IN = False

        if hasattr(self, "parent_interface") and self.parent_interface != None:
            while self in self.parent_interface.spawned_interfaces:
                self.parent_interface.spawned_interfaces.remove(self)

        if not self.initiator:
            RNS.Transport.remove_interface(self)


    def __str__(self):
        if ":" in self.target_ip: ip_str = f"[{self.target_ip}]"
        else: ip_str = f"{self.target_ip}"
        return "BackboneInterface["+str(self.name)+"/"+ip_str+":"+str(self.target_port)+"]"