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
from RNS.Interfaces.BackboneInterface import BackboneInterface
import socketserver
import threading
import socket
import time
import sys
import os
import RNS
from threading import Lock

class HDLC():
    FLAG              = 0x7E
    ESC               = 0x7D
    ESC_MASK          = 0x20

    @staticmethod
    def escape(data):
        data = data.replace(bytes([HDLC.ESC]), bytes([HDLC.ESC, HDLC.ESC^HDLC.ESC_MASK]))
        data = data.replace(bytes([HDLC.FLAG]), bytes([HDLC.ESC, HDLC.FLAG^HDLC.ESC_MASK]))
        return data

class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    def server_bind(self):
        if RNS.vendor.platformutils.is_windows():
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()

class LocalClientInterface(Interface):
    RECONNECT_WAIT = 8
    AUTOCONFIGURE_MTU = True

    def __init__(self, owner, name, target_port = None, connected_socket=None, socket_path=None):
        super().__init__()

        self.epoll_backend    = False
        self.HW_MTU           = 262144
        self.online           = False
        
        if socket_path != None and RNS.Reticulum.get_instance().use_af_unix: self.socket_path = f"\0rns/{socket_path}"
        else: self.socket_path = None
        
        self.IN               = True
        self.OUT              = False
        self.socket           = None
        self.parent_interface = None
        self.reconnecting     = False
        self.never_connected  = True
        self.detached         = False
        self.name             = name
        self.mode             = RNS.Interfaces.Interface.Interface.MODE_FULL
        self.frame_buffer     = b""
        self.transmit_buffer  = b""

        if RNS.vendor.platformutils.use_epoll():
            self.epoll_backend = True

        if connected_socket != None:
            self.receives    = True
            self.target_ip   = None
            self.target_port = None
            self.socket      = connected_socket

            if self.socket.family == socket.AF_INET:
                self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            self.is_connected_to_shared_instance = False

        elif self.socket_path != None:
            self.receives    = True
            self.target_ip   = None
            self.target_port = None
            self.connect()

        elif target_port != None:
            self.receives    = True
            self.target_ip   = "127.0.0.1"
            self.target_port = target_port
            self.connect()

        self.owner   = owner
        self.bitrate = 1_000_000_000
        self.online  = True
        self.writing = False

        self._force_bitrate = False

        self.announce_rate_target  = None
        self.announce_rate_grace   = None
        self.announce_rate_penalty = None

        if connected_socket == None:
            if not self.epoll_backend:
                thread = threading.Thread(target=self.read_loop)
                thread.daemon = True
                thread.start()

    def should_ingress_limit(self):
        return False

    def connect(self):
        if self.socket_path != None:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.connect(self.socket_path)
        
        else:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.connect((self.target_ip, self.target_port))

        self.online = True
        self.is_connected_to_shared_instance = True
        self.never_connected = False

        if self.epoll_backend: BackboneInterface.add_client_socket(self.socket, self)

        return True


    def reconnect(self):
        if self.is_connected_to_shared_instance:
            if not self.reconnecting:
                self.reconnecting = True
                attempts = 0

                while not self.online:
                    time.sleep(LocalClientInterface.RECONNECT_WAIT)
                    attempts += 1

                    try:
                        self.connect()

                    except Exception as e:
                        RNS.log("Connection attempt for "+str(self)+" failed: "+str(e), RNS.LOG_DEBUG)

                if not self.never_connected:
                    RNS.log("Reconnected socket for "+str(self)+".", RNS.LOG_INFO)

                self.reconnecting = False
                if not self.epoll_backend:
                    thread = threading.Thread(target=self.read_loop)
                    thread.daemon = True
                    thread.start()

                def job():
                    time.sleep(LocalClientInterface.RECONNECT_WAIT+2)
                    RNS.Transport.shared_connection_reappeared()
                threading.Thread(target=job, daemon=True).start()
        
        else:
            RNS.log("Attempt to reconnect on a non-initiator shared local interface. This should not happen.", RNS.LOG_ERROR)
            raise IOError("Attempt to reconnect on a non-initiator local interface")


    def process_incoming(self, data):
        self.rxb += len(data)
        if self.parent_interface != None: self.parent_interface.rxb += len(data)
        
        try:
            self.owner.inbound(data, self)
        except Exception as e:
            RNS.log(f"An error in the processing of an incoming frame for {self}: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

    def process_outgoing(self, data):
        if self.online:
            try:
                if self.epoll_backend:
                    self.transmit_buffer += bytes([HDLC.FLAG])+HDLC.escape(data)+bytes([HDLC.FLAG])
                    BackboneInterface.tx_ready(self)

                else:
                    self.writing = True

                    if self._force_bitrate:
                        if not hasattr(self, "send_lock"):
                            self.send_lock = Lock()

                        with self.send_lock:
                            # RNS.log(f"Simulating latency of {RNS.prettytime(s)} for {len(data)} bytes", RNS.LOG_EXTREME)
                            s = len(data) / self.bitrate * 8
                            time.sleep(s)

                    data = bytes([HDLC.FLAG])+HDLC.escape(data)+bytes([HDLC.FLAG])
                    self.socket.sendall(data)
                    self.writing = False
                    self.txb += len(data)
                    if hasattr(self, "parent_interface") and self.parent_interface != None:
                        self.parent_interface.txb += len(data)

            except Exception as e:
                RNS.log("Exception occurred while transmitting via "+str(self)+", tearing down interface", RNS.LOG_ERROR)
                RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                RNS.trace_exception(e)
                self.teardown()

    def handle_hdlc(self, data_in):
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

    def receive(self, data_in):
        try:
            if len(data_in) > 0: self.handle_hdlc(data_in)
            else:
                self.online = False
                if self.is_connected_to_shared_instance and not self.detached:
                    RNS.log("Socket for "+str(self)+" was closed, attempting to reconnect...", RNS.LOG_WARNING)
                    RNS.Transport.shared_connection_disappeared()
                    self.reconnect()
                else:
                    self.teardown(nowarning=True)
                
        except Exception as e:
            self.online = False
            RNS.log("An interface error occurred, the contained exception was: "+str(e), RNS.LOG_ERROR)
            RNS.log("Tearing down "+str(self), RNS.LOG_ERROR)
            self.teardown()

    def read_loop(self):
        try:
            self.frame_buffer = b""
            data_in = b""
            while True:
                data_in = self.socket.recv(4096)
                if len(data_in) > 0: self.handle_hdlc(data_in)
                else:
                    self.online = False
                    if self.is_connected_to_shared_instance and not self.detached:
                        RNS.log("Socket for "+str(self)+" was closed, attempting to reconnect...", RNS.LOG_WARNING)
                        RNS.Transport.shared_connection_disappeared()
                        self.reconnect()
                    else:
                        self.teardown(nowarning=True)

                    break

        except Exception as e:
            self.online = False
            RNS.log("An interface error occurred, the contained exception was: "+str(e), RNS.LOG_ERROR)
            RNS.log("Tearing down "+str(self), RNS.LOG_ERROR)
            self.teardown()

    def detach(self):
        if self.socket != None:
            if hasattr(self.socket, "close"):
                if callable(self.socket.close):
                    RNS.log("Detaching "+str(self), RNS.LOG_DEBUG)
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

    def teardown(self, nowarning=False):
        self.online = False
        self.OUT = False
        self.IN = False

        if self in RNS.Transport.interfaces:
            RNS.Transport.interfaces.remove(self)

        if self in RNS.Transport.local_client_interfaces:
            RNS.Transport.local_client_interfaces.remove(self)
            if hasattr(self, "parent_interface") and self.parent_interface != None:
                self.parent_interface.clients -= 1
                if hasattr(RNS.Transport, "owner") and RNS.Transport.owner != None:
                    RNS.Transport.owner._should_persist_data()

        if nowarning == False:
            RNS.log("The interface "+str(self)+" experienced an unrecoverable error and is being torn down. Restart Reticulum to attempt to open this interface again.", RNS.LOG_ERROR)
            if RNS.Reticulum.panic_on_interface_error:
                RNS.panic()

        if self.is_connected_to_shared_instance:
            if nowarning == False:
                RNS.log("Permanently lost connection to local shared RNS instance. Exiting now.", RNS.LOG_CRITICAL)
    
            RNS.exit()


    def __str__(self):
        if self.socket_path: return "LocalInterface["+str(self.socket_path.replace("\0", ""))+"]"
        else: return "LocalInterface["+str(self.target_port)+"]"


class LocalServerInterface(Interface):
    AUTOCONFIGURE_MTU = True

    def __init__(self, owner, bindport=None, socket_path=None):
        super().__init__()
        self.epoll_backend = False
        self.online = False
        self.clients = 0
        
        if socket_path != None and RNS.Reticulum.get_instance().use_af_unix: self.socket_path = f"\0rns/{socket_path}"
        else: self.socket_path = None
        
        self.IN  = True
        self.OUT = False
        self.name = "Reticulum"
        self.mode = RNS.Interfaces.Interface.Interface.MODE_FULL

        if RNS.vendor.platformutils.use_epoll():
            self.epoll_backend = True

        if socket_path != None and self.epoll_backend:
            self.receives = True
            self.bind_ip = None
            self.bind_port = None

            self.owner = owner
            self.is_local_shared_instance = True
            BackboneInterface.add_listener(self, self.socket_path, socket_type=socket.AF_UNIX)

        elif bindport != None:
            self.receives = True
            self.bind_ip = "127.0.0.1"
            self.bind_port = bindport

            self.owner = owner
            self.is_local_shared_instance = True

            address = (self.bind_ip, self.bind_port)
            if self.epoll_backend: BackboneInterface.add_listener(self, address)
            else:
                def handlerFactory(callback):
                    def createHandler(*args, **keys):
                        return LocalInterfaceHandler(callback, *args, **keys)
                    return createHandler

                self.server = ThreadingTCPServer(address, handlerFactory(self.incoming_connection))
                self.server.daemon_threads = True
                thread = threading.Thread(target=self.server.serve_forever)
                thread.daemon = True
                thread.start()

        self.announce_rate_target  = None
        self.announce_rate_grace   = None
        self.announce_rate_penalty = None

        self.bitrate = 1000*1000*1000
        self.online = True

    def incoming_connection(self, handler):
        if self.epoll_backend:
            client_socket = handler
            if client_socket.family == socket.AF_INET:
                interface_name = str(str(client_socket.getpeername()[1]))
            elif client_socket.family == socket.AF_UNIX:
                interface_name = f"{self.clients}@{self.socket_path}"

            spawned_interface = LocalClientInterface(self.owner, name=interface_name, connected_socket=client_socket)
            spawned_interface.OUT = self.OUT
            spawned_interface.IN  = self.IN
            spawned_interface.socket = client_socket
            spawned_interface.parent_interface = self
            spawned_interface.bitrate = self.bitrate

            if client_socket.family == socket.AF_INET:
                spawned_interface.target_ip = client_socket.getpeername()[0]
                spawned_interface.target_port = str(client_socket.getpeername()[1])

            elif client_socket.family == socket.AF_UNIX:
                spawned_interface.target_ip = None
                spawned_interface.target_port = interface_name
                spawned_interface.socket_path = self.socket_path

            if hasattr(self, "_force_bitrate"): spawned_interface._force_bitrate = self._force_bitrate
            RNS.Transport.interfaces.append(spawned_interface)
            RNS.Transport.local_client_interfaces.append(spawned_interface)
            BackboneInterface.add_client_socket(client_socket, spawned_interface)
            self.clients += 1
            return True

        else:
            interface_name = str(str(handler.client_address[1]))
            spawned_interface = LocalClientInterface(self.owner, name=interface_name, connected_socket=handler.request)
            spawned_interface.OUT = self.OUT
            spawned_interface.IN  = self.IN
            spawned_interface.target_ip = handler.client_address[0]
            spawned_interface.target_port = str(handler.client_address[1])
            spawned_interface.parent_interface = self
            spawned_interface.bitrate = self.bitrate
            if hasattr(self, "_force_bitrate"): spawned_interface._force_bitrate = self._force_bitrate
            RNS.Transport.interfaces.append(spawned_interface)
            RNS.Transport.local_client_interfaces.append(spawned_interface)
            self.clients += 1
            spawned_interface.read_loop()

    def process_outgoing(self, data):
        pass

    def received_announce(self, from_spawned=False):
        if from_spawned: self.ia_freq_deque.append(time.time())

    def sent_announce(self, from_spawned=False):
        if from_spawned: self.oa_freq_deque.append(time.time())

    def __str__(self):
        if self.socket_path: return "Shared Instance["+str(self.socket_path.replace("\0", ""))+"]"
        else: return "Shared Instance["+str(self.bind_port)+"]"

class LocalInterfaceHandler(socketserver.BaseRequestHandler):
    def __init__(self, callback, *args, **keys):
        self.callback = callback
        socketserver.BaseRequestHandler.__init__(self, *args, **keys)

    def handle(self):
        self.callback(handler=self)