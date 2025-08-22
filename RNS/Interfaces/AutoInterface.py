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
    HW_MTU = 1196
    FIXED_MTU = True

    DEFAULT_DISCOVERY_PORT = 29716
    DEFAULT_DATA_PORT      = 42671
    DEFAULT_GROUP_ID       = "reticulum".encode("utf-8")
    DEFAULT_IFAC_SIZE      = 16

    SCOPE_LINK         = "2"
    SCOPE_ADMIN        = "4"
    SCOPE_SITE         = "5"
    SCOPE_ORGANISATION = "8"
    SCOPE_GLOBAL       = "e"

    MULTICAST_PERMANENT_ADDRESS_TYPE = "0"
    MULTICAST_TEMPORARY_ADDRESS_TYPE = "1"

    PEERING_TIMEOUT    = 10.0

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

    def __init__(self, owner, configuration):
        c                      = Interface.get_config_obj(configuration)
        name                   = c["name"]
        group_id               = c["group_id"] if "group_id" in c else None
        discovery_scope        = c["discovery_scope"] if "discovery_scope" in c else None
        discovery_port         = int(c["discovery_port"]) if "discovery_port" in c else None
        multicast_address_type = c["multicast_address_type"] if "multicast_address_type" in c else None
        data_port              = int(c["data_port"]) if "data_port" in c else None
        allowed_interfaces     = c.as_list("devices") if "devices" in c else None
        ignored_interfaces     = c.as_list("ignored_devices") if "ignored_devices" in c else None
        configured_bitrate     = c["configured_bitrate"] if "configured_bitrate" in c else None

        from RNS.Interfaces import netinfo
        super().__init__()
        self.netinfo = netinfo

        self.HW_MTU = AutoInterface.HW_MTU
        self.IN  = True
        self.OUT = False
        self.name = name
        self.owner = owner
        self.online = False
        self.final_init_done = False
        self.peers = {}
        self.link_local_addresses = []
        self.adopted_interfaces = {}
        self.interface_servers = {}
        self.multicast_echoes = {}
        self.timed_out_interfaces = {}
        self.spawned_interfaces = {}
        self.write_lock = threading.Lock()
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
            self.peering_timeout *= 2.5

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
        #gt  = "{:02x}".format(g[1]+(g[0]<<8))
        gt  = "0"
        gt += ":"+"{:02x}".format(g[3]+(g[2]<<8))
        gt += ":"+"{:02x}".format(g[5]+(g[4]<<8))
        gt += ":"+"{:02x}".format(g[7]+(g[6]<<8))
        gt += ":"+"{:02x}".format(g[9]+(g[8]<<8))
        gt += ":"+"{:02x}".format(g[11]+(g[10]<<8))
        gt += ":"+"{:02x}".format(g[13]+(g[12]<<8))
        self.mcast_discovery_address = "ff"+self.multicast_address_type+self.discovery_scope+":"+gt

        suitable_interfaces = 0
        for ifname in self.list_interfaces():
            try:
                if RNS.vendor.platformutils.is_darwin() and ifname in AutoInterface.DARWIN_IGNORE_IFS and not ifname in self.allowed_interfaces:
                    RNS.log(str(self)+" skipping Darwin AWDL or tethering interface "+str(ifname), RNS.LOG_EXTREME)
                elif RNS.vendor.platformutils.is_darwin() and ifname == "lo0":
                    RNS.log(str(self)+" skipping Darwin loopback interface "+str(ifname), RNS.LOG_EXTREME)
                elif RNS.vendor.platformutils.is_android() and ifname in AutoInterface.ANDROID_IGNORE_IFS and not ifname in self.allowed_interfaces:
                    RNS.log(str(self)+" skipping Android system interface "+str(ifname), RNS.LOG_EXTREME)
                elif ifname in self.ignored_interfaces:
                    RNS.log(str(self)+" ignoring disallowed interface "+str(ifname), RNS.LOG_EXTREME)
                elif ifname in AutoInterface.ALL_IGNORE_IFS:
                    RNS.log(str(self)+" skipping interface "+str(ifname), RNS.LOG_EXTREME)
                else:
                    if len(self.allowed_interfaces) > 0 and not ifname in self.allowed_interfaces:
                        RNS.log(str(self)+" ignoring interface "+str(ifname)+" since it was not allowed", RNS.LOG_EXTREME)
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
                                RNS.log(str(self)+" No link-local IPv6 address configured for "+str(ifname)+", skipping interface", RNS.LOG_EXTREME)
                            else:
                                mcast_addr = self.mcast_discovery_address
                                RNS.log(str(self)+" Creating multicast discovery listener on "+str(ifname)+" with address "+str(mcast_addr), RNS.LOG_EXTREME)

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
                                        addr_info = socket.getaddrinfo(mcast_addr+"%"+ifname, self.discovery_port, socket.AF_INET6, socket.SOCK_DGRAM)
                                    else:
                                        addr_info = socket.getaddrinfo(mcast_addr, self.discovery_port, socket.AF_INET6, socket.SOCK_DGRAM)

                                    discovery_socket.bind(addr_info[0][4])

                                # Set up thread for discovery packets
                                def discovery_loop(): self.discovery_handler(discovery_socket, ifname)

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
            RNS.log(str(self)+" could not autoconfigure. This interface currently provides no connectivity.", RNS.LOG_WARNING)
        else:
            self.receives = True

            if configured_bitrate != None:
                self.bitrate = configured_bitrate
            else:
                self.bitrate = AutoInterface.BITRATE_GUESS

    def final_init(self):
        peering_wait = self.announce_interval*1.2
        RNS.log(str(self)+" discovering peers for "+str(round(peering_wait, 2))+" seconds...", RNS.LOG_VERBOSE)

        socketserver.UDPServer.address_family = socket.AF_INET6

        for ifname in self.adopted_interfaces:
            local_addr = self.adopted_interfaces[ifname]+"%"+str(self.interface_name_to_index(ifname))
            addr_info = socket.getaddrinfo(local_addr, self.data_port, socket.AF_INET6, socket.SOCK_DGRAM)
            address = addr_info[0][4]

            udp_server = socketserver.UDPServer(address, self.handler_factory(self.process_incoming))
            self.interface_servers[ifname] = udp_server
            
            thread = threading.Thread(target=udp_server.serve_forever)
            thread.daemon = True
            thread.start()

        job_thread = threading.Thread(target=self.peer_jobs)
        job_thread.daemon = True
        job_thread.start()

        time.sleep(peering_wait)

        self.online = True
        self.final_init_done = True

    def discovery_handler(self, socket, ifname):
        def announce_loop():
            self.announce_handler(ifname)
            
        thread = threading.Thread(target=announce_loop)
        thread.daemon = True
        thread.start()
        
        while True:
            data, ipv6_src = socket.recvfrom(1024)
            if self.final_init_done:
                peering_hash = data[:RNS.Identity.HASHLENGTH//8]
                expected_hash = RNS.Identity.full_hash(self.group_id+ipv6_src[0].encode("utf-8"))
                if peering_hash == expected_hash:
                    self.add_peer(ipv6_src[0], ifname)
                else:
                    RNS.log(str(self)+" received peering packet on "+str(ifname)+" from "+str(ipv6_src[0])+", but authentication hash was incorrect.", RNS.LOG_DEBUG)

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
                if peer_addr in self.spawned_interfaces:
                    spawned_interface = self.spawned_interfaces[peer_addr]
                    spawned_interface.detach()
                    spawned_interface.teardown()
                RNS.log(str(self)+" removed peer "+str(peer_addr)+" on "+str(removed_peer[0]), RNS.LOG_DEBUG)

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
                                        RNS.log("Replacing link-local address "+str(old_link_local_address)+" for "+str(ifname)+" with "+str(link_local_addr), RNS.LOG_DEBUG)
                                        self.adopted_interfaces[ifname] = link_local_addr
                                        self.link_local_addresses.append(link_local_addr)

                                        if old_link_local_address in self.link_local_addresses:
                                            self.link_local_addresses.remove(old_link_local_address)

                                        local_addr = link_local_addr+"%"+ifname
                                        addr_info = socket.getaddrinfo(local_addr, self.data_port, socket.AF_INET6, socket.SOCK_DGRAM)
                                        listen_address = addr_info[0][4]

                                        if ifname in self.interface_servers:
                                            RNS.log("Shutting down previous UDP listener for "+str(self)+" "+str(ifname), RNS.LOG_DEBUG)
                                            previous_server = self.interface_servers[ifname]
                                            def shutdown_server():
                                                previous_server.shutdown()
                                            threading.Thread(target=shutdown_server, daemon=True).start()

                                        RNS.log("Starting new UDP listener for "+str(self)+" "+str(ifname), RNS.LOG_DEBUG)

                                        udp_server = socketserver.UDPServer(listen_address, self.handler_factory(self.process_incoming))
                                        self.interface_servers[ifname] = udp_server

                                        thread = threading.Thread(target=udp_server.serve_forever)
                                        thread.daemon = True
                                        thread.start()

                                        self.carrier_changed = True

                except Exception as e:
                    RNS.log("Could not get device information while updating link-local addresses for "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

                # Check multicast echo timeouts
                last_multicast_echo = 0
                if ifname in self.multicast_echoes:
                    last_multicast_echo = self.multicast_echoes[ifname]

                if now - last_multicast_echo > self.multicast_echo_timeout:
                    if ifname not in self.timed_out_interfaces or self.timed_out_interfaces[ifname] == False:
                        self.carrier_changed = True
                        RNS.log("Multicast echo timeout for "+str(ifname)+". Carrier lost.", RNS.LOG_WARNING)
                    self.timed_out_interfaces[ifname] = True
                else:
                    if ifname in self.timed_out_interfaces and self.timed_out_interfaces[ifname] == True:
                        self.carrier_changed = True
                        RNS.log(str(self)+" Carrier recovered on "+str(ifname), RNS.LOG_WARNING)
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
                RNS.log(str(self)+" Detected possible carrier loss on "+str(ifname)+": "+str(e), RNS.LOG_WARNING)
            else:
                pass

    @property
    def peer_count(self):
        return len(self.spawned_interfaces)

    def add_peer(self, addr, ifname):
        if addr in self.link_local_addresses:
            ifname = None
            for interface_name in self.adopted_interfaces:
                if self.adopted_interfaces[interface_name] == addr:
                    ifname = interface_name

            if ifname != None:
                self.multicast_echoes[ifname] = time.time()
            else:
                RNS.log(str(self)+" received multicast echo on unexpected interface "+str(ifname), RNS.LOG_WARNING)

        else:
            if not addr in self.peers:
                self.peers[addr] = [ifname, time.time()]

                spawned_interface = AutoInterfacePeer(self, addr, ifname)
                spawned_interface.OUT = self.OUT
                spawned_interface.IN  = self.IN
                spawned_interface.parent_interface = self
                spawned_interface.bitrate = self.bitrate
                
                spawned_interface.ifac_size = self.ifac_size
                spawned_interface.ifac_netname = self.ifac_netname
                spawned_interface.ifac_netkey = self.ifac_netkey
                if spawned_interface.ifac_netname != None or spawned_interface.ifac_netkey != None:
                    ifac_origin = b""
                    if spawned_interface.ifac_netname != None:
                        ifac_origin += RNS.Identity.full_hash(spawned_interface.ifac_netname.encode("utf-8"))
                    if spawned_interface.ifac_netkey != None:
                        ifac_origin += RNS.Identity.full_hash(spawned_interface.ifac_netkey.encode("utf-8"))

                    ifac_origin_hash = RNS.Identity.full_hash(ifac_origin)
                    spawned_interface.ifac_key = RNS.Cryptography.hkdf(
                        length=64,
                        derive_from=ifac_origin_hash,
                        salt=RNS.Reticulum.IFAC_SALT,
                        context=None
                    )
                    spawned_interface.ifac_identity = RNS.Identity.from_bytes(spawned_interface.ifac_key)
                    spawned_interface.ifac_signature = spawned_interface.ifac_identity.sign(RNS.Identity.full_hash(spawned_interface.ifac_key))

                spawned_interface.announce_rate_target = self.announce_rate_target
                spawned_interface.announce_rate_grace = self.announce_rate_grace
                spawned_interface.announce_rate_penalty = self.announce_rate_penalty
                spawned_interface.mode = self.mode
                spawned_interface.HW_MTU = self.HW_MTU
                spawned_interface.online = True
                RNS.Transport.interfaces.append(spawned_interface)
                if addr in self.spawned_interfaces:
                    self.spawned_interfaces[addr].detach()
                    self.spawned_interfaces[addr].teardown()
                    self.spawned_interfaces.pop(spawned_interface)
                self.spawned_interfaces[addr] = spawned_interface

                RNS.log(str(self)+" added peer "+str(addr)+" on "+str(ifname), RNS.LOG_DEBUG)
            else:
                self.refresh_peer(addr)

    def refresh_peer(self, addr):
        try:
            self.peers[addr][1] = time.time()
        except Exception as e:
            RNS.log(f"An error occurred while refreshing peer {addr} on {self}: {e}", RNS.LOG_ERROR)

    def process_incoming(self, data, addr=None):
        if self.online and addr in self.spawned_interfaces:
            self.spawned_interfaces[addr].process_incoming(data, addr)

    def process_outgoing(self,data):
        pass

    # Until per-device sub-interfacing is implemented,
    # ingress limiting should be disabled on AutoInterface
    def should_ingress_limit(self):
        return False

    def detach(self):
        self.online = False

    def __str__(self):
        return "AutoInterface["+self.name+"]"

class AutoInterfacePeer(Interface):

    def __init__(self, owner, addr, ifname):
        super().__init__()
        self.owner = owner
        self.parent_interface = owner
        self.addr = addr
        self.ifname = ifname
        self.peer_addr = None
        self.addr_info = None
        self.HW_MTU = self.owner.HW_MTU
        self.FIXED_MTU = self.owner.FIXED_MTU

    def __str__(self):
        return f"AutoInterfacePeer[{self.ifname}/{self.addr}]"

    def process_incoming(self, data, addr=None):
        if self.online and self.owner.online:
            data_hash = RNS.Identity.full_hash(data)
            deque_hit = False
            if data_hash in self.owner.mif_deque:
                for te in self.owner.mif_deque_times:
                    if te[0] == data_hash and time.time() < te[1]+AutoInterface.MULTI_IF_DEQUE_TTL:
                        deque_hit = True
                        break

            if not deque_hit:
                self.owner.refresh_peer(self.addr)
                self.owner.mif_deque.append(data_hash)
                self.owner.mif_deque_times.append([data_hash, time.time()])
                self.rxb += len(data)
                self.owner.rxb += len(data)
                self.owner.owner.inbound(data, self)

    def process_outgoing(self, data):
        if self.online:
            with self.owner.write_lock:
                try:
                    if self.owner.outbound_udp_socket == None: self.owner.outbound_udp_socket = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                    if self.peer_addr == None: self.peer_addr = str(self.addr)+"%"+str(self.owner.interface_name_to_index(self.ifname))
                    if self.addr_info == None: self.addr_info = socket.getaddrinfo(self.peer_addr, self.owner.data_port, socket.AF_INET6, socket.SOCK_DGRAM)
                    self.owner.outbound_udp_socket.sendto(data, self.addr_info[0][4])
                    self.txb += len(data)
                    self.owner.txb += len(data)
                except Exception as e:
                    RNS.log("Could not transmit on "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

    def detach(self):
        self.online = False
        self.detached = True
        
    def teardown(self):
        if not self.detached:
            RNS.log("The interface "+str(self)+" experienced an unrecoverable error and is being torn down.", RNS.LOG_ERROR)
            if RNS.Reticulum.panic_on_interface_error:
                RNS.panic()

        else:
            RNS.log("The interface "+str(self)+" is being torn down.", RNS.LOG_VERBOSE)

        self.online = False
        self.OUT = False
        self.IN = False

        if self.addr in self.owner.spawned_interfaces:
            try: self.owner.spawned_interfaces.pop(self.addr)
            except Exception as e:
                RNS.log(f"Could not remove {self} from parent interface on detach. The contained exception was: {e}", RNS.LOG_ERROR)

        if self in RNS.Transport.interfaces:
            RNS.Transport.interfaces.remove(self)

    # Until per-device sub-interfacing is implemented,
    # ingress limiting should be disabled on AutoInterface
    def should_ingress_limit(self):
        return False

class AutoInterfaceHandler(socketserver.BaseRequestHandler):
    def __init__(self, callback, *args, **keys):
        self.callback = callback
        socketserver.BaseRequestHandler.__init__(self, *args, **keys)

    def handle(self):
        data = self.request[0]
        addr = self.client_address[0]
        self.callback(data, addr)