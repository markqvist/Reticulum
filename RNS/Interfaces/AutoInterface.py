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
    SCOPE_GLOBAL       = "E"

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

    def __init__(self, owner, name, group_id=None, discovery_scope=None, discovery_port=None, data_port=None):
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
        self.IN  = True
        self.OUT = False
        self.name = name
        self.online = False
        self.peers = {}

        self.outbound_udp_socket = None

        if group_id == None:
            self.group_id = AutoInterface.DEFAULT_GROUP_ID
        else:
            self.group_id = group_id.encode("utf-8")

        self.group_hash = RNS.Identity.full_hash(self.group_id)

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

        suitable_interfaces = 0
        for ifname in self.netifaces.interfaces():
            addresses = self.netifaces.ifaddresses(ifname)
            if self.netifaces.AF_INET6 in addresses:
                link_local_addr = None
                for address in addresses[self.netifaces.AF_INET6]:
                    if "addr" in address:
                        if address["addr"].startswith("fe80:"):
                            link_local_addr = address["addr"]
                            RNS.log(str(self)+" Selecting link-local address "+str(link_local_addr)+" for interface "+str(ifname), RNS.LOG_EXTREME)

                if link_local_addr == None:
                    RNS.log(str(self)+" No link-local IPv6 address configured for "+str(ifname)+", skipping interface", RNS.LOG_EXTREME)
                else:
                    g = self.group_hash
                    gt = "{:02x}".format(g[1]+(g[0]<<8))+":"+"{:02x}".format(g[3]+(g[2]<<8))+":"+"{:02x}".format(g[5]+(g[4]<<8))+":"+"{:02x}".format(g[7]+(g[6]<<8))+":"+"{:02x}".format(g[9]+(g[8]<<8))+":"+"{:02x}".format(g[11]+(g[10]<<8))+":"+"{:02x}".format(g[13]+(g[12]<<8))
                    mcast_addr = "ff1"+self.discovery_scope+":"+gt

                    RNS.log(str(self)+" Creating multicast discovery listener on "+str(ifname)+" with address "+str(mcast_addr), RNS.LOG_EXTREME)

                    # Struct with interface index
                    if_struct = struct.pack("I", socket.if_nametoindex(ifname))

                    # Set up multicast socket
                    discovery_socket = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                    discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                    discovery_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, if_struct)

                    # Join multicast group
                    discovery_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, socket.inet_pton(socket.AF_INET6, mcast_addr) + if_struct)

                    # Bind socket
                    addr_info = socket.getaddrinfo(mcast_addr+"%"+ifname, self.discovery_port, socket.AF_INET6, socket.SOCK_DGRAM)
                    discovery_socket.bind(addr_info[0][4])

                    # Set up thread for discovery packets
                    def discovery_loop():
                        self.discovery_handler(discovery_socket, ifname)

                    thread = threading.Thread(target=discovery_loop)
                    thread.setDaemon(True)
                    thread.start()

                    suitable_interfaces += 1

        if suitable_interfaces == 0:
            RNS.log(str(self)+" could not autoconfigure connectivity. You will need to manually configure this instance.", RNS.LOG_WARNING)
        else:
            self.receives = True

            def handlerFactory(callback):
                def createHandler(*args, **keys):
                    return AutoInterfaceHandler(callback, *args, **keys)
                return createHandler

            self.owner = owner
            socketserver.UDPServer.address_family = socket.AF_INET6
            address = ("::", self.data_port)
            self.server = socketserver.UDPServer(address, handlerFactory(self.processIncoming))

            thread = threading.Thread(target=self.server.serve_forever)
            thread.setDaemon(True)
            thread.start()

            self.online = True


    def discovery_handler(self, socket, ifname):
        while True:
            data, ipv6_src = socket.recvfrom(1024)

            # TODO: Add real peer discovery integrity check
            if data.decode("utf-8") == "peer":
                self.add_peer(ipv6_src[0], ifname)

    def add_peer(self, addr, ifname):
        if not addr in self.peers:
            self.peers[addr] = [ifname, time.time()]
            RNS.log(str(self)+" added peer "+str(addr)+" on "+str(ifname), RNS.LOG_EXTREME)
        else:
            self.heard_peer(addr)

    def heard_peer(self, addr):
        self.peers[addr][1] = time.time()
        RNS.log(str(self)+" heard peer "+str(addr)+" on "+str(self.peers[addr][0]), RNS.LOG_EXTREME)

    def processIncoming(self, data):
        self.rxb += len(data)
        self.owner.inbound(data, self)

    def processOutgoing(self,data):
            for peer in self.peers:
                # TODO: Remove
                # RNS.log("Send to "+str(peer))
                try:
                    if self.outbound_udp_socket == None:
                        self.outbound_udp_socket = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                    
                    self.outbound_udp_socket.sendto(data, (peer, self.data_port))
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