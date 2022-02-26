from .vendor.platformutils import get_platform

if get_platform() == "android":
    from .Interfaces import Interface
    from .Interfaces import LocalInterface
    from .Interfaces import AutoInterface
    from .Interfaces import TCPInterface
    from .Interfaces import UDPInterface
    from .Interfaces import I2PInterface
else:
    from .Interfaces import *

from .vendor.configobj import ConfigObj
import configparser
import multiprocessing.connection
import signal
import threading
import atexit
import struct
import array
import os.path
import os
import RNS

class Reticulum:
    """
    This class is used to initialise access to Reticulum within a
    program. You must create exactly one instance of this class before
    carrying out any other RNS operations, such as creating destinations
    or sending traffic. Every independently executed program must create
    their own instance of the Reticulum class, but Reticulum will
    automatically handle inter-program communication on the same system,
    and expose all connected programs to external interfaces as well.

    As soon as an instance of this class is created, Reticulum will start
    opening and configuring any hardware devices specified in the supplied
    configuration.

    Currently the first running instance must be kept running while other
    local instances are connected, as the first created instance will
    act as a master instance that directly communicates with external
    hardware such as modems, TNCs and radios. If a master instance is
    asked to exit, it will not exit until all client processes have
    terminated (unless killed forcibly).

    If you are running Reticulum on a system with several different
    programs that use RNS starting and terminating at different times,
    it will be advantageous to run a master RNS instance as a daemon for
    other programs to use on demand.
    """

    # Future minimum will probably be locked in at 244 bytes to support
    # networks with segments of different MTUs. Absolute minimum is 211.
    MTU            = 500
    """
    The MTU that Reticulum adheres to, and will expect other peers to
    adhere to. By default, the MTU is 500 bytes. In custom RNS network
    implementations, it is possible to change this value, but doing so will
    completely break compatibility with all other RNS networks. An identical
    MTU is a prerequisite for peers to communicate in the same network.

    Unless you really know what you are doing, the MTU should be left at
    the default value.
    """

    # TODO: To reach the 300bps level without unreasonably impacting
    # performance on faster links, we need a mechanism for setting
    # this value more intelligently. One option could be inferring it
    # from interface speed, but a better general approach would most
    # probably be to let Reticulum somehow continously build a map of
    # per-hop latencies and use this map for the timeout calculation. 
    DEFAULT_PER_HOP_TIMEOUT = 5

    # Length of truncated hashes in bits.
    TRUNCATED_HASHLENGTH = 80

    HEADER_MINSIZE = 2+1+(TRUNCATED_HASHLENGTH//8)*1
    HEADER_MAXSIZE = 2+1+(TRUNCATED_HASHLENGTH//8)*2
    
    MDU            = MTU - HEADER_MAXSIZE

    router         = None
    config         = None
    
    # The default configuration path will be expanded to a directory
    # named ".reticulum" inside the current users home directory
    configdir    = os.path.expanduser("~")+"/.reticulum"
    configpath   = ""
    storagepath  = ""
    cachepath    = ""
    
    @staticmethod
    def exit_handler():
        # This exit handler is called whenever Reticulum is asked to
        # shut down, and will in turn call exit handlers in other
        # classes, saving necessary information to disk and carrying
        # out cleanup operations.

        RNS.Transport.exit_handler()
        RNS.Identity.exit_handler()

    @staticmethod
    def sigint_handler(signal, frame):
        RNS.Transport.detach_interfaces()
        RNS.exit()


    @staticmethod
    def sigterm_handler(signal, frame):
        RNS.Transport.detach_interfaces()
        RNS.exit()


    def __init__(self,configdir=None, loglevel=None):
        """
        Initialises and starts a Reticulum instance. This must be
        done before any other operations, and Reticulum will not
        pass any traffic before being instantiated.

        :param configdir: Full path to a Reticulum configuration directory.
        """

        RNS.vendor.platformutils.platform_checks()

        if configdir != None:
            Reticulum.configdir = configdir
        
        Reticulum.configpath    = Reticulum.configdir+"/config"
        Reticulum.storagepath   = Reticulum.configdir+"/storage"
        Reticulum.cachepath     = Reticulum.configdir+"/storage/cache"
        Reticulum.resourcepath  = Reticulum.configdir+"/storage/resources"

        Reticulum.__transport_enabled = False
        Reticulum.__use_implicit_proof = True

        Reticulum.panic_on_interface_error = False

        self.local_interface_port = 37428
        self.local_control_port   = 37429
        self.share_instance       = True
        self.rpc_listener         = None

        self.requested_loglevel = loglevel
        if self.requested_loglevel != None:
            if self.requested_loglevel > RNS.LOG_EXTREME:
                self.requested_loglevel = RNS.LOG_EXTREME
            if self.requested_loglevel < RNS.LOG_CRITICAL:
                self.requested_loglevel = RNS.LOG_CRITICAL

            RNS.loglevel = self.requested_loglevel

        self.is_shared_instance = False
        self.is_connected_to_shared_instance = False
        self.is_standalone_instance = False

        if not os.path.isdir(Reticulum.storagepath):
            os.makedirs(Reticulum.storagepath)

        if not os.path.isdir(Reticulum.cachepath):
            os.makedirs(Reticulum.cachepath)

        if not os.path.isdir(Reticulum.resourcepath):
            os.makedirs(Reticulum.resourcepath)

        if os.path.isfile(self.configpath):
            try:
                self.config = ConfigObj(self.configpath)
            except Exception as e:
                RNS.log("Could not parse the configuration at "+self.configpath, RNS.LOG_ERROR)
                RNS.log("Check your configuration file for errors!", RNS.LOG_ERROR)
                RNS.panic()
        else:
            RNS.log("Could not load config file, creating default configuration file...")
            self.__create_default_config()
            RNS.log("Default config file created. Make any necessary changes in "+Reticulum.configdir+"/config and restart Reticulum if needed.")
            import time
            time.sleep(1.5)

        self.__apply_config()
        RNS.log("Configuration loaded from "+self.configpath, RNS.LOG_VERBOSE)
        
        RNS.Identity.load_known_destinations()

        RNS.Transport.start(self)

        self.rpc_addr = ("127.0.0.1", self.local_control_port)
        self.rpc_key  = RNS.Identity.full_hash(RNS.Transport.identity.get_private_key())
        
        if self.is_shared_instance:
            self.rpc_listener = multiprocessing.connection.Listener(self.rpc_addr, authkey=self.rpc_key)
            thread = threading.Thread(target=self.rpc_loop)
            thread.setDaemon(True)
            thread.start()

        atexit.register(Reticulum.exit_handler)
        signal.signal(signal.SIGINT, Reticulum.sigint_handler)
        signal.signal(signal.SIGTERM, Reticulum.sigterm_handler)

    def __start_local_interface(self):
        if self.share_instance:
            try:
                interface = LocalInterface.LocalServerInterface(
                    RNS.Transport,
                    self.local_interface_port
                )
                interface.OUT = True
                RNS.Transport.interfaces.append(interface)
                
                self.is_shared_instance = True
                RNS.log("Started shared instance interface: "+str(interface), RNS.LOG_DEBUG)
            except Exception as e:
                try:
                    interface = LocalInterface.LocalClientInterface(
                        RNS.Transport,
                        "Local shared instance",
                        self.local_interface_port)
                    interface.target_port = self.local_interface_port
                    interface.OUT = True
                    RNS.Transport.interfaces.append(interface)
                    self.is_shared_instance = False
                    self.is_standalone_instance = False
                    self.is_connected_to_shared_instance = True
                    Reticulum.__transport_enabled = False
                    RNS.log("Connected to local shared instance via: "+str(interface), RNS.LOG_DEBUG)
                except Exception as e:
                    RNS.log("Local shared instance appears to be running, but it could not be connected", RNS.LOG_ERROR)
                    RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                    self.is_shared_instance = False
                    self.is_standalone_instance = True
                    self.is_connected_to_shared_instance = False
        else:
            self.is_shared_instance = False
            self.is_standalone_instance = True
            self.is_connected_to_shared_instance = False

    def __apply_config(self):
        if "logging" in self.config:
            for option in self.config["logging"]:
                value = self.config["logging"][option]
                if option == "loglevel" and self.requested_loglevel == None:
                    RNS.loglevel = int(value)
                    if RNS.loglevel < 0:
                        RNS.loglevel = 0
                    if RNS.loglevel > 7:
                        RNS.loglevel = 7

        if "reticulum" in self.config:
            for option in self.config["reticulum"]:
                value = self.config["reticulum"][option]
                if option == "share_instance":
                    value = self.config["reticulum"].as_bool(option)
                    self.share_instance = value
                if option == "shared_instance_port":
                    value = int(self.config["reticulum"][option])
                    self.local_interface_port = value
                if option == "instance_control_port":
                    value = int(self.config["reticulum"][option])
                    self.local_control_port = value
                if option == "enable_transport":
                    v = self.config["reticulum"].as_bool(option)
                    if v == True:
                        Reticulum.__transport_enabled = True
                if option == "panic_on_interface_error":
                    v = self.config["reticulum"].as_bool(option)
                    if v == True:
                        Reticulum.panic_on_interface_error = True
                if option == "use_implicit_proof":
                    v = self.config["reticulum"].as_bool(option)
                    if v == True:
                        Reticulum.__use_implicit_proof = True
                    if v == False:
                        Reticulum.__use_implicit_proof = False

        self.__start_local_interface()

        if self.is_shared_instance or self.is_standalone_instance:
            RNS.log("Bringing up system interfaces...", RNS.LOG_DEBUG)
            interface_names = []
            for name in self.config["interfaces"]:
                if not name in interface_names:
                    c = self.config["interfaces"][name]

                    interface_mode = Interface.Interface.MODE_FULL
                    
                    if "mode" in c:
                        if c["mode"] == "full":
                            interface_mode = Interface.Interface.MODE_FULL
                        elif c["mode"] == "accesspoint" or c["mode"] == "ap":
                            interface_mode = Interface.Interface.MODE_ACCESS_POINT
                        elif c["mode"] == "pointtopoint" or c["mode"] == "ptp":
                            interface_mode = Interface.Interface.MODE_POINT_TO_POINT

                    try:
                        if ("interface_enabled" in c) and c.as_bool("interface_enabled") == True:
                            if c["type"] == "AutoInterface":
                                if not RNS.vendor.platformutils.is_windows():
                                    group_id        = c["group_id"] if "group_id" in c else None
                                    discovery_scope = c["discovery_scope"] if "discovery_scope" in c else None
                                    discovery_port  = int(c["discovery_port"]) if "discovery_port" in c else None
                                    data_port  = int(c["data_port"]) if "data_port" in c else None
                                    allowed_interfaces = c.as_list("devices") if "devices" in c else None
                                    ignored_interfaces = c.as_list("ignored_devices") if "ignored_devices" in c else None

                                    interface = AutoInterface.AutoInterface(
                                        RNS.Transport,
                                        name,
                                        group_id,
                                        discovery_scope,
                                        discovery_port,
                                        data_port,
                                        allowed_interfaces,
                                        ignored_interfaces
                                    )

                                    if "outgoing" in c and c.as_bool("outgoing") == False:
                                        interface.OUT = False
                                    else:
                                        interface.OUT = True

                                    interface.mode = interface_mode

                                    RNS.Transport.interfaces.append(interface)
                                else:
                                    RNS.log("AutoInterface is not currently supported on Windows, disabling interface.", RNS.LOG_ERROR);
                                    RNS.log("Please remove this AutoInterface instance from your configuration file.", RNS.LOG_ERROR);
                                    RNS.log("You will have to manually configure other interfaces for connectivity.", RNS.LOG_ERROR);


                            if c["type"] == "UDPInterface":
                                device       = c["device"] if "device" in c else None
                                port         = int(c["port"]) if "port" in c else None
                                listen_ip    = c["listen_ip"] if "listen_ip" in c else None
                                listen_port  = int(c["listen_port"]) if "listen_port" in c else None
                                forward_ip   = c["forward_ip"] if "forward_ip" in c else None
                                forward_port = int(c["forward_port"]) if "forward_port" in c else None

                                if port != None:
                                    if listen_port == None:
                                        listen_port = port
                                    if forward_port == None:
                                        forward_port = port

                                interface = UDPInterface.UDPInterface(
                                    RNS.Transport,
                                    name,
                                    device,
                                    listen_ip,
                                    listen_port,
                                    forward_ip,
                                    forward_port
                                )

                                if "outgoing" in c and c.as_bool("outgoing") == False:
                                    interface.OUT = False
                                else:
                                    interface.OUT = True

                                interface.mode = interface_mode

                                RNS.Transport.interfaces.append(interface)


                            if c["type"] == "TCPServerInterface":
                                device       = c["device"] if "device" in c else None
                                port         = int(c["port"]) if "port" in c else None
                                listen_ip    = c["listen_ip"] if "listen_ip" in c else None
                                listen_port  = int(c["listen_port"]) if "listen_port" in c else None
                                i2p_tunneled = c.as_bool("i2p_tunneled") if "i2p_tunneled" in c else False

                                if port != None:
                                    listen_port = port

                                interface = TCPInterface.TCPServerInterface(
                                    RNS.Transport,
                                    name,
                                    device,
                                    listen_ip,
                                    listen_port,
                                    i2p_tunneled
                                )

                                if "outgoing" in c and c.as_bool("outgoing") == False:
                                    interface.OUT = False
                                else:
                                    interface.OUT = True

                                if interface_mode != Interface.Interface.MODE_FULL:
                                    RNS.log(str(interface)+" does not support Access Point mode, reverting to default mode: Full", RNS.LOG_WARNING)
                                    interface_mode = Interface.Interface.MODE_FULL
                                
                                interface.mode = interface_mode

                                RNS.Transport.interfaces.append(interface)


                            if c["type"] == "TCPClientInterface":
                                kiss_framing = False
                                if "kiss_framing" in c and c.as_bool("kiss_framing") == True:
                                    kiss_framing = True
                                i2p_tunneled = c.as_bool("i2p_tunneled") if "i2p_tunneled" in c else False


                                interface = TCPInterface.TCPClientInterface(
                                    RNS.Transport,
                                    name,
                                    c["target_host"],
                                    int(c["target_port"]),
                                    kiss_framing = kiss_framing,
                                    i2p_tunneled = i2p_tunneled
                                )

                                if "outgoing" in c and c.as_bool("outgoing") == False:
                                    interface.OUT = False
                                else:
                                    interface.OUT = True

                                if interface_mode != Interface.Interface.MODE_FULL:
                                    RNS.log(str(interface)+" does not support Access Point mode, reverting to default mode: Full", RNS.LOG_WARNING)
                                    interface_mode = Interface.Interface.MODE_FULL
                                
                                interface.mode = interface_mode

                                RNS.Transport.interfaces.append(interface)


                            if c["type"] == "I2PInterface":
                                i2p_peers = c.as_list("peers") if "peers" in c else None
                                connectable = c.as_bool("connectable") if "connectable" in c else False

                                interface = I2PInterface.I2PInterface(
                                    RNS.Transport,
                                    name,
                                    Reticulum.storagepath,
                                    i2p_peers,
                                    connectable = connectable,
                                )

                                if "outgoing" in c and c.as_bool("outgoing") == False:
                                    interface.OUT = False
                                else:
                                    interface.OUT = True

                                if interface_mode != Interface.Interface.MODE_FULL:
                                    RNS.log(str(interface)+" does not support Access Point mode, reverting to default mode: Full", RNS.LOG_WARNING)
                                    interface_mode = Interface.Interface.MODE_FULL
                                
                                interface.mode = interface_mode

                                RNS.Transport.interfaces.append(interface)


                            if c["type"] == "SerialInterface":
                                port = c["port"] if "port" in c else None
                                speed = int(c["speed"]) if "speed" in c else 9600
                                databits = int(c["databits"]) if "databits" in c else 8
                                parity = c["parity"] if "parity" in c else "N"
                                stopbits = int(c["stopbits"]) if "stopbits" in c else 1

                                if port == None:
                                    raise ValueError("No port specified for serial interface")

                                interface = SerialInterface.SerialInterface(
                                    RNS.Transport,
                                    name,
                                    port,
                                    speed,
                                    databits,
                                    parity,
                                    stopbits
                                )

                                if "outgoing" in c and c.as_bool("outgoing") == False:
                                    interface.OUT = False
                                else:
                                    interface.OUT = True

                                interface.mode = interface_mode

                                RNS.Transport.interfaces.append(interface)

                            if c["type"] == "KISSInterface":
                                preamble = int(c["preamble"]) if "preamble" in c else None
                                txtail = int(c["txtail"]) if "txtail" in c else None
                                persistence = int(c["persistence"]) if "persistence" in c else None
                                slottime = int(c["slottime"]) if "slottime" in c else None
                                flow_control = c.as_bool("flow_control") if "flow_control" in c else False
                                port = c["port"] if "port" in c else None
                                speed = int(c["speed"]) if "speed" in c else 9600
                                databits = int(c["databits"]) if "databits" in c else 8
                                parity = c["parity"] if "parity" in c else "N"
                                stopbits = int(c["stopbits"]) if "stopbits" in c else 1
                                beacon_interval = int(c["id_interval"]) if "id_interval" in c else None
                                beacon_data = c["id_callsign"] if "id_callsign" in c else None

                                if port == None:
                                    raise ValueError("No port specified for serial interface")

                                interface = KISSInterface.KISSInterface(
                                    RNS.Transport,
                                    name,
                                    port,
                                    speed,
                                    databits,
                                    parity,
                                    stopbits,
                                    preamble,
                                    txtail,
                                    persistence,
                                    slottime,
                                    flow_control,
                                    beacon_interval,
                                    beacon_data
                                )

                                if "outgoing" in c and c.as_bool("outgoing") == False:
                                    interface.OUT = False
                                else:
                                    interface.OUT = True

                                interface.mode = interface_mode

                                RNS.Transport.interfaces.append(interface)

                            if c["type"] == "AX25KISSInterface":
                                preamble = int(c["preamble"]) if "preamble" in c else None
                                txtail = int(c["txtail"]) if "txtail" in c else None
                                persistence = int(c["persistence"]) if "persistence" in c else None
                                slottime = int(c["slottime"]) if "slottime" in c else None
                                flow_control = c.as_bool("flow_control") if "flow_control" in c else False
                                port = c["port"] if "port" in c else None
                                speed = int(c["speed"]) if "speed" in c else 9600
                                databits = int(c["databits"]) if "databits" in c else 8
                                parity = c["parity"] if "parity" in c else "N"
                                stopbits = int(c["stopbits"]) if "stopbits" in c else 1

                                callsign = c["callsign"] if "callsign" in c else ""
                                ssid = int(c["ssid"]) if "ssid" in c else -1

                                if port == None:
                                    raise ValueError("No port specified for serial interface")

                                interface = AX25KISSInterface.AX25KISSInterface(
                                    RNS.Transport,
                                    name,
                                    callsign,
                                    ssid,
                                    port,
                                    speed,
                                    databits,
                                    parity,
                                    stopbits,
                                    preamble,
                                    txtail,
                                    persistence,
                                    slottime,
                                    flow_control
                                )

                                if "outgoing" in c and c.as_bool("outgoing") == False:
                                    interface.OUT = False
                                else:
                                    interface.OUT = True

                                interface.mode = interface_mode

                                RNS.Transport.interfaces.append(interface)

                            if c["type"] == "RNodeInterface":
                                frequency = int(c["frequency"]) if "frequency" in c else None
                                bandwidth = int(c["bandwidth"]) if "bandwidth" in c else None
                                txpower = int(c["txpower"]) if "txpower" in c else None
                                spreadingfactor = int(c["spreadingfactor"]) if "spreadingfactor" in c else None
                                codingrate = int(c["codingrate"]) if "codingrate" in c else None
                                flow_control = c.as_bool("flow_control") if "flow_control" in c else False
                                id_interval = int(c["id_interval"]) if "id_interval" in c else None
                                id_callsign = c["id_callsign"] if "id_callsign" in c else None

                                port = c["port"] if "port" in c else None
                                
                                if port == None:
                                    raise ValueError("No port specified for RNode interface")

                                interface = RNodeInterface.RNodeInterface(
                                    RNS.Transport,
                                    name,
                                    port,
                                    frequency = frequency,
                                    bandwidth = bandwidth,
                                    txpower = txpower,
                                    sf = spreadingfactor,
                                    cr = codingrate,
                                    flow_control = flow_control,
                                    id_interval = id_interval,
                                    id_callsign = id_callsign
                                )

                                if "outgoing" in c and c.as_bool("outgoing") == False:
                                    interface.OUT = False
                                else:
                                    interface.OUT = True

                                interface.mode = interface_mode

                                RNS.Transport.interfaces.append(interface)
                        else:
                            RNS.log("Skipping disabled interface \""+name+"\"", RNS.LOG_DEBUG)

                    except Exception as e:
                        RNS.log("The interface \""+name+"\" could not be created. Check your configuration file for errors!", RNS.LOG_ERROR)
                        RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                        RNS.panic()
                else:
                    RNS.log("The interface name \""+name+"\" was already used. Check your configuration file for errors!", RNS.LOG_ERROR)
                    RNS.panic()

            RNS.log("System interfaces are ready", RNS.LOG_DEBUG)

                

    def __create_default_config(self):
        self.config = ConfigObj(__default_rns_config__)
        self.config.filename = Reticulum.configpath
        
        if not os.path.isdir(Reticulum.configdir):
            os.makedirs(Reticulum.configdir)
        self.config.write()

    def rpc_loop(self):
        while True:
            try:
                rpc_connection = self.rpc_listener.accept()
                call = rpc_connection.recv()

                if "get" in call:
                    path = call["get"]

                    if path == "interface_stats":
                        rpc_connection.send(self.get_interface_stats())

                    if path == "next_hop_if_name":
                        rpc_connection.send(self.get_next_hop_if_name(call["destination_hash"]))

                    if path == "next_hop":
                        rpc_connection.send(self.get_next_hop(call["destination_hash"]))

                    if path == "packet_rssi":
                        rpc_connection.send(self.get_packet_rssi(call["packet_hash"]))

                    if path == "packet_snr":
                        rpc_connection.send(self.get_packet_snr(call["packet_hash"]))

                rpc_connection.close()
            except Exception as e:
                RNS.log("An error ocurred while handling RPC call from local client: "+str(e), RNS.LOG_ERROR)

    def get_interface_stats(self):
        if self.is_connected_to_shared_instance:
            rpc_connection = multiprocessing.connection.Client(self.rpc_addr, authkey=self.rpc_key)
            rpc_connection.send({"get": "interface_stats"})
            response = rpc_connection.recv()
            return response
        else:
            stats = []
            for interface in RNS.Transport.interfaces:
                ifstats = {}
                
                if hasattr(interface, "clients"):
                    ifstats["clients"] = interface.clients
                else:
                    ifstats["clients"] = None

                if hasattr(interface, "b32"):
                    if interface.b32 != None:
                        ifstats["i2p_b32"] = interface.b32+".b32.i2p"
                    else:
                        ifstats["i2p_b32"] = None

                ifstats["name"] = str(interface)
                ifstats["rxb"] = interface.rxb
                ifstats["txb"] = interface.txb
                ifstats["status"] = interface.online
                stats.append(ifstats)

            return stats

    def get_next_hop_if_name(self, destination):
        if self.is_connected_to_shared_instance:
            rpc_connection = multiprocessing.connection.Client(self.rpc_addr, authkey=self.rpc_key)
            rpc_connection.send({"get": "next_hop_if_name", "destination_hash": destination})
            response = rpc_connection.recv()
            return response

        else:
            return str(RNS.Transport.next_hop_interface(destination))

    def get_next_hop(self, destination):
        if self.is_connected_to_shared_instance:
            rpc_connection = multiprocessing.connection.Client(self.rpc_addr, authkey=self.rpc_key)
            rpc_connection.send({"get": "next_hop", "destination_hash": destination})
            response = rpc_connection.recv()
            return response

        else:
            return RNS.Transport.next_hop(destination)

    def get_packet_rssi(self, packet_hash):
        if self.is_connected_to_shared_instance:
            rpc_connection = multiprocessing.connection.Client(self.rpc_addr, authkey=self.rpc_key)
            rpc_connection.send({"get": "packet_rssi", "packet_hash": packet_hash})
            response = rpc_connection.recv()
            return response

        else:
            for entry in RNS.Transport.local_client_rssi_cache:
                if entry[0] == packet_hash:
                    return entry[1]

            return None

    def get_packet_snr(self, packet_hash):
        if self.is_connected_to_shared_instance:
            rpc_connection = multiprocessing.connection.Client(self.rpc_addr, authkey=self.rpc_key)
            rpc_connection.send({"get": "packet_snr", "packet_hash": packet_hash})
            response = rpc_connection.recv()
            return response

        else:
            for entry in RNS.Transport.local_client_snr_cache:
                if entry[0] == packet_hash:
                    return entry[1]

            return None


    @staticmethod
    def should_use_implicit_proof():
        """
        Returns whether proofs sent are explicit or implicit.

        :returns: True if the current running configuration specifies to use implicit proofs. False if not.
        """
        return Reticulum.__use_implicit_proof

    @staticmethod
    def transport_enabled():
        """
        Returns whether Transport is enabled for the running
        instance.

        When Transport is enabled, Reticulum will
        route traffic for other peers, respond to path requests
        and pass announces over the network.

        :returns: True if Transport is enabled, False if not.
        """
        return Reticulum.__transport_enabled

# Default configuration file:
__default_rns_config__ = '''# This is the default Reticulum config file.
# You should probably edit it to include any additional,
# interfaces and settings you might need.

# Only the most basic options are included in this default
# configuration. To see a more verbose, and much longer,
# configuration example, you can run the command:
# rnsd --exampleconfig


[reticulum]

# If you enable Transport, your system will route traffic
# for other peers, pass announces and serve path requests.
# This should be done for systems that are suited to act
# as transport nodes, ie. if they are stationary and
# always-on. This directive is optional and can be removed
# for brevity.

enable_transport = False


# By default, the first program to launch the Reticulum
# Network Stack will create a shared instance, that other
# programs can communicate with. Only the shared instance
# opens all the configured interfaces directly, and other
# local programs communicate with the shared instance over
# a local socket. This is completely transparent to the
# user, and should generally be turned on. This directive
# is optional and can be removed for brevity.

share_instance = Yes


# If you want to run multiple *different* shared instances
# on the same system, you will need to specify different
# shared instance ports for each. The defaults are given
# below, and again, these options can be left out if you
# don't need them.

shared_instance_port = 37428
instance_control_port = 37429


# You can configure Reticulum to panic and forcibly close
# if an unrecoverable interface error occurs, such as the
# hardware device for an interface disappearing. This is
# an optional directive, and can be left out for brevity.
# This behaviour is disabled by default.

panic_on_interface_error = No


[logging]
# Valid log levels are 0 through 7:
#   0: Log only critical information
#   1: Log errors and lower log levels
#   2: Log warnings and lower log levels
#   3: Log notices and lower log levels
#   4: Log info and lower (this is the default)
#   5: Verbose logging
#   6: Debug logging
#   7: Extreme logging

loglevel = 4


# The interfaces section defines the physical and virtual
# interfaces Reticulum will use to communicate on. This
# section will contain examples for a variety of interface
# types. You can modify these or use them as a basis for
# your own config, or simply remove the unused ones.

[interfaces]

  # This interface enables communication with other
  # link-local Reticulum nodes over UDP. It does not
  # need any functional IP infrastructure like routers
  # or DHCP servers, but will require that at least link-
  # local IPv6 is enabled in your operating system, which
  # should be enabled by default in almost any OS. See
  # the Reticulum Manual for more configuration options.

  [[Default Interface]]
    type = AutoInterface
    interface_enabled = True

'''.splitlines()
