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
import threading
import socket
import select
import time
import sys
import os
import RNS

class HDLC():
    FLAG              = 0x7E
    ESC               = 0x7D
    ESC_MASK          = 0x20

    @staticmethod
    def escape(data):
        data = data.replace(bytes([HDLC.ESC]), bytes([HDLC.ESC, HDLC.ESC^HDLC.ESC_MASK]))
        data = data.replace(bytes([HDLC.FLAG]), bytes([HDLC.ESC, HDLC.FLAG^HDLC.ESC_MASK]))
        return data

class BackboneInterface(Interface):
    HW_MTU            = 1048576
    BITRATE_GUESS     = 1_000_000_000
    DEFAULT_IFAC_SIZE = 16
    AUTOCONFIGURE_MTU = True

    epoll = None
    listener_filenos = {}
    spawned_interface_filenos = {}
    epoll = None
    _job_active = False
    _job_lock = threading.Lock()

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

        c            = Interface.get_config_obj(configuration)
        name         = c["name"]
        device       = c["device"] if "device" in c else None
        port         = int(c["port"]) if "port" in c else None
        bindip       = c["listen_ip"] if "listen_ip" in c else None
        bindport     = int(c["listen_port"]) if "listen_port" in c else None
        prefer_ipv6  = c.as_bool("prefer_ipv6") if "prefer_ipv6" in c else False

        if port != None: bindport = port

        self.HW_MTU = BackboneInterface.HW_MTU
        self.online = False
        self.IN  = True
        self.OUT = False
        self.name = name
        self.detached = False
        self.mode = RNS.Interfaces.Interface.Interface.MODE_FULL
        self.spawned_interfaces = []

        if bindport == None:
            raise SystemError(f"No TCP port configured for interface \"{name}\"")
        else:
            self.bind_port = bindport

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

    @staticmethod
    def start():
        if not BackboneInterface._job_active: threading.Thread(target=BackboneInterface.__job, daemon=True).start()

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
            RNS.log(f"Attempt to register invalid file descriptor {fileno}", RNS.LOG_ERROR)
            return

        try: BackboneInterface.epoll.register(fileno, select.EPOLLIN)
        except Exception as e:
            RNS.log(f"An error occurred while registering EPOLL_IN for file descriptor {fileno}: {e}", RNS.LOG_ERROR)

    @staticmethod
    def deregister_fileno(fileno):
        if fileno < 0:
            RNS.log(f"Attempt to deregister invalid file descriptor {fileno}", RNS.LOG_ERROR)
            return

        try: BackboneInterface.epoll.unregister(fileno)
        except Exception as e:
            RNS.log(f"An error occurred while deregistering file descriptor {fileno}: {e}", RNS.LOG_DEBUG)

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
                    BackboneInterface.epoll.modify(interface.socket.fileno(), select.EPOLLOUT)
                except Exception as e:
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
                        events = BackboneInterface.epoll.poll(1)
                        for fileno, event in BackboneInterface.epoll.poll(1):
                            if fileno in BackboneInterface.spawned_interface_filenos:
                                spawned_interface = BackboneInterface.spawned_interface_filenos[fileno]
                                client_socket = spawned_interface.socket
                                if client_socket and fileno == client_socket.fileno() and (event & select.EPOLLIN):
                                    try: received_bytes = client_socket.recv(spawned_interface.HW_MTU)
                                    except Exception as e:
                                        RNS.log(f"Error while reading from {spawned_interface}: {e}", RNS.LOG_DEBUG)
                                        received_bytes = b""

                                    if len(received_bytes): spawned_interface.receive(received_bytes)
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
                                
                                elif client_socket and fileno == client_socket.fileno() and (event & select.EPOLLOUT):
                                    try:
                                        written = client_socket.send(spawned_interface.transmit_buffer)
                                    except Exception as e:
                                        written = 0
                                        if not spawned_interface.detached: RNS.log(f"Error while writing to {spawned_interface}: {e}", RNS.LOG_DEBUG)
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

                                    spawned_interface.transmit_buffer = spawned_interface.transmit_buffer[written:]
                                    if len(spawned_interface.transmit_buffer) == 0: BackboneInterface.epoll.modify(fileno, select.EPOLLIN)
                                    spawned_interface.txb += written
                                    if spawned_interface.parent_interface: spawned_interface.parent_interface.txb += written
                                
                                elif client_socket and fileno == client_socket.fileno() and event & (select.EPOLLHUP):
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
                                    client_socket, address = server_socket.accept()
                                    client_socket.setblocking(0)
                                    if not owner_interface.incoming_connection(client_socket):
                                        try: client_socket.close()
                                        except Exception as e: RNS.log(f"Error while closing socket for failed incoming connection: {e}", RNS.LOG_ERROR)
                                
                                elif fileno == server_socket.fileno() and (event & select.EPOLLHUP):
                                    try: BackboneInterface.deregister_fileno(fileno)
                                    except Exception as e: RNS.log(f"Error while deregistering listener file descriptor {fileno}: {e}", RNS.LOG_ERROR)

                                    try: server_socket.close()
                                    except Exception as e: RNS.log(f"Error while closing listener socket for {server_socket}: {e}", RNS.LOG_ERROR)

                except Exception as e:
                    RNS.log(f"BackboneInterface error: {e}", RNS.LOG_ERROR)
                    RNS.trace_exception(e)

                finally:
                    BackboneInterface.deregister_listeners()
    
    def incoming_connection(self, socket):
        RNS.log("Accepting incoming connection", RNS.LOG_VERBOSE)
        try:
            spawned_configuration = {"name": "Client on "+self.name, "target_host": None, "target_port": None}
            spawned_interface = BackboneClientInterface(self.owner, spawned_configuration, connected_socket=socket)
            spawned_interface.OUT = self.OUT
            spawned_interface.IN  = self.IN
            spawned_interface.socket = socket
            spawned_interface.target_ip = socket.getpeername()[0]
            spawned_interface.target_port = str(socket.getpeername()[1])
            spawned_interface.parent_interface = self
            spawned_interface.bitrate = self.bitrate
            spawned_interface.optimise_mtu()
            
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
            RNS.log("Spawned new BackboneClient Interface: "+str(spawned_interface), RNS.LOG_VERBOSE)
            RNS.Transport.interfaces.append(spawned_interface)
            while spawned_interface in self.spawned_interfaces: self.spawned_interfaces.remove(spawned_interface)
            self.spawned_interfaces.append(spawned_interface)
            BackboneInterface.add_client_socket(socket, spawned_interface)

        except Exception as e:
            RNS.log(f"An error occurred while accepting incoming connection on {self}: {e}", RNS.LOG_ERROR)
            return False

        return True

    def received_announce(self, from_spawned=False):
        if from_spawned: self.ia_freq_deque.append(time.time())

    def sent_announce(self, from_spawned=False):
        if from_spawned: self.oa_freq_deque.append(time.time())

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
                        except Exception as e: RNS.log("Error while shutting down socket for "+str(self)+": "+str(e), RNS.LOG_ERROR)

    def __str__(self):
        if ":" in self.bind_ip:
            ip_str = f"[{self.bind_ip}]"
        else:
            ip_str = f"{self.bind_ip}"

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
        self.frame_buffer     = b""
        self.transmit_buffer  = b""
        
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
                    except Exception as e: RNS.log("Error while shutting down socket for "+str(self)+": "+str(e), RNS.LOG_ERROR)

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
            self.socket.settimeout(None)

            BackboneInterface.add_client_socket(self.socket, self)
            self.online  = True

            if initial:
                RNS.log("TCP connection for "+str(self)+" established", RNS.LOG_DEBUG)
        
        except Exception as e:
            if initial:
                RNS.log("Initial connection for "+str(self)+" could not be established: "+str(e), RNS.LOG_ERROR)
                RNS.log("Leaving unconnected and retrying connection in "+str(BackboneClientInterface.RECONNECT_WAIT)+" seconds.", RNS.LOG_ERROR)
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
                while not self.online:
                    time.sleep(BackboneClientInterface.RECONNECT_WAIT)
                    attempts += 1

                    if self.max_reconnect_tries != None and attempts > self.max_reconnect_tries:
                        RNS.log("Max reconnection attempts reached for "+str(self), RNS.LOG_ERROR)
                        self.teardown()
                        break

                    try:
                        self.connect()

                    except Exception as e:
                        RNS.log("Connection attempt for "+str(self)+" failed: "+str(e), RNS.LOG_DEBUG)

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
                        
            self.owner.inbound(data, self)

    def process_outgoing(self, data):
        if self.online and not self.detached:
            try:
                self.transmit_buffer += bytes([HDLC.FLAG])+HDLC.escape(data)+bytes([HDLC.FLAG])
                BackboneInterface.tx_ready(self)

            except Exception as e:
                RNS.log("Exception occurred while transmitting via "+str(self)+", tearing down interface", RNS.LOG_ERROR)
                RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                self.teardown()

    def receive(self, data_in):
        try:
            if len(data_in) > 0:
                self.frame_buffer += data_in
                flags_remaining = True
                while flags_remaining:
                    frame_start = self.frame_buffer.find(HDLC.FLAG)
                    if frame_start != -1:
                        frame_end = self.frame_buffer.find(HDLC.FLAG, frame_start+1)
                        if frame_end != -1:
                            frame = self.frame_buffer[frame_start+1:frame_end]
                            frame = frame.replace(bytes([HDLC.ESC, HDLC.FLAG ^ HDLC.ESC_MASK]), bytes([HDLC.FLAG]))
                            frame = frame.replace(bytes([HDLC.ESC, HDLC.ESC  ^ HDLC.ESC_MASK]), bytes([HDLC.ESC]))
                            if len(frame) > RNS.Reticulum.HEADER_MINSIZE:
                                self.process_incoming(frame)
                            self.frame_buffer = self.frame_buffer[frame_end:]
                        else:
                            flags_remaining = False
                    else:
                        flags_remaining = False

            else:
                self.online = False
                if self.initiator and not self.detached:
                    RNS.log("The socket for "+str(self)+" was closed, attempting to reconnect...", RNS.LOG_WARNING)
                    self.reconnect()
                else:
                    RNS.log("The socket for remote client "+str(self)+" was closed.", RNS.LOG_VERBOSE)
                    self.teardown()
                
        except Exception as e:
            self.online = False
            RNS.log("An interface error occurred for "+str(self)+", the contained exception was: "+str(e), RNS.LOG_WARNING)

            if self.initiator:
                RNS.log("Attempting to reconnect...", RNS.LOG_WARNING)
                self.reconnect()
            else:
                self.teardown()

    def teardown(self):
        if self.initiator and not self.detached:
            RNS.log("The interface "+str(self)+" experienced an unrecoverable error and is being torn down. Restart Reticulum to attempt to open this interface again.", RNS.LOG_ERROR)
            if RNS.Reticulum.panic_on_interface_error:
                RNS.panic()

        else:
            RNS.log("The interface "+str(self)+" is being torn down.", RNS.LOG_VERBOSE)

        self.online = False
        self.OUT = False
        self.IN = False

        if hasattr(self, "parent_interface") and self.parent_interface != None:
            while self in self.parent_interface.spawned_interfaces:
                self.parent_interface.spawned_interfaces.remove(self)

        if self in RNS.Transport.interfaces:
            if not self.initiator:
                RNS.Transport.interfaces.remove(self)


    def __str__(self):
        if ":" in self.target_ip: ip_str = f"[{self.target_ip}]"
        else: ip_str = f"{self.target_ip}"
        return "BackboneInterface["+str(self.name)+"/"+ip_str+":"+str(self.target_port)+"]"