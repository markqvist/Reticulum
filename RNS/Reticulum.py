from .Interfaces import *
import configparser
from .vendor.configobj import ConfigObj
import RNS
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

    # The default RNS MTU is 500 bytes. This number has been chosen as
    # a balance between compatibility with existing hardware devices
    # on one hand, and the ability to use sufficiently high cryptographic
    # key sizes on the other. In custom RNS network implementations, it
    # is possible to raise this value, but doing so will completely break
    # compatibility with all other RNS networks. An identical MTU is a
    # prerequisite for peers to communicate in the same network.
    MTU            = 500
    HEADER_MAXSIZE = 23
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

    def __init__(self,configdir=None):
        """
        Initialises and starts a Reticulum instance. This must be
        done before any other operations, and Reticulum will not
        pass any traffic before being instantiated.

        :param configdir: Full path to a Reticulum configuration directory.
        """

        if configdir != None:
            Reticulum.configdir = configdir
        
        Reticulum.configpath    = Reticulum.configdir+"/config"
        Reticulum.storagepath   = Reticulum.configdir+"/storage"
        Reticulum.cachepath     = Reticulum.configdir+"/storage/cache"
        Reticulum.resourcepath  = Reticulum.configdir+"/storage/resources"

        Reticulum.__allow_unencrypted = False
        Reticulum.__transport_enabled = False
        Reticulum.__use_implicit_proof = True

        self.local_interface_port = 37428
        self.share_instance = True

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
                RNS.log("Configuration loaded from "+self.configpath)
            except Exception as e:
                RNS.log("Could not parse the configuration at "+self.configpath, RNS.LOG_ERROR)
                RNS.log("Check your configuration file for errors!", RNS.LOG_ERROR)
                RNS.panic()
        else:
            RNS.log("Could not load config file, creating default configuration file...")
            self.__create_default_config()
            RNS.log("Default config file created. Make any necessary changes in "+Reticulum.configdir+"/config and start Reticulum again.")
            RNS.log("Exiting now!")
            exit(1)

        self.__apply_config()
        RNS.Identity.load_known_destinations()

        RNS.Transport.start(self)

        atexit.register(Reticulum.exit_handler)

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
                if option == "loglevel":
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
                if option == "enable_transport":
                    v = self.config["reticulum"].as_bool(option)
                    if v == True:
                        Reticulum.__transport_enabled = True
                if option == "use_implicit_proof":
                    v = self.config["reticulum"].as_bool(option)
                    if v == True:
                        Reticulum.__use_implicit_proof = True
                    if v == False:
                        Reticulum.__use_implicit_proof = False
                if option == "allow_unencrypted":
                    v = self.config["reticulum"].as_bool(option)
                    if v == True:
                        RNS.log("", RNS.LOG_CRITICAL)
                        RNS.log("! ! !     ! ! !     ! ! !", RNS.LOG_CRITICAL)
                        RNS.log("", RNS.LOG_CRITICAL)
                        RNS.log("Danger! Encryptionless links have been allowed in the config file!", RNS.LOG_CRITICAL)
                        RNS.log("Beware of the consequences! Any data sent over a link can potentially be intercepted,", RNS.LOG_CRITICAL)
                        RNS.log("read and modified! If you are not absolutely sure that you want this,", RNS.LOG_CRITICAL)
                        RNS.log("you should exit Reticulum NOW and change your config file!", RNS.LOG_CRITICAL)
                        RNS.log("", RNS.LOG_CRITICAL)
                        RNS.log("! ! !     ! ! !     ! ! !", RNS.LOG_CRITICAL)
                        RNS.log("", RNS.LOG_CRITICAL)
                        Reticulum.__allow_unencrypted = True

        self.__start_local_interface()

        if self.is_shared_instance or self.is_standalone_instance:
            interface_names = []
            for name in self.config["interfaces"]:
                if not name in interface_names:
                    c = self.config["interfaces"][name]

                    try:
                        if ("interface_enabled" in c) and c.as_bool("interface_enabled") == True:
                            if c["type"] == "UDPInterface":
                                interface = UDPInterface.UDPInterface(
                                    RNS.Transport,
                                    name,
                                    c["listen_ip"],
                                    int(c["listen_port"]),
                                    c["forward_ip"],
                                    int(c["forward_port"])
                                )

                                if "outgoing" in c and c.as_bool("outgoing") == True:
                                    interface.OUT = True
                                else:
                                    interface.OUT = False

                                RNS.Transport.interfaces.append(interface)


                            if c["type"] == "TCPServerInterface":
                                interface = TCPInterface.TCPServerInterface(
                                    RNS.Transport,
                                    name,
                                    c["listen_ip"],
                                    int(c["listen_port"])
                                )

                                if "outgoing" in c and c.as_bool("outgoing") == True:
                                    interface.OUT = True
                                else:
                                    interface.OUT = False

                                RNS.Transport.interfaces.append(interface)


                            if c["type"] == "TCPClientInterface":
                                interface = TCPInterface.TCPClientInterface(
                                    RNS.Transport,
                                    name,
                                    c["target_host"],
                                    int(c["target_port"])
                                )

                                if "outgoing" in c and c.as_bool("outgoing") == True:
                                    interface.OUT = True
                                else:
                                    interface.OUT = False

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

                                if "outgoing" in c and c["outgoing"].lower() == "true":
                                    interface.OUT = True
                                else:
                                    interface.OUT = False

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

                                if "outgoing" in c and c["outgoing"].lower() == "true":
                                    interface.OUT = True
                                else:
                                    interface.OUT = False

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

                                if "outgoing" in c and c["outgoing"].lower() == "true":
                                    interface.OUT = True
                                else:
                                    interface.OUT = False

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

                                if "outgoing" in c and c["outgoing"].lower() == "true":
                                    interface.OUT = True
                                else:
                                    interface.OUT = False

                                RNS.Transport.interfaces.append(interface)
                        else:
                            RNS.log("Skipping disabled interface \""+name+"\"", RNS.LOG_NOTICE)

                    except Exception as e:
                        RNS.log("The interface \""+name+"\" could not be created. Check your configuration file for errors!", RNS.LOG_ERROR)
                        RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                        RNS.panic()
                else:
                    RNS.log("The interface name \""+name+"\" was already used. Check your configuration file for errors!", RNS.LOG_ERROR)
                    RNS.panic()
                

    def __create_default_config(self):
        self.config = ConfigObj(__default_rns_config__)
        self.config.filename = Reticulum.configpath
        
        if not os.path.isdir(Reticulum.configdir):
            os.makedirs(Reticulum.configdir)
        self.config.write()
        self.__apply_config()

    @staticmethod
    def should_allow_unencrypted():
        """
        Returns whether unencrypted links are allowed by the
        current configuration.

        :returns: True if the current running configuration allows downgrading links to plaintext. False if not.
        """
        return Reticulum.__allow_unencrypted

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

[reticulum]

# Don't allow unencrypted links by default.
# If you REALLY need to allow unencrypted links, for example
# for debug or regulatory purposes, this can be set to true.
# This directive is optional and can be removed for brevity.

allow_unencrypted = False


# If you enable Transport, your system will route traffic
# for other peers, pass announces and serve path requests.
# Unless you really know what you're doing, this should be
# done only for systems that are suited to act as transport
# nodes, ie. if they are stationary and always-on. This
# directive is optional and can be removed for brevity.

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
# on the same system, you will need to specify a different
# shared instance port for each. The default is given below,
# and again, this option is optional and can be left out.

shared_instance_port = 37428


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
  # Reticulum nodes on your local ethernet networks.
  # It's enabled by default, and provides basic
  # connectivity to other peers in your local ethernet
  # broadcast domain. You can modify it to suit your
  # needs or turn it off completely.
  
  [[Default UDP Interface]]
    type = UDPInterface
    interface_enabled = True
    outgoing = True
    listen_ip = 0.0.0.0
    listen_port = 4242
    forward_ip = 255.255.255.255
    forward_port = 4242


  # This example demonstrates a TCP server interface.
  # It will listen for incoming connections on the
  # specified IP address and port number.
  
  [[TCP Server Interface]]
    type = TCPServerInterface
    interface_enabled = False
    outgoing = True
    listen_ip = 0.0.0.0
    listen_port = 4242


  # To connect to a TCP server interface, you would
  # naturally use the TCP client interface. Here's
  # an example. The target_host can either be an IP
  # address or a hostname

  [[TCP Client Interface]]
    type = TCPClientInterface
    interface_enabled = False
    outgoing = True
    target_host = 127.0.0.1
    target_port = 4242


  # Here's an example of how to add a LoRa interface
  # using the RNode LoRa transceiver.

  [[RNode LoRa Interface]]
    type = RNodeInterface

    # Enable interface if you want use it!
    interface_enabled = False

    # Allow transmit on interface. Setting
    # this to false will create a listen-
    # only interface.
    outgoing = true

    # Serial port for the device
    port = /dev/ttyUSB0

    # Set frequency to 867.2 MHz
    frequency = 867200000

    # Set LoRa bandwidth to 125 KHz
    bandwidth = 125000

    # Set TX power to 7 dBm (5 mW)
    txpower = 7

    # Select spreading factor 8. Valid 
    # range is 7 through 12, with 7
    # being the fastest and 12 having
    # the longest range.
    spreadingfactor = 8

    # Select coding rate 5. Valid range
    # is 5 throough 8, with 5 being the
    # fastest, and 8 the longest range.
    codingrate = 5

    # You can configure the RNode to send
    # out identification on the channel with
    # a set interval by configuring the
    # following two parameters. The trans-
    # ceiver will only ID if the set
    # interval has elapsed since it's last
    # actual transmission. The interval is
    # configured in seconds.
    # This option is commented out and not
    # used by default.
    # id_callsign = MYCALL-0
    # id_interval = 600

    # For certain homebrew RNode interfaces
    # with low amounts of RAM, using packet
    # flow control can be useful. By default
    # it is disabled.
    flow_control = False
    
    
  # An example KISS modem interface. Useful for running
  # Reticulum over packet radio hardware.

  [[Packet Radio KISS Interface]]
    type = KISSInterface

    # Enable interface if you want use it!
    interface_enabled = False

    # Allow transmit on interface.
    outgoing = true

    # Serial port for the device
    port = /dev/ttyUSB1

    # Set the serial baud-rate and other
    # configuration parameters.
    speed = 115200    
    databits = 8
    parity = none
    stopbits = 1

    # Set the modem preamble. A 150ms
    # preamble should be a reasonable
    # default, but may need to be
    # increased for radios with slow-
    # opening squelch and long TX/RX
    # turnaround
    preamble = 150

    # Set the modem TX tail. In most
    # cases this should be kept as low
    # as possible to not waste airtime.
    txtail = 10

    # Configure CDMA parameters. These
    # settings are reasonable defaults.
    persistence = 200
    slottime = 20

    # You can configure the interface to send
    # out identification on the channel with
    # a set interval by configuring the
    # following two parameters. The KISS
    # interface will only ID if the set
    # interval has elapsed since it's last
    # actual transmission. The interval is
    # configured in seconds.
    # This option is commented out and not
    # used by default.
    # id_callsign = MYCALL-0
    # id_interval = 600

    # Whether to use KISS flow-control.
    # This is useful for modems that have
    # a small internal packet buffer, but
    # support packet flow control instead.
    flow_control = false


  # If you're using Reticulum on amateur radio spectrum,
  # you might want to use the AX.25 KISS interface. This
  # way, Reticulum will automatically encapsulate it's
  # traffic in AX.25 and also identify your stations
  # transmissions with your callsign and SSID.
  # 
  # Only do this if you really need to! Reticulum doesn't
  # need the AX.25 layer for anything, and it incurs extra
  # overhead on every packet to encapsulate in AX.25.
  #
  # A more efficient way is to use the plain KISS interface
  # with the beaconing functionality described above.

  [[Packet Radio AX.25 KISS Interface]]
    type = AX25KISSInterface

    # Set the station callsign and SSID
    callsign = NO1CLL
    ssid = 0

    # Enable interface if you want use it!
    interface_enabled = False

    # Allow transmit on interface.
    outgoing = true

    # Serial port for the device
    port = /dev/ttyUSB2

    # Set the serial baud-rate and other
    # configuration parameters.
    speed = 115200    
    databits = 8
    parity = none
    stopbits = 1

    # Whether to use KISS flow-control.
    # This is useful for modems with a
    # small internal packet buffer.
    flow_control = false

    # Set the modem preamble. A 150ms
    # preamble should be a reasonable
    # default, but may need to be
    # increased for radios with slow-
    # opening squelch and long TX/RX
    # turnaround
    preamble = 150

    # Set the modem TX tail. In most
    # cases this should be kept as low
    # as possible to not waste airtime.
    txtail = 10

    # Configure CDMA parameters. These
    # settings are reasonable defaults.
    persistence = 200
    slottime = 20

'''.splitlines()