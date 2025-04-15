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
import socketserver
import threading
import platform
import socket
import time
import sys
import os
import RNS

class TCPInterface():
    HW_MTU            = 262144

class HDLC():
    FLAG              = 0x7E
    ESC               = 0x7D
    ESC_MASK          = 0x20

    @staticmethod
    def escape(data):
        data = data.replace(bytes([HDLC.ESC]), bytes([HDLC.ESC, HDLC.ESC^HDLC.ESC_MASK]))
        data = data.replace(bytes([HDLC.FLAG]), bytes([HDLC.ESC, HDLC.FLAG^HDLC.ESC_MASK]))
        return data

class KISS():
    FEND              = 0xC0
    FESC              = 0xDB
    TFEND             = 0xDC
    TFESC             = 0xDD
    CMD_DATA          = 0x00
    CMD_UNKNOWN       = 0xFE

    @staticmethod
    def escape(data):
        data = data.replace(bytes([0xdb]), bytes([0xdb, 0xdd]))
        data = data.replace(bytes([0xc0]), bytes([0xdb, 0xdc]))
        return data

class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

class ThreadingTCP6Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    address_family = socket.AF_INET6

class TCPClientInterface(Interface):
    BITRATE_GUESS = 10*1000*1000
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

    I2P_USER_TIMEOUT = 45
    I2P_PROBE_AFTER = 10
    I2P_PROBE_INTERVAL = 9
    I2P_PROBES = 5

    def __init__(self, owner, configuration, connected_socket=None):
        super().__init__()

        c = Interface.get_config_obj(configuration)
        name = c["name"]
        target_ip = c["target_host"] if "target_host" in c and c["target_host"] != None else None
        target_port = int(c["target_port"]) if "target_port" in c and c["target_host"] != None else None
        kiss_framing = False
        if "kiss_framing" in c and c.as_bool("kiss_framing") == True:
            kiss_framing = True
        i2p_tunneled = c.as_bool("i2p_tunneled") if "i2p_tunneled" in c else False
        connect_timeout = c.as_int("connect_timeout") if "connect_timeout" in c else None
        max_reconnect_tries = c.as_int("max_reconnect_tries") if "max_reconnect_tries" in c else None
        
        self.HW_MTU           = TCPInterface.HW_MTU
        self.IN               = True
        self.OUT              = False
        self.socket           = None
        self.parent_interface = None
        self.name             = name
        self.initiator        = False
        self.reconnecting     = False
        self.never_connected  = True
        self.owner            = owner
        self.writing          = False
        self.online           = False
        self.detached         = False
        self.kiss_framing     = kiss_framing
        self.i2p_tunneled     = i2p_tunneled
        self.mode             = RNS.Interfaces.Interface.Interface.MODE_FULL
        self.bitrate          = TCPClientInterface.BITRATE_GUESS
        
        if max_reconnect_tries == None:
            self.max_reconnect_tries = TCPClientInterface.RECONNECT_MAX_TRIES
        else:
            self.max_reconnect_tries = max_reconnect_tries

        if connected_socket != None:
            self.receives    = True
            self.target_ip   = None
            self.target_port = None
            self.socket      = connected_socket

            if platform.system() == "Linux":
                self.set_timeouts_linux()
            elif platform.system() == "Darwin":
                self.set_timeouts_osx()

            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        elif target_ip != None and target_port != None:
            self.receives    = True
            self.target_ip   = target_ip
            self.target_port = target_port
            self.initiator   = True

            if connect_timeout != None:
                self.connect_timeout = connect_timeout
            else:
                self.connect_timeout = TCPClientInterface.INITIAL_CONNECT_TIMEOUT
            
            if TCPClientInterface.SYNCHRONOUS_START:
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
            thread = threading.Thread(target=self.read_loop)
            thread.daemon = True
            thread.start()
            if not self.kiss_framing:
                self.wants_tunnel = True

    def set_timeouts_linux(self):
        if not self.i2p_tunneled:
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT, int(TCPClientInterface.TCP_USER_TIMEOUT * 1000))
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, int(TCPClientInterface.TCP_PROBE_AFTER))
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, int(TCPClientInterface.TCP_PROBE_INTERVAL))
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, int(TCPClientInterface.TCP_PROBES))

        else:
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT, int(TCPClientInterface.I2P_USER_TIMEOUT * 1000))
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, int(TCPClientInterface.I2P_PROBE_AFTER))
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, int(TCPClientInterface.I2P_PROBE_INTERVAL))
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, int(TCPClientInterface.I2P_PROBES))

    def set_timeouts_osx(self):
        if hasattr(socket, "TCP_KEEPALIVE"):
            TCP_KEEPIDLE = socket.TCP_KEEPALIVE
        else:
            TCP_KEEPIDLE = 0x10

        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        
        if not self.i2p_tunneled:
            self.socket.setsockopt(socket.IPPROTO_TCP, TCP_KEEPIDLE, int(TCPClientInterface.TCP_PROBE_AFTER))
        else:
            self.socket.setsockopt(socket.IPPROTO_TCP, TCP_KEEPIDLE, int(TCPClientInterface.I2P_PROBE_AFTER))
        
    def detach(self):
        self.online = False
        if self.socket != None:
            if hasattr(self.socket, "close"):
                if callable(self.socket.close):
                    self.detached = True
                    
                    try:
                        if self.socket != None:
                            self.socket.shutdown(socket.SHUT_RDWR)
                    except Exception as e:
                        RNS.log("Error while shutting down socket for "+str(self)+": "+str(e))

                    try:
                        if self.socket != None:
                            self.socket.close()
                    except Exception as e:
                        RNS.log("Error while closing socket for "+str(self)+": "+str(e))

                    self.socket = None

    def connect(self, initial=False):
        try:
            if initial:
                RNS.log("Establishing TCP connection for "+str(self)+"...", RNS.LOG_DEBUG)

            address_info = socket.getaddrinfo(self.target_ip, self.target_port, proto=socket.IPPROTO_TCP)[0]
            address_family = address_info[0]
            target_address = address_info[4]

            self.socket = socket.socket(address_family, socket.SOCK_STREAM)
            self.socket.settimeout(TCPClientInterface.INITIAL_CONNECT_TIMEOUT)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.connect(target_address)
            self.socket.settimeout(None)
            self.online  = True

            if initial:
                RNS.log("TCP connection for "+str(self)+" established", RNS.LOG_DEBUG)
        
        except Exception as e:
            if initial:
                RNS.log("Initial connection for "+str(self)+" could not be established: "+str(e), RNS.LOG_ERROR)
                RNS.log("Leaving unconnected and retrying connection in "+str(TCPClientInterface.RECONNECT_WAIT)+" seconds.", RNS.LOG_ERROR)
                return False
            
            else:
                raise e

        if platform.system() == "Linux":
            self.set_timeouts_linux()
        elif platform.system() == "Darwin":
            self.set_timeouts_osx()
        
        self.online  = True
        self.writing = False
        self.never_connected = False

        return True


    def reconnect(self):
        if self.initiator:
            if not self.reconnecting:
                self.reconnecting = True
                attempts = 0
                while not self.online:
                    time.sleep(TCPClientInterface.RECONNECT_WAIT)
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
                thread = threading.Thread(target=self.read_loop)
                thread.daemon = True
                thread.start()
                if not self.kiss_framing:
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
            # while self.writing:
            #     time.sleep(0.01)

            try:
                self.writing = True

                if self.kiss_framing:
                    data = bytes([KISS.FEND])+bytes([KISS.CMD_DATA])+KISS.escape(data)+bytes([KISS.FEND])
                else:
                    data = bytes([HDLC.FLAG])+HDLC.escape(data)+bytes([HDLC.FLAG])

                self.socket.sendall(data)
                self.writing = False
                self.txb += len(data)
                if hasattr(self, "parent_interface") and self.parent_interface != None:
                    self.parent_interface.txb += len(data)

            except Exception as e:
                RNS.log("Exception occurred while transmitting via "+str(self)+", tearing down interface", RNS.LOG_ERROR)
                RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                self.teardown()


    def read_loop(self):
        try:
            in_frame = False
            escape = False
            frame_buffer = b""
            data_in = b""
            data_buffer = b""

            while True:
                if self.socket: data_in = self.socket.recv(4096)
                else: data_in = b""
                if len(data_in) > 0:
                    if self.kiss_framing:
                        # Read loop for KISS framing
                        pointer = 0
                        while pointer < len(data_in):
                            byte = data_in[pointer]
                            pointer += 1
                            if (in_frame and byte == KISS.FEND and command == KISS.CMD_DATA):
                                in_frame = False
                                self.process_incoming(data_buffer)
                            elif (byte == KISS.FEND):
                                in_frame = True
                                command = KISS.CMD_UNKNOWN
                                data_buffer = b""
                            elif (in_frame and len(data_buffer) < self.HW_MTU):
                                if (len(data_buffer) == 0 and command == KISS.CMD_UNKNOWN):
                                    # We only support one HDLC port for now, so
                                    # strip off the port nibble
                                    byte = byte & 0x0F
                                    command = byte
                                elif (command == KISS.CMD_DATA):
                                    if (byte == KISS.FESC):
                                        escape = True
                                    else:
                                        if (escape):
                                            if (byte == KISS.TFEND):
                                                byte = KISS.FEND
                                            if (byte == KISS.TFESC):
                                                byte = KISS.FESC
                                            escape = False
                                        data_buffer = data_buffer+bytes([byte])

                    else:
                        # Read loop for standard HDLC framing
                        frame_buffer += data_in
                        flags_remaining = True
                        while flags_remaining:
                            frame_start = frame_buffer.find(HDLC.FLAG)
                            if frame_start != -1:
                                frame_end = frame_buffer.find(HDLC.FLAG, frame_start+1)
                                if frame_end != -1:
                                    frame = frame_buffer[frame_start+1:frame_end]
                                    frame = frame.replace(bytes([HDLC.ESC, HDLC.FLAG ^ HDLC.ESC_MASK]), bytes([HDLC.FLAG]))
                                    frame = frame.replace(bytes([HDLC.ESC, HDLC.ESC  ^ HDLC.ESC_MASK]), bytes([HDLC.ESC]))
                                    if len(frame) > RNS.Reticulum.HEADER_MINSIZE:
                                        self.process_incoming(frame)
                                    frame_buffer = frame_buffer[frame_end:]
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

                    break

                
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
        if ":" in self.target_ip:
            ip_str = f"[{self.target_ip}]"
        else:
            ip_str = f"{self.target_ip}"

        return "TCPInterface["+str(self.name)+"/"+ip_str+":"+str(self.target_port)+"]"


class TCPServerInterface(Interface):
    BITRATE_GUESS     = 10_000_000
    DEFAULT_IFAC_SIZE = 16
    AUTOCONFIGURE_MTU = True

    @staticmethod
    def get_address_for_if(name, bind_port, prefer_ipv6=False):
        from RNS.Interfaces import netinfo
        ifaddr = netinfo.ifaddresses(name)
        if len(ifaddr) < 1:
            raise SystemError(f"No addresses available on specified kernel interface \"{name}\" for TCPServerInterface to bind to")

        if (prefer_ipv6 or not netinfo.AF_INET in ifaddr) and netinfo.AF_INET6 in ifaddr:
            bind_ip = ifaddr[netinfo.AF_INET6][0]["addr"]
            if bind_ip.lower().startswith("fe80::"):
                # We'll need to add the interface as scope for link-local addresses
                return TCPServerInterface.get_address_for_host(f"{bind_ip}%{name}", bind_port, prefer_ipv6)
            else:
                return TCPServerInterface.get_address_for_host(bind_ip, bind_port, prefer_ipv6)
        elif netinfo.AF_INET in ifaddr:
            bind_ip = ifaddr[netinfo.AF_INET][0]["addr"]
            return (bind_ip, bind_port)
        else:
            raise SystemError(f"No addresses available on specified kernel interface \"{name}\" for TCPServerInterface to bind to")

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
            raise SystemError(f"No suitable kernel interface available for address \"{name}\" for TCPServerInterface to bind to")


    @property
    def clients(self):
        return len(self.spawned_interfaces)

    def __init__(self, owner, configuration):
        super().__init__()

        c            = Interface.get_config_obj(configuration)
        name         = c["name"]
        device       = c["device"] if "device" in c else None
        port         = int(c["port"]) if "port" in c else None
        bindip       = c["listen_ip"] if "listen_ip" in c else None
        bindport     = int(c["listen_port"]) if "listen_port" in c else None
        i2p_tunneled = c.as_bool("i2p_tunneled") if "i2p_tunneled" in c else False
        prefer_ipv6  = c.as_bool("prefer_ipv6") if "prefer_ipv6" in c else False

        if port != None:
            bindport = port

        self.HW_MTU = TCPInterface.HW_MTU

        self.online = False
        self.spawned_interfaces = []
        
        self.IN  = True
        self.OUT = False
        self.name = name
        self.detached = False

        self.i2p_tunneled = i2p_tunneled
        self.mode         = RNS.Interfaces.Interface.Interface.MODE_FULL

        if bindport == None:
            raise SystemError(f"No TCP port configured for interface \"{name}\"")
        else:
            self.bind_port = bindport

        bind_address = None
        if device != None:
            bind_address = TCPServerInterface.get_address_for_if(device, self.bind_port, prefer_ipv6)
        else:
            if bindip == None:
                raise SystemError(f"No TCP bind IP configured for interface \"{name}\"")
            bind_address = TCPServerInterface.get_address_for_host(bindip, self.bind_port, prefer_ipv6)

        if bind_address != None:
            self.receives = True
            self.bind_ip = bind_address[0]

            def handlerFactory(callback):
                def createHandler(*args, **keys):
                    return TCPInterfaceHandler(callback, *args, **keys)
                return createHandler

            self.owner = owner

            if len(bind_address) == 4:
                try:
                    ThreadingTCP6Server.allow_reuse_address = True
                    self.server = ThreadingTCP6Server(bind_address, handlerFactory(self.incoming_connection))
                except Exception as e:
                    RNS.log(f"Error while binding IPv6 socket for interface, the contained exception was: {e}", RNS.LOG_ERROR)
                    raise SystemError("Could not bind IPv6 socket for interface. Please check the specified \"listen_ip\" configuration option")
            else:
                ThreadingTCPServer.allow_reuse_address = True
                self.server = ThreadingTCPServer(bind_address, handlerFactory(self.incoming_connection))
                self.server.daemon_threads = True

            self.bitrate = TCPServerInterface.BITRATE_GUESS

            thread = threading.Thread(target=self.server.serve_forever)
            thread.daemon = True
            thread.start()

            self.online = True

        else:
            raise SystemError("Insufficient parameters to create TCP listener")

    def incoming_connection(self, handler):
        RNS.log("Accepting incoming TCP connection", RNS.LOG_VERBOSE)
        spawned_configuration = {"name": "Client on "+self.name, "target_host": None, "target_port": None, "i2p_tunneled": self.i2p_tunneled}
        spawned_interface = TCPClientInterface(self.owner, spawned_configuration, connected_socket=handler.request)
        spawned_interface.OUT = self.OUT
        spawned_interface.IN  = self.IN
        spawned_interface.target_ip = handler.client_address[0]
        spawned_interface.target_port = str(handler.client_address[1])
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
        RNS.log("Spawned new TCPClient Interface: "+str(spawned_interface), RNS.LOG_VERBOSE)
        RNS.Transport.interfaces.append(spawned_interface)
        while spawned_interface in self.spawned_interfaces:
            self.spawned_interfaces.remove(spawned_interface)
        self.spawned_interfaces.append(spawned_interface)
        spawned_interface.read_loop()

    def received_announce(self, from_spawned=False):
        if from_spawned: self.ia_freq_deque.append(time.time())

    def sent_announce(self, from_spawned=False):
        if from_spawned: self.oa_freq_deque.append(time.time())

    def process_outgoing(self, data):
        pass

    def detach(self):
        self.detached = True
        self.online = False
        if self.server != None:
            if hasattr(self.server, "shutdown"):
                if callable(self.server.shutdown):
                    try:
                        RNS.log("Detaching "+str(self), RNS.LOG_DEBUG)
                        self.server.shutdown()
                        self.server.server_close()
                        self.server = None

                    except Exception as e:
                        RNS.log("Error while shutting down server for "+str(self)+": "+str(e))


    def __str__(self):
        if ":" in self.bind_ip:
            ip_str = f"[{self.bind_ip}]"
        else:
            ip_str = f"{self.bind_ip}"

        return "TCPServerInterface["+self.name+"/"+ip_str+":"+str(self.bind_port)+"]"


class TCPInterfaceHandler(socketserver.BaseRequestHandler):
    def __init__(self, callback, *args, **keys):
        self.callback = callback
        socketserver.BaseRequestHandler.__init__(self, *args, **keys)

    def handle(self):
        self.callback(handler=self)
