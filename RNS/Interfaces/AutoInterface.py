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

from .Interface import Interface
from collections import deque
import socketserver
import threading
import re
import socket
import struct
import time
import sys
import RNS


class AutoInterface(Interface):
    DEFAULT_DISCOVERY_PORT = 29716
    DEFAULT_DATA_PORT      = 42671
    DEFAULT_GROUP_ID       = b"reticulum"

    SCOPE_LINK         = "2"
    SCOPE_ADMIN        = "4"
    SCOPE_SITE         = "5"
    SCOPE_ORGANISATION = "8"
    SCOPE_GLOBAL       = "e"

    MULTICAST_PERMANENT_ADDRESS_TYPE = "0"
    MULTICAST_TEMPORARY_ADDRESS_TYPE = "1"

    PEERING_TIMEOUT    = 7.5

    ALL_IGNORE_IFS     = ["lo0"]
    DARWIN_IGNORE_IFS  = ["awdl0", "llw0", "lo0", "en5"]
    ANDROID_IGNORE_IFS = ["dummy0", "lo", "tun0"]

    BITRATE_GUESS      = 10*1000*1000

    MULTI_IF_DEQUE_LEN = 48
    MULTI_IF_DEQUE_TTL = 0.75

    def handler_factory(self, callback):
        def create_handler(*args, **keys):
            return AutoInterfaceHandler(callback, *args, **keys)
        return create_handler

    def descope_linklocal(self, link_local_addr):
        # Drop scope specifier expressd as %ifname (macOS)
        link_local_addr = link_local_addr.split("%")[0]
        # Drop embedded scope specifier (NetBSD, OpenBSD)
        link_local_addr = re.sub(r"fe80:[0-9a-f]*::","fe80::", link_local_addr)
        return link_local_addr

    def list_interfaces(self):
        ifs = self.netinfo.interfaces()
        return ifs

    def list_addresses(self, ifname):
        ifas = self.netinfo.ifaddresses(ifname)
        return ifas

    def interface_name_to_index(self, ifname):

        # socket.if_nametoindex doesn't work with uuid interface names on windows, it wants the ethernet_0 style
        # we will just get the index from netinfo instead as it seems to work
        if RNS.vendor.platformutils.is_windows():
            return self.netinfo.interface_names_to_indexes()[ifname]

        return socket.if_nametoindex(ifname)

    def __init__(self, owner, name, group_id=None, discovery_scope=None, discovery_port=None, multicast_address_type=None, data_port=None, allowed_interfaces=None, ignored_interfaces=None, configured_bitrate=None):
        from RNS.vendor.ifaddr import niwrapper
        super().__init__()
        self.netinfo = niwrapper

        self.HW_MTU = 1064

        self.IN  = True
        self.OUT = False
        self.name = name
        self.online = False
        self.peers = {}
        self.link_local_addresses = []
        self.adopted_interfaces = {}
        self.interface_servers = {}
        self.multicast_echoes = {}
        self.timed_out_interfaces = {}
        self.mif_deque = deque(maxlen=AutoInterface.MULTI_IF_DEQUE_LEN)
        self.mif_deque_times = deque(maxlen=AutoInterface.MULTI_IF_DEQUE_LEN)
        self.carrier_changed = False

        self.outbound_udp_socket = None

        self.announce_rate_target = None
        self.announce_interval = AutoInterface.PEERING_TIMEOUT/6.0
        self.peer_job_interval = AutoInterface.PEERING_TIMEOUT*1.1
        self.peering_timeout   = AutoInterface.PEERING_TIMEOUT
        self.multicast_echo_timeout = AutoInterface.PEERING_TIMEOUT/2

        # Increase peering timeout on Android, due to potential
        # low-power modes implemented on many chipsets.
        if RNS.vendor.platformutils.is_android():
            self.peering_timeout *= 3

        if allowed_interfaces == None:
            self.allowed_interfaces = []
        else:
            self.allowed_interfaces = allowed_interfaces

        if ignored_interfaces == None:
            self.ignored_interfaces = []
        else:
            self.ignored_interfaces = ignored_interfaces

        if group_id == None:
            self.group_id = AutoInterface.DEFAULT_GROUP_ID
        else:
            self.group_id = group_id.encode("utf-8")

        if discovery_port == None:
            self.discovery_port = AutoInterface.DEFAULT_DISCOVERY_PORT
        else:
            self.discovery_port = discovery_port

        if multicast_address_type == None:
            self.multicast_address_type = AutoInterface.MULTICAST_TEMPORARY_ADDRESS_TYPE
        elif str(multicast_address_type).lower() == "temporary":
            self.multicast_address_type = AutoInterface.MULTICAST_TEMPORARY_ADDRESS_TYPE
        elif str(multicast_address_type).lower() == "permanent":
            self.multicast_address_type = AutoInterface.MULTICAST_PERMANENT_ADDRESS_TYPE
        else:
            self.multicast_address_type = AutoInterface.MULTICAST_TEMPORARY_ADDRESS_TYPE

        if data_port == None:
            self.data_port = AutoInterface.DEFAULT_DATA_PORT
        else:
            self.data_port = data_port

        if discovery_scope == None:
            self.discovery_scope = AutoInterface.SCOPE_LINK
        elif str(discovery_scope).lower() == "link":
            self.discovery_scope = AutoInterface.SCOPE_LINK
        elif str(discovery_scope).lower() == "admin":
            self.discovery_scope = AutoInterface.SCOPE_ADMIN
        elif str(discovery_scope).lower() == "site":
            self.discovery_scope = AutoInterface.SCOPE_SITE
        elif str(discovery_scope).lower() == "organisation":
            self.discovery_scope = AutoInterface.SCOPE_ORGANISATION
        elif str(discovery_scope).lower() == "global":
            self.discovery_scope = AutoInterface.SCOPE_GLOBAL

        self.group_hash = RNS.Identity.full_hash(self.group_id)
        g = self.group_hash
        #gt  = f"{g[1] + (g[0] << 8):02x}"
        gt  = "0"
        gt += f":{g[3] + (g[2] << 8):02x}"
        gt += f":{g[5] + (g[4] << 8):02x}"
        gt += f":{g[7] + (g[6] << 8):02x}"
        gt += f":{g[9] + (g[8] << 8):02x}"
        gt += f":{g[11] + (g[10] << 8):02x}"
        gt += f":{g[13] + (g[12] << 8):02x}"
        self.mcast_discovery_address = f"ff{self.multicast_address_type}{self.discovery_scope}:{gt}"

        suitable_interfaces = 0
        for ifname in self.list_interfaces():
            try:
                if RNS.vendor.platformutils.is_darwin() and ifname in AutoInterface.DARWIN_IGNORE_IFS and not ifname in self.allowed_interfaces:
                    RNS.log(f"{self} skipping Darwin AWDL or tethering interface {ifname}", RNS.LOG_EXTREME)
                elif RNS.vendor.platformutils.is_darwin() and ifname == "lo0":
                    RNS.log(f"{self} skipping Darwin loopback interface {ifname}", RNS.LOG_EXTREME)
                elif RNS.vendor.platformutils.is_android() and ifname in AutoInterface.ANDROID_IGNORE_IFS and not ifname in self.allowed_interfaces:
                    RNS.log(f"{self} skipping Android system interface {ifname}", RNS.LOG_EXTREME)
                elif ifname in self.ignored_interfaces:
                    RNS.log(f"{self} ignoring disallowed interface {ifname}", RNS.LOG_EXTREME)
                elif ifname in AutoInterface.ALL_IGNORE_IFS:
                    RNS.log(f"{self} skipping interface {ifname}", RNS.LOG_EXTREME)
                else:
                    if len(self.allowed_interfaces) > 0 and not ifname in self.allowed_interfaces:
                        RNS.log(f"{self} ignoring interface {ifname} since it was not allowed", RNS.LOG_EXTREME)
                    else:
                        addresses = self.list_addresses(ifname)
                        if self.netinfo.AF_INET6 in addresses:
                            link_local_addr = None
                            for address in addresses[self.netinfo.AF_INET6]:
                                if "addr" in address:
                                    if address["addr"].startswith("fe80:"):
                                        link_local_addr = self.descope_linklocal(address["addr"])
                                        self.link_local_addresses.append(link_local_addr)
                                        self.adopted_interfaces[ifname] = link_local_addr
                                        self.multicast_echoes[ifname] = time.time()
                                        nice_name = self.netinfo.interface_name_to_nice_name(ifname)
                                        if nice_name != None and nice_name != ifname:
                                            RNS.log(f"{self} Selecting link-local address {link_local_addr} for interface {nice_name} / {ifname}", RNS.LOG_EXTREME)
                                        else:
                                            RNS.log(f"{self} Selecting link-local address {link_local_addr} for interface {ifname}", RNS.LOG_EXTREME)

                            if link_local_addr == None:
                                RNS.log(f"{self} No link-local IPv6 address configured for {ifname}, skipping interface", RNS.LOG_EXTREME)
                            else:
                                mcast_addr = self.mcast_discovery_address
                                RNS.log(f"{self} Creating multicast discovery listener on {ifname} with address {mcast_addr}", RNS.LOG_EXTREME)

                                # Struct with interface index
                                if_struct = struct.pack("I", self.interface_name_to_index(ifname))

                                # Set up multicast socket
                                discovery_socket = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                                discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                                if hasattr(socket, "SO_REUSEPORT"):
                                    discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                                discovery_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, if_struct)

                                # Join multicast group
                                mcast_group = socket.inet_pton(socket.AF_INET6, mcast_addr) + if_struct
                                discovery_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mcast_group)

                                # Bind socket
                                if RNS.vendor.platformutils.is_windows():

                                    # window throws "[WinError 10049] The requested address is not valid in its context"
                                    # when trying to use the multicast address as host, or when providing interface index
                                    # passing an empty host appears to work, but probably not exactly how we want it to...
                                    discovery_socket.bind(('', self.discovery_port))

                                else:

                                    if self.discovery_scope == AutoInterface.SCOPE_LINK:
                                        addr_info = socket.getaddrinfo(f"{mcast_addr}%{ifname}", self.discovery_port, socket.AF_INET6, socket.SOCK_DGRAM)
                                    else:
                                        addr_info = socket.getaddrinfo(mcast_addr, self.discovery_port, socket.AF_INET6, socket.SOCK_DGRAM)

                                    discovery_socket.bind(addr_info[0][4])

                                # Set up thread for discovery packets
                                def discovery_loop():
                                    self.discovery_handler(discovery_socket, ifname)

                                thread = threading.Thread(target=discovery_loop)
                                thread.daemon = True
                                thread.start()

                                suitable_interfaces += 1

            except Exception as e:
                nice_name = self.netinfo.interface_name_to_nice_name(ifname)
                if nice_name != None and nice_name != ifname:
                    RNS.log(f"Could not configure the system interface {nice_name} / {ifname} for use with {self}, skipping it. The contained exception was: {e}", RNS.LOG_ERROR)
                else:
                    RNS.log(f"Could not configure the system interface {ifname} for use with {self}, skipping it. The contained exception was: {e}", RNS.LOG_ERROR)

        if suitable_interfaces == 0:
            RNS.log(f"{self} could not autoconfigure. This interface currently provides no connectivity.", RNS.LOG_WARNING)
        else:
            self.receives = True

            if configured_bitrate != None:
                self.bitrate = configured_bitrate
            else:
                self.bitrate = AutoInterface.BITRATE_GUESS

            peering_wait = self.announce_interval*1.2
            RNS.log(f"{self} discovering peers for {round(peering_wait, 2)} seconds...", RNS.LOG_VERBOSE)

            self.owner = owner
            socketserver.UDPServer.address_family = socket.AF_INET6

            for ifname in self.adopted_interfaces:
                local_addr = f"{self.adopted_interfaces[ifname]}%{self.interface_name_to_index(ifname)}"
                addr_info = socket.getaddrinfo(local_addr, self.data_port, socket.AF_INET6, socket.SOCK_DGRAM)
                address = addr_info[0][4]

                udp_server = socketserver.UDPServer(address, self.handler_factory(self.processIncoming))
                self.interface_servers[ifname] = udp_server

                thread = threading.Thread(target=udp_server.serve_forever)
                thread.daemon = True
                thread.start()

            job_thread = threading.Thread(target=self.peer_jobs)
            job_thread.daemon = True
            job_thread.start()

            time.sleep(peering_wait)

            self.online = True


    def discovery_handler(self, socket, ifname):
        def announce_loop():
            self.announce_handler(ifname)

        thread = threading.Thread(target=announce_loop)
        thread.daemon = True
        thread.start()

        while True:
            data, ipv6_src = socket.recvfrom(1024)
            expected_hash = RNS.Identity.full_hash(self.group_id+ipv6_src[0].encode("utf-8"))
            if data == expected_hash:
                self.add_peer(ipv6_src[0], ifname)
            else:
                RNS.log(f"{self} received peering packet on {ifname} from {ipv6_src[0]}, but authentication hash was incorrect.", RNS.LOG_DEBUG)

    def peer_jobs(self):
        while True:
            time.sleep(self.peer_job_interval)
            now = time.time()
            timed_out_peers = []

            # Check for timed out peers
            for peer_addr in self.peers:
                peer = self.peers[peer_addr]
                last_heard = peer[1]
                if now > last_heard+self.peering_timeout:
                    timed_out_peers.append(peer_addr)

            # Remove any timed out peers
            for peer_addr in timed_out_peers:
                removed_peer = self.peers.pop(peer_addr)
                RNS.log(f"{self} removed peer {peer_addr} on {removed_peer[0]}", RNS.LOG_DEBUG)

            for ifname in self.adopted_interfaces:
                # Check that the link-local address has not changed
                try:
                    addresses = self.list_addresses(ifname)
                    if self.netinfo.AF_INET6 in addresses:
                        link_local_addr = None
                        for address in addresses[self.netinfo.AF_INET6]:
                            if "addr" in address:
                                if address["addr"].startswith("fe80:"):
                                    link_local_addr = self.descope_linklocal(address["addr"])
                                    if link_local_addr != self.adopted_interfaces[ifname]:
                                        old_link_local_address = self.adopted_interfaces[ifname]
                                        RNS.log(f"Replacing link-local address {old_link_local_address} for {ifname} with {link_local_addr}", RNS.LOG_DEBUG)
                                        self.adopted_interfaces[ifname] = link_local_addr
                                        self.link_local_addresses.append(link_local_addr)

                                        if old_link_local_address in self.link_local_addresses:
                                            self.link_local_addresses.remove(old_link_local_address)

                                        local_addr = f"{link_local_addr}%{ifname}"
                                        addr_info = socket.getaddrinfo(local_addr, self.data_port, socket.AF_INET6, socket.SOCK_DGRAM)
                                        listen_address = addr_info[0][4]

                                        if ifname in self.interface_servers:
                                            RNS.log(f"Shutting down previous UDP listener for {self} {ifname}", RNS.LOG_DEBUG)
                                            previous_server = self.interface_servers[ifname]
                                            def shutdown_server():
                                                previous_server.shutdown()
                                            threading.Thread(target=shutdown_server, daemon=True).start()

                                        RNS.log(f"Starting new UDP listener for {self} {ifname}", RNS.LOG_DEBUG)

                                        udp_server = socketserver.UDPServer(listen_address, self.handler_factory(self.processIncoming))
                                        self.interface_servers[ifname] = udp_server

                                        thread = threading.Thread(target=udp_server.serve_forever)
                                        thread.daemon = True
                                        thread.start()

                                        self.carrier_changed = True

                except Exception as e:
                    RNS.log(f"Could not get device information while updating link-local addresses for {self}. The contained exception was: {e}", RNS.LOG_ERROR)

                # Check multicast echo timeouts
                last_multicast_echo = 0
                if ifname in self.multicast_echoes:
                    last_multicast_echo = self.multicast_echoes[ifname]

                if now - last_multicast_echo > self.multicast_echo_timeout:
                    if ifname in self.timed_out_interfaces and self.timed_out_interfaces[ifname] == False:
                        self.carrier_changed = True
                        RNS.log(f"Multicast echo timeout for {ifname}. Carrier lost.", RNS.LOG_WARNING)
                    self.timed_out_interfaces[ifname] = True
                else:
                    if ifname in self.timed_out_interfaces and self.timed_out_interfaces[ifname] == True:
                        self.carrier_changed = True
                        RNS.log(f"{self} Carrier recovered on {ifname}", RNS.LOG_WARNING)
                    self.timed_out_interfaces[ifname] = False


    def announce_handler(self, ifname):
        while True:
            self.peer_announce(ifname)
            time.sleep(self.announce_interval)

    def peer_announce(self, ifname):
        try:
            link_local_address = self.adopted_interfaces[ifname]
            discovery_token = RNS.Identity.full_hash(self.group_id+link_local_address.encode("utf-8"))
            announce_socket = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            addr_info = socket.getaddrinfo(self.mcast_discovery_address, self.discovery_port, socket.AF_INET6, socket.SOCK_DGRAM)

            ifis = struct.pack("I", self.interface_name_to_index(ifname))
            announce_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, ifis)
            announce_socket.sendto(discovery_token, addr_info[0][4])
            announce_socket.close()

        except Exception as e:
            if (ifname in self.timed_out_interfaces and self.timed_out_interfaces[ifname] == False) or not ifname in self.timed_out_interfaces:
                RNS.log(f"{self} Detected possible carrier loss on {ifname}: {e}", RNS.LOG_WARNING)
            else:
                pass

    def add_peer(self, addr, ifname):
        if addr in self.link_local_addresses:
            ifname = None
            for interface_name in self.adopted_interfaces:
                if self.adopted_interfaces[interface_name] == addr:
                    ifname = interface_name

            if ifname != None:
                self.multicast_echoes[ifname] = time.time()
            else:
                RNS.log(f"{self} received multicast echo on unexpected interface {ifname}", RNS.LOG_WARNING)

        else:
            if not addr in self.peers:
                self.peers[addr] = [ifname, time.time()]
                RNS.log(f"{self} added peer {addr} on {ifname}", RNS.LOG_DEBUG)
            else:
                self.refresh_peer(addr)

    def refresh_peer(self, addr):
        self.peers[addr][1] = time.time()

    def processIncoming(self, data):
        data_hash = RNS.Identity.full_hash(data)
        deque_hit = False
        if data_hash in self.mif_deque:
            for te in self.mif_deque_times:
                if te[0] == data_hash and time.time() < te[1]+AutoInterface.MULTI_IF_DEQUE_TTL:
                    deque_hit = True
                    break

        if not deque_hit:
            self.mif_deque.append(data_hash)
            self.mif_deque_times.append([data_hash, time.time()])
            self.rxb += len(data)
            self.owner.inbound(data, self)

    def processOutgoing(self,data):
            for peer in self.peers:
                try:
                    if self.outbound_udp_socket == None:
                        self.outbound_udp_socket = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)

                    peer_addr = f"{peer}%{self.interface_name_to_index(self.peers[peer][0])}"
                    addr_info = socket.getaddrinfo(peer_addr, self.data_port, socket.AF_INET6, socket.SOCK_DGRAM)
                    self.outbound_udp_socket.sendto(data, addr_info[0][4])

                except Exception as e:
                    RNS.log(f"Could not transmit on {self}. The contained exception was: {e}", RNS.LOG_ERROR)


            self.txb += len(data)


    # Until per-device sub-interfacing is implemented,
    # ingress limiting should be disabled on AutoInterface
    def should_ingress_limit(self):
        return False

    def __str__(self):
        return f"AutoInterface[{self.name}]"

class AutoInterfaceHandler(socketserver.BaseRequestHandler):
    def __init__(self, callback, *args, **keys):
        self.callback = callback
        socketserver.BaseRequestHandler.__init__(self, *args, **keys)

    def handle(self):
        data = self.request[0]
        self.callback(data)
