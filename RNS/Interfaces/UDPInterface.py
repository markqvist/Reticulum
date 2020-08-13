from .Interface import Interface
import socketserver
import threading
import socket
import time
import sys
import RNS

class UDPInterface(Interface):

    def __init__(self, owner, name, bindip=None, bindport=None, forwardip=None, forwardport=None):
        self.IN  = True
        self.OUT = False
        self.name = name

        if (bindip != None and bindport != None):
            self.receives = True
            self.bind_ip = bindip
            self.bind_port = bindport

            def handlerFactory(callback):
                def createHandler(*args, **keys):
                    return UDPInterfaceHandler(callback, *args, **keys)
                return createHandler

            self.owner = owner
            address = (self.bind_ip, self.bind_port)
            self.server = socketserver.UDPServer(address, handlerFactory(self.processIncoming))

            thread = threading.Thread(target=self.server.serve_forever)
            thread.setDaemon(True)
            thread.start()

        if (forwardip != None and forwardport != None):
            self.forwards = True
            self.forward_ip = forwardip
            self.forward_port = forwardport


    def processIncoming(self, data):
        self.owner.inbound(data, self)

    def processOutgoing(self,data):
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_socket.sendto(data, (self.forward_ip, self.forward_port))


    def __str__(self):
        return "UDPInterface["+self.name+"/"+self.bind_ip+":"+str(self.bind_port)+"]"

class UDPInterfaceHandler(socketserver.BaseRequestHandler):
    def __init__(self, callback, *args, **keys):
        self.callback = callback
        socketserver.BaseRequestHandler.__init__(self, *args, **keys)

    def handle(self):
        data = self.request[0]
        self.callback(data)