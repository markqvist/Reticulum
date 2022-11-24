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
import socketserver
import threading
import socket
import struct
import time
import sys
import RNS


class AutoInterface(Interface):
    DEFAULT_DISCOVERY_PORT = 29716
    DEFAULT_DATA_PORT      = 42671
    DEFAULT_GROUP_ID       = "reticulum".encode("utf-8")

    SCOPE_LINK         = "2"
    SCOPE_ADMIN        = "4"
    SCOPE_SITE         = "5"
    SCOPE_ORGANISATION = "8"
    SCOPE_GLOBAL       = "e"

    PEERING_TIMEOUT    = 7.5

    DARWIN_IGNORE_IFS  = ["awdl0", "llw0", "lo0", "en5"]
    ANDROID_IGNORE_IFS = ["dummy0", "lo", "tun0"]

    BITRATE_GUESS      = 10*1000*1000

    def handler_factory(self, callback):
        def create_handler(*args, **keys):
            return AutoInterfaceHandler(callback, *args, **keys)
        return create_handler

    def __init__(self, owner, name, group_id=None, discovery_scope=None, discovery_port=None, data_port=None, allowed_interfaces=None, ignored_interfaces=None, configured_bitrate=None):
        import importlib
        if importlib.util.find_spec('netifaces') != None:
            import netifaces
        else:
            RNS.log("Using AutoInterface requires the netifaces module.", RNS.LOG_CRITICAL)
            RNS.log("You can install it with the command: python3 -m pip install netifaces", RNS.LOG_CRITICAL)
            RNS.panic()

        self.netifaces = netifaces
        self.rxb = 0
        self.txb = 0

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

        self.outbound_udp_socket = None

        self.announce_rate_target = None
        self.announce_interval = AutoInterface.PEERING_TIMEOUT/6.0
        self.peer_job_interval = AutoInterface.PEERING_TIMEOUT*1.1
        self.peering_timeout   = AutoInterface.PEERING_TIMEOUT
        self.multicast_echo_timeout = AutoInterface.PEERING_TIMEOUT/2

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
        self.mcast_discovery_address = "ff1"+self.discovery_scope+":"+gt

        suitable_interfaces = 0
        for ifname in self.netifaces.interfaces():
            if RNS.vendor.platformutils.is_darwin() and ifname in AutoInterface.DARWIN_IGNORE_IFS and not ifname in self.allowed_interfaces:
                RNS.log(str(self)+" skipping Darwin AWDL or tethering interface "+str(ifname), RNS.LOG_EXTREME)
            elif RNS.vendor.platformutils.is_darwin() and ifname == "lo0":
                RNS.log(str(self)+" skipping Darwin loopback interface "+str(ifname), RNS.LOG_EXTREME)
            elif RNS.vendor.platformutils.is_android() and ifname in AutoInterface.ANDROID_IGNORE_IFS and not ifname in self.allowed_interfaces:
                RNS.log(str(self)+" skipping Android system interface "+str(ifname), RNS.LOG_EXTREME)
            elif ifname in self.ignored_interfaces:
                RNS.log(str(self)+" ignoring disallowed interface "+str(ifname), RNS.LOG_EXTREME)
            else:
                if len(self.allowed_interfaces) > 0 and not ifname in self.allowed_interfaces:
                    RNS.log(str(self)+" ignoring interface "+str(ifname)+" since it was not allowed", RNS.LOG_EXTREME)
                else:
                    addresses = self.netifaces.ifaddresses(ifname)
                    if self.netifaces.AF_INET6 in addresses:
                        link_local_addr = None
                        for address in addresses[self.netifaces.AF_INET6]:
                            if "addr" in address:
                                if address["addr"].startswith("fe80:"):
                                    link_local_addr = address["addr"]
                                    self.link_local_addresses.append(link_local_addr.split("%")[0])
                                    self.adopted_interfaces[ifname] = link_local_addr.split("%")[0]
                                    self.multicast_echoes[ifname] = time.time()
                                    RNS.log(str(self)+" Selecting link-local address "+str(link_local_addr)+" for interface "+str(ifname), RNS.LOG_EXTREME)

                        if link_local_addr == None:
                            RNS.log(str(self)+" No link-local IPv6 address configured for "+str(ifname)+", skipping interface", RNS.LOG_EXTREME)
                        else:
                            mcast_addr = self.mcast_discovery_address
                            RNS.log(str(self)+" Creating multicast discovery listener on "+str(ifname)+" with address "+str(mcast_addr), RNS.LOG_EXTREME)

                            # Struct with interface index
                            if_struct = struct.pack("I", socket.if_nametoindex(ifname))

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
                            addr_info = socket.getaddrinfo(mcast_addr+"%"+ifname, self.discovery_port, socket.AF_INET6, socket.SOCK_DGRAM)
                            discovery_socket.bind(addr_info[0][4])

                            # Set up thread for discovery packets
                            def discovery_loop():
                                self.discovery_handler(discovery_socket, ifname)

                            thread = threading.Thread(target=discovery_loop)
                            thread.daemon = True
                            thread.start()

                            suitable_interfaces += 1

        if suitable_interfaces == 0:
            RNS.log(str(self)+" could not autoconfigure. This interface currently provides no connectivity.", RNS.LOG_WARNING)
        else:
            self.receives = True

            peering_wait = self.announce_interval*1.2
            RNS.log(str(self)+" discovering peers for "+str(round(peering_wait, 2))+" seconds...", RNS.LOG_VERBOSE)

            self.owner = owner
            socketserver.UDPServer.address_family = socket.AF_INET6

            for ifname in self.adopted_interfaces:
                local_addr = self.adopted_interfaces[ifname]+"%"+ifname
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

            if configured_bitrate != None:
                self.bitrate = configured_bitrate
            else:
                self.bitrate = AutoInterface.BITRATE_GUESS

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
                RNS.log(str(self)+" removed peer "+str(peer_addr)+" on "+str(removed_peer[0]), RNS.LOG_DEBUG)

            for ifname in self.adopted_interfaces:
                # Check that the link-local address has not changed
                try:
                    addresses = self.netifaces.ifaddresses(ifname)
                    if self.netifaces.AF_INET6 in addresses:
                        link_local_addr = None
                        for address in addresses[self.netifaces.AF_INET6]:
                            if "addr" in address:
                                if address["addr"].startswith("fe80:"):
                                    link_local_addr = address["addr"].split("%")[0]
                                    if link_local_addr != self.adopted_interfaces[ifname]:
                                        # TODO: Remove
                                        # RNS.log("Replacing link-local address for "+str(ifname), RNS.LOG_DEBUG)
                                        self.adopted_interfaces[ifname] = link_local_addr

                                        local_addr = link_local_addr+"%"+ifname
                                        addr_info = socket.getaddrinfo(local_addr, self.data_port, socket.AF_INET6, socket.SOCK_DGRAM)
                                        listen_address = addr_info[0][4]

                                        if ifname in self.interface_servers:
                                            # TODO: Remove
                                            # RNS.log("Shutting down previous UDP socket server for "+str(ifname), RNS.LOG_DEBUG)
                                            previous_server = self.interface_servers[ifname]
                                            def shutdown_server():
                                                previous_server.shutdown()
                                            threading.Thread(target=shutdown_server, daemon=True).start()

                                        # TODO: Remove
                                        # RNS.log("Starting new UDP socket server for "+str(ifname), RNS.LOG_DEBUG)

                                        udp_server = socketserver.UDPServer(listen_address, self.handler_factory(self.processIncoming))
                                        self.interface_servers[ifname] = udp_server

                                        thread = threading.Thread(target=udp_server.serve_forever)
                                        thread.daemon = True
                                        thread.start()

                except Exception as e:
                    RNS.log("Could not get device information while updating link-local addresses for "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

                # Check multicast echo timeouts
                last_multicast_echo = 0
                if ifname in self.multicast_echoes:
                    last_multicast_echo = self.multicast_echoes[ifname]

                if now - last_multicast_echo > self.multicast_echo_timeout:
                    if ifname in self.timed_out_interfaces and self.timed_out_interfaces[ifname] == False:
                        RNS.log("Multicast echo timeout for "+str(ifname)+". Carrier lost.", RNS.LOG_WARNING)
                    self.timed_out_interfaces[ifname] = True
                else:
                    if ifname in self.timed_out_interfaces and self.timed_out_interfaces[ifname] == True:
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

            ifis = struct.pack("I", socket.if_nametoindex(ifname))
            announce_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, ifis)
            announce_socket.sendto(discovery_token, addr_info[0][4])
            announce_socket.close()
            
        except Exception as e:
            if (ifname in self.timed_out_interfaces and self.timed_out_interfaces[ifname] == False) or not ifname in self.timed_out_interfaces:
                RNS.log(str(self)+" Detected possible carrier loss on "+str(ifname)+": "+str(e), RNS.LOG_WARNING)
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
                RNS.log(str(self)+" received multicast echo on unexpected interface "+str(ifname), RNS.LOG_WARNING)

        else:
            if not addr in self.peers:
                self.peers[addr] = [ifname, time.time()]
                RNS.log(str(self)+" added peer "+str(addr)+" on "+str(ifname), RNS.LOG_DEBUG)
            else:
                self.refresh_peer(addr)

    def refresh_peer(self, addr):
        self.peers[addr][1] = time.time()

    def processIncoming(self, data):
        self.rxb += len(data)
        self.owner.inbound(data, self)

    def processOutgoing(self,data):
            for peer in self.peers:
                try:
                    if self.outbound_udp_socket == None:
                        self.outbound_udp_socket = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                    
                    peer_addr = str(peer)+"%"+str(self.peers[peer][0])
                    addr_info = socket.getaddrinfo(peer_addr, self.data_port, socket.AF_INET6, socket.SOCK_DGRAM)
                    self.outbound_udp_socket.sendto(data, addr_info[0][4])

                except Exception as e:
                    RNS.log("Could not transmit on "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

            
            self.txb += len(data)
            

    def __str__(self):
        return "AutoInterface["+self.name+"]"

class AutoInterfaceHandler(socketserver.BaseRequestHandler):
    def __init__(self, callback, *args, **keys):
        self.callback = callback
        socketserver.BaseRequestHandler.__init__(self, *args, **keys)

    def handle(self):
        data = self.request[0]
        self.callback(data)
