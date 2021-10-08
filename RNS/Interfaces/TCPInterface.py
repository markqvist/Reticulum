from .Interface import Interface
import socketserver
import threading
import netifaces
import platform
import socket
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

class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

class TCPClientInterface(Interface):
    RECONNECT_WAIT = 5
    RECONNECT_MAX_TRIES = None

    # TCP socket options
    TCP_USER_TIMEOUT = 20
    TCP_PROBE_AFTER = 5
    TCP_PROBE_INTERVAL = 3
    TCP_PROBES = 5

    def __init__(self, owner, name, target_ip=None, target_port=None, connected_socket=None, max_reconnect_tries=None):
        self.rxb = 0
        self.txb = 0
        
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

        elif target_ip != None and target_port != None:
            self.receives    = True
            self.target_ip   = target_ip
            self.target_port = target_port
            self.initiator   = True
            
            if not self.connect(initial=True):
                thread = threading.Thread(target=self.reconnect)
                thread.setDaemon(True)
                thread.start()
            else:
                thread = threading.Thread(target=self.read_loop)
                thread.setDaemon(True)
                thread.start()
                self.wants_tunnel = True


    def set_timeouts_linux(self):
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT, int(TCPClientInterface.TCP_USER_TIMEOUT * 1000))

        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, int(TCPClientInterface.TCP_PROBE_AFTER))
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, int(TCPClientInterface.TCP_PROBE_INTERVAL))
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, int(TCPClientInterface.TCP_PROBES))

    def set_timeouts_osx(self):
        if hasattr(socket, "TCP_KEEPALIVE"):
            TCP_KEEPIDLE = socket.TCP_KEEPALIVE
        else:
            TCP_KEEPIDLE = 0x10

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, TCP_KEEPIDLE, int(TCPClientInterface.TCP_PROBE_AFTER))

    def detach(self):
        if self.socket != None:
            if hasattr(self.socket, "close"):
                if callable(self.socket.close):
                    RNS.log("Detaching "+str(self), RNS.LOG_DEBUG)
                    self.detached = True
                    
                    try:
                        self.socket.shutdown(socket.SHUT_RDWR)
                    except Exception as e:
                        RNS.log("Error while shutting down socket for "+str(self)+": "+str(e))

                    try:
                        self.socket.close()
                    except Exception as e:
                        RNS.log("Error while closing socket for "+str(self)+": "+str(e))

                    self.socket = None

    def connect(self, initial=False):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.target_ip, self.target_port))
            self.online  = True
        
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
                    RNS.log("Reconnected TCP socket for "+str(self)+".", RNS.LOG_INFO)

                self.reconnecting = False
                thread = threading.Thread(target=self.read_loop)
                thread.setDaemon(True)
                thread.start()
                RNS.Transport.synthesize_tunnel(self)

        else:
            RNS.log("Attempt to reconnect on a non-initiator TCP interface. This should not happen.", RNS.LOG_ERROR)
            raise IOError("Attempt to reconnect on a non-initiator TCP interface")

    def processIncoming(self, data):
        self.rxb += len(data)
        if hasattr(self, "parent_interface") and self.parent_interface != None:
            self.parent_interface.rxb += len(data)
                    
        self.owner.inbound(data, self)

    def processOutgoing(self, data):
        if self.online:
            while self.writing:
                time.sleep(0.01)

            try:
                self.writing = True
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
            data_buffer = b""

            while True:
                data_in = self.socket.recv(4096)
                if len(data_in) > 0:
                    pointer = 0
                    while pointer < len(data_in):
                        byte = data_in[pointer]
                        pointer += 1
                        if (in_frame and byte == HDLC.FLAG):
                            in_frame = False
                            self.processIncoming(data_buffer)
                        elif (byte == HDLC.FLAG):
                            in_frame = True
                            data_buffer = b""
                        elif (in_frame and len(data_buffer) < RNS.Reticulum.MTU):
                            if (byte == HDLC.ESC):
                                escape = True
                            else:
                                if (escape):
                                    if (byte == HDLC.FLAG ^ HDLC.ESC_MASK):
                                        byte = HDLC.FLAG
                                    if (byte == HDLC.ESC  ^ HDLC.ESC_MASK):
                                        byte = HDLC.ESC
                                    escape = False
                                data_buffer = data_buffer+bytes([byte])
                else:
                    self.online = False
                    if self.initiator and not self.detached:
                        RNS.log("TCP socket for "+str(self)+" was closed, attempting to reconnect...", RNS.LOG_WARNING)
                        self.reconnect()
                    else:
                        RNS.log("TCP socket for remote client "+str(self)+" was closed.", RNS.LOG_VERBOSE)
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
            self.parent_interface.clients -= 1

        if self in RNS.Transport.interfaces:
            if not self.initiator:
                RNS.Transport.interfaces.remove(self)


    def __str__(self):
        return "TCPInterface["+str(self.name)+"/"+str(self.target_ip)+":"+str(self.target_port)+"]"


class TCPServerInterface(Interface):
    @staticmethod
    def get_address_for_if(name):
        return netifaces.ifaddresses(name)[netifaces.AF_INET][0]['addr']

    def get_broadcast_for_if(name):
        return netifaces.ifaddresses(name)[netifaces.AF_INET][0]['broadcast']

    def __init__(self, owner, name, device=None, bindip=None, bindport=None):
        self.rxb = 0
        self.txb = 0
        self.online = False
        self.clients = 0
        
        self.IN  = True
        self.OUT = False
        self.name = name

        if device != None:
            bindip = TCPServerInterface.get_address_for_if(device)

        if (bindip != None and bindport != None):
            self.receives = True
            self.bind_ip = bindip
            self.bind_port = bindport

            def handlerFactory(callback):
                def createHandler(*args, **keys):
                    return TCPInterfaceHandler(callback, *args, **keys)
                return createHandler

            self.owner = owner
            address = (self.bind_ip, self.bind_port)

            ThreadingTCPServer.allow_reuse_address = True
            self.server = ThreadingTCPServer(address, handlerFactory(self.incoming_connection))

            thread = threading.Thread(target=self.server.serve_forever)
            thread.setDaemon(True)
            thread.start()

            self.online = True


    def incoming_connection(self, handler):
        RNS.log("Accepting incoming TCP connection", RNS.LOG_VERBOSE)
        interface_name = "Client on "+self.name
        spawned_interface = TCPClientInterface(self.owner, interface_name, target_ip=None, target_port=None, connected_socket=handler.request)
        spawned_interface.OUT = self.OUT
        spawned_interface.IN  = self.IN
        spawned_interface.target_ip = handler.client_address[0]
        spawned_interface.target_port = str(handler.client_address[1])
        spawned_interface.parent_interface = self
        spawned_interface.online = True
        RNS.log("Spawned new TCPClient Interface: "+str(spawned_interface), RNS.LOG_VERBOSE)
        RNS.Transport.interfaces.append(spawned_interface)
        self.clients += 1
        spawned_interface.read_loop()

    def processOutgoing(self, data):
        pass

    def __str__(self):
        return "TCPServerInterface["+self.name+"/"+self.bind_ip+":"+str(self.bind_port)+"]"

class TCPInterfaceHandler(socketserver.BaseRequestHandler):
    def __init__(self, callback, *args, **keys):
        self.callback = callback
        socketserver.BaseRequestHandler.__init__(self, *args, **keys)

    def handle(self):
        self.callback(handler=self)