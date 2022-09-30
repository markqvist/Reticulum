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
import time
import sys
import RNS


class UDPInterface(Interface):
    BITRATE_GUESS = 10*1000*1000

    @staticmethod
    def get_address_for_if(name):
        import importlib
        if importlib.util.find_spec('netifaces') != None:
            import netifaces
            return netifaces.ifaddresses(name)[netifaces.AF_INET][0]['addr']
        else:
            RNS.log("Getting interface addresses from device names requires the netifaces module.", RNS.LOG_CRITICAL)
            RNS.log("You can install it with the command: python3 -m pip install netifaces", RNS.LOG_CRITICAL)
            RNS.panic()

    @staticmethod
    def get_broadcast_for_if(name):
        import importlib
        if importlib.util.find_spec('netifaces') != None:
            import netifaces
            return netifaces.ifaddresses(name)[netifaces.AF_INET][0]['broadcast']
        else:
            RNS.log("Getting interface addresses from device names requires the netifaces module.", RNS.LOG_CRITICAL)
            RNS.log("You can install it with the command: python3 -m pip install netifaces", RNS.LOG_CRITICAL)
            RNS.panic()

    def __init__(self, owner, name, device=None, bindip=None, bindport=None, forwardip=None, forwardport=None):
        self.rxb = 0
        self.txb = 0

        self.HW_MTU = 1064

        self.IN  = True
        self.OUT = False
        self.name = name
        self.online = False
        self.bitrate = UDPInterface.BITRATE_GUESS

        if device != None:
            if bindip == None:
                bindip = UDPInterface.get_broadcast_for_if(device)
            if forwardip == None:
                forwardip = UDPInterface.get_broadcast_for_if(device)


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
            socketserver.UDPServer.address_family = socket.AF_INET
            self.server = socketserver.UDPServer(address, handlerFactory(self.processIncoming))

            thread = threading.Thread(target=self.server.serve_forever)
            thread.daemon = True
            thread.start()

            self.online = True

        if (forwardip != None and forwardport != None):
            self.forwards = True
            self.forward_ip = forwardip
            self.forward_port = forwardport


    def processIncoming(self, data):
        self.rxb += len(data)
        self.owner.inbound(data, self)

    def processOutgoing(self,data):
        try:
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp_socket.sendto(data, (self.forward_ip, self.forward_port))
            self.txb += len(data)
            
        except Exception as e:
            RNS.log("Could not transmit on "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)


    def __str__(self):
        return "UDPInterface["+self.name+"/"+self.bind_ip+":"+str(self.bind_port)+"]"

class UDPInterfaceHandler(socketserver.BaseRequestHandler):
    def __init__(self, callback, *args, **keys):
        self.callback = callback
        socketserver.BaseRequestHandler.__init__(self, *args, **keys)

    def handle(self):
        data = self.request[0]
        self.callback(data)