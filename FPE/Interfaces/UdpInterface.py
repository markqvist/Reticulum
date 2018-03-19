from Interface import Interface
import SocketServer
import threading
import socket
import sys

class UdpInterface(Interface):
    bind_ip = None
    bind_port = None
    forward_ip = None
    forward_port = None
    owner = None

    def __init__(self, owner, bindip=None, bindport=None, forwardip=None, forwardport=None):
        self.IN  = True
        self.OUT = False

        if (bindip != None and bindport != None):
            self.receives = True
            self.bind_ip = bindip
            self.bind_port = bindport

            UdpInterfaceHandler.interface = self
            self.owner = owner
            address = (self.bind_ip, self.bind_port)
            self.server = SocketServer.UDPServer(address, UdpInterfaceHandler)

            thread = threading.Thread(target=self.server.serve_forever)
            thread.setDaemon(True)
            thread.start()

        if (forwardip != None and forwardport != None):
            self.forwards = True
            self.forward_ip = forwardip
            self.forward_port = forwardport


    def processIncoming(self, data):
        self.owner.inbound(data)

    def processOutgoing(self,data):
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_socket.sendto(data, (self.forward_ip, self.forward_port))


    def __str__(self):
        return "UdpInterface["+self.bind_ip+":"+str(self.bind_port)+"]"

class UdpInterfaceHandler(SocketServer.BaseRequestHandler):
    interface = None

    def handle(self):
        if (UdpInterfaceHandler.interface != None):
            data = self.request[0].strip()
            UdpInterfaceHandler.interface.processIncoming(data)