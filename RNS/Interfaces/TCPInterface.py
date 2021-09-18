from .Interface import Interface
import socketserver
import threading
import netifaces
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

    def __init__(self, owner, name, target_ip=None, target_port=None, connected_socket=None, max_reconnect_tries=None):
        self.IN               = True
        self.OUT              = False
        self.socket           = None
        self.parent_interface = None
        self.name             = name
        self.initiator        = False

        if max_reconnect_tries == None:
            self.max_reconnect_tries = TCPClientInterface.RECONNECT_MAX_TRIES
        else:
            self.max_reconnect_tries = max_reconnect_tries

        if connected_socket != None:
            self.receives    = True
            self.target_ip   = None
            self.target_port = None
            self.socket      = connected_socket

        elif target_ip != None and target_port != None:
            self.receives    = True
            self.target_ip   = target_ip
            self.target_port = target_port

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.target_ip, self.target_port))

        self.owner   = owner
        self.online  = True
        self.writing = False

        if connected_socket == None:
            self.initiator = True
            thread = threading.Thread(target=self.read_loop)
            thread.setDaemon(True)
            thread.start()
            self.wants_tunnel = True

    def reconnect(self):
        if self.initiator:
            attempts = 0
            while not self.online:
                attempts += 1

                if self.max_reconnect_tries != None and attempts > self.max_reconnect_tries:
                    RNS.log("Max reconnection attempts reached for "+str(self), RNS.LOG_ERROR)
                    self.teardown()
                    break

                try:
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.socket.connect((self.target_ip, self.target_port))
                    self.online  = True
                    self.writing = False

                    thread = threading.Thread(target=self.read_loop)
                    thread.setDaemon(True)
                    thread.start()
                    RNS.Transport.synthesize_tunnel(self)

                except Exception as e:
                    RNS.log("Reconnection attempt for "+str(self)+" failed. The contained exception was: "+str(e), RNS.LOG_ERROR)

                time.sleep(TCPClientInterface.RECONNECT_WAIT)

        else:
            RNS.log("Attempt to reconnect on a non-initiator TCP interface. This should not happen.", RNS.LOG_ERROR)
            raise IOError("Attempt to reconnect on a non-initiator TCP interface")

    def processIncoming(self, data):
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
                    RNS.log("TCP socket for "+str(self)+" was closed, attempting to reconnect...", RNS.LOG_WARNING)
                    self.online = False
                    if self.initiator:
                        self.reconnect()

                    break

                
        except Exception as e:
            self.online = False
            RNS.log("An interface error occurred, the contained exception was: "+str(e), RNS.LOG_ERROR)
            self.teardown()

    def teardown(self):
        RNS.log("The interface "+str(self)+" experienced an unrecoverable error and is being torn down. Restart Reticulum to attempt to open this interface again.", RNS.LOG_ERROR)
        self.online = False
        self.OUT = False
        self.IN = False
        if self in RNS.Transport.interfaces:
            RNS.Transport.interfaces.remove(self)

        if RNS.Reticulum.panic_on_interface_error:
            RNS.panic()


    def __str__(self):
        return "TCPInterface["+str(self.name)+"/"+str(self.target_ip)+":"+str(self.target_port)+"]"


class TCPServerInterface(Interface):
    @staticmethod
    def get_address_for_if(name):
        return netifaces.ifaddresses(name)[netifaces.AF_INET][0]['addr']

    def get_broadcast_for_if(name):
        return netifaces.ifaddresses(name)[netifaces.AF_INET][0]['broadcast']

    def __init__(self, owner, name, device=None, bindip=None, bindport=None):
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
            self.server = ThreadingTCPServer(address, handlerFactory(self.incoming_connection))

            thread = threading.Thread(target=self.server.serve_forever)
            thread.setDaemon(True)
            thread.start()


    def incoming_connection(self, handler):
        RNS.log("Accepting incoming TCP connection", RNS.LOG_VERBOSE)
        interface_name = "Client on "+self.name
        spawned_interface = TCPClientInterface(self.owner, interface_name, target_ip=None, target_port=None, connected_socket=handler.request)
        spawned_interface.OUT = self.OUT
        spawned_interface.IN  = self.IN
        spawned_interface.target_ip = handler.client_address[0]
        spawned_interface.target_port = str(handler.client_address[1])
        spawned_interface.parent_interface = self
        RNS.log("Spawned new TCPClient Interface: "+str(spawned_interface), RNS.LOG_VERBOSE)
        RNS.Transport.interfaces.append(spawned_interface)
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