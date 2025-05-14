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

from .vendor.platformutils import get_platform

if get_platform() == "android":
    from .Interfaces import Interface
    from .Interfaces import LocalInterface
    from .Interfaces import AutoInterface
    from .Interfaces import BackboneInterface
    from .Interfaces import TCPInterface
    from .Interfaces import UDPInterface
    from .Interfaces import I2PInterface
    from .Interfaces import RNodeMultiInterface
    from .Interfaces.Android import RNodeInterface
    from .Interfaces.Android import SerialInterface
    from .Interfaces.Android import KISSInterface
else:
    from RNS.Interfaces import *

from RNS.vendor.configobj import ConfigObj
import configparser
import multiprocessing.connection
import importlib.util
import threading
import signal
import atexit
import struct
import array
import time
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

    # Future minimum will probably be locked in at 251 bytes to support
    # networks with segments of different MTUs. Absolute minimum is 219.
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

    LINK_MTU_DISCOVERY   = True
    """
    Whether automatic link MTU discovery is enabled by default in this
    release. Link MTU discovery significantly increases throughput over
    fast links, but requires all intermediary hops to also support it.
    Support for this feature was added in RNS version 0.9.0. This option
    will become enabled by default in the near future. Please update your
    RNS instances.
    """

    MAX_QUEUED_ANNOUNCES = 16384
    QUEUED_ANNOUNCE_LIFE = 60*60*24

    ANNOUNCE_CAP = 2
    """
    The maximum percentage of interface bandwidth that, at any given time,
    may be used to propagate announces. If an announce was scheduled for
    broadcasting on an interface, but doing so would exceed the allowed
    bandwidth allocation, the announce will be queued for transmission
    when there is bandwidth available.

    Reticulum will always prioritise propagating announces with fewer
    hops, ensuring that distant, large networks with many peers on fast
    links don't overwhelm the capacity of smaller networks on slower
    mediums. If an announce remains queued for an extended amount of time,
    it will eventually be dropped.

    This value will be applied by default to all created interfaces,
    but it can be configured individually on a per-interface basis. In
    general, the global default setting should not be changed, and any
    alterations should be made on a per-interface basis instead.
    """

    MINIMUM_BITRATE = 5
    """
    Minimum bitrate required across a medium for Reticulum to be able
    to successfully establish links. Currently 5 bits per second.
    """

    # TODO: Let Reticulum somehow continously build a map of per-hop
    # latencies and use this map for global timeout calculation.
    DEFAULT_PER_HOP_TIMEOUT = 6

    # Length of truncated hashes in bits.
    TRUNCATED_HASHLENGTH = 128

    HEADER_MINSIZE   = 2+1+(TRUNCATED_HASHLENGTH//8)*1
    HEADER_MAXSIZE   = 2+1+(TRUNCATED_HASHLENGTH//8)*2
    IFAC_MIN_SIZE    = 1
    IFAC_SALT        = bytes.fromhex("adf54d882c9a9b80771eb4995d702d4a3e733391b2a0f53f416d9f907e55cff8")
    
    MDU              = MTU - HEADER_MAXSIZE - IFAC_MIN_SIZE

    RESOURCE_CACHE   = 24*60*60
    JOB_INTERVAL     = 5*60
    CLEAN_INTERVAL   = 15*60
    PERSIST_INTERVAL = 60*60*12
    GRACIOUS_PERSIST_INTERVAL = 60*5

    router           = None
    config           = None
    
    # The default configuration path will be expanded to a directory
    # named ".reticulum" inside the current users home directory
    userdir          = os.path.expanduser("~")
    configdir        = None
    configpath       = ""
    storagepath      = ""
    cachepath        = ""
    interfacepath    = ""

    __instance       = None

    __interface_detach_ran = False
    __exit_handler_ran = False
    @staticmethod
    def exit_handler():
        # This exit handler is called whenever Reticulum is asked to
        # shut down, and will in turn call exit handlers in other
        # classes, saving necessary information to disk and carrying
        # out cleanup operations.
        if not Reticulum.__exit_handler_ran:
            Reticulum.__exit_handler_ran = True
            if not Reticulum.__interface_detach_ran:
                RNS.Transport.detach_interfaces()
            RNS.Transport.exit_handler()
            RNS.Identity.exit_handler()

            if RNS.Profiler.ran():
                RNS.Profiler.results()

            RNS.loglevel = -1

    @staticmethod
    def sigint_handler(signal, frame):
        RNS.Transport.detach_interfaces()
        Reticulum.__interface_detach_ran = True
        RNS.exit()

    @staticmethod
    def sigterm_handler(signal, frame):
        RNS.Transport.detach_interfaces()
        Reticulum.__interface_detach_ran = True
        RNS.exit()

    @staticmethod
    def get_instance():
        """
        Return the currently running Reticulum instance
        """
        return Reticulum.__instance

    def __init__(self,configdir=None, loglevel=None, logdest=None, verbosity=None,
                 require_shared_instance=False, shared_instance_type=None):
        """
        Initialises and starts a Reticulum instance. This must be
        done before any other operations, and Reticulum will not
        pass any traffic before being instantiated.

        :param configdir: Full path to a Reticulum configuration directory.
        """

        if Reticulum.__instance != None:
            raise OSError("Attempt to reinitialise Reticulum, when it was already running")
        else:
            Reticulum.__instance = self

        RNS.vendor.platformutils.platform_checks()

        if configdir != None:
            Reticulum.configdir = configdir
        else:
            if os.path.isdir("/etc/reticulum") and os.path.isfile("/etc/reticulum/config"):
                Reticulum.configdir = "/etc/reticulum"
            elif os.path.isdir(Reticulum.userdir+"/.config/reticulum") and os.path.isfile(Reticulum.userdir+"/.config/reticulum/config"):
                Reticulum.configdir = Reticulum.userdir+"/.config/reticulum"
            else:
                Reticulum.configdir = Reticulum.userdir+"/.reticulum"

        if logdest == RNS.LOG_FILE:
            RNS.logdest = RNS.LOG_FILE
            RNS.logfile = Reticulum.configdir+"/logfile"
        elif callable(logdest):
            RNS.logdest = RNS.LOG_CALLBACK
            RNS.logcall = logdest
        
        Reticulum.configpath    = Reticulum.configdir+"/config"
        Reticulum.storagepath   = Reticulum.configdir+"/storage"
        Reticulum.cachepath     = Reticulum.configdir+"/storage/cache"
        Reticulum.resourcepath  = Reticulum.configdir+"/storage/resources"
        Reticulum.identitypath  = Reticulum.configdir+"/storage/identities"
        Reticulum.interfacepath = Reticulum.configdir+"/interfaces"

        Reticulum.__transport_enabled = False
        Reticulum.__link_mtu_discovery = Reticulum.LINK_MTU_DISCOVERY
        Reticulum.__remote_management_enabled = False
        Reticulum.__use_implicit_proof = True
        Reticulum.__allow_probes = False

        Reticulum.panic_on_interface_error = False

        self.local_interface_port = 37428
        self.local_control_port   = 37429
        self.local_socket_path    = None
        self.share_instance       = True
        self.shared_instance_type = shared_instance_type
        self.rpc_listener         = None
        self.rpc_key              = None
        self.rpc_type             = "AF_INET"
        self.use_af_unix          = False

        self.ifac_salt = Reticulum.IFAC_SALT

        self.requested_loglevel = loglevel
        self.requested_verbosity = verbosity
        if self.requested_loglevel != None:
            if self.requested_loglevel > RNS.LOG_EXTREME:
                self.requested_loglevel = RNS.LOG_EXTREME
            if self.requested_loglevel < RNS.LOG_CRITICAL:
                self.requested_loglevel = RNS.LOG_CRITICAL

            RNS.loglevel = self.requested_loglevel

        self.is_shared_instance = False
        self.shared_instance_interface = None
        self.require_shared = require_shared_instance
        self.is_connected_to_shared_instance = False
        self.is_standalone_instance = False
        self.jobs_thread = None
        self.last_data_persist = time.time()
        self.last_cache_clean = 0

        if not os.path.isdir(Reticulum.storagepath):
            os.makedirs(Reticulum.storagepath)

        if not os.path.isdir(Reticulum.cachepath):
            os.makedirs(Reticulum.cachepath)

        if not os.path.isdir(os.path.join(Reticulum.cachepath, "announces")):
            os.makedirs(os.path.join(Reticulum.cachepath, "announces"))

        if not os.path.isdir(Reticulum.resourcepath):
            os.makedirs(Reticulum.resourcepath)

        if not os.path.isdir(Reticulum.identitypath):
            os.makedirs(Reticulum.identitypath)

        if not os.path.isdir(Reticulum.interfacepath):
            os.makedirs(Reticulum.interfacepath)

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
            time.sleep(1.5)

        self.__apply_config()
        RNS.log(f"Utilising cryptography backend \"{RNS.Cryptography.Provider.backend()}\"", RNS.LOG_DEBUG)
        RNS.log(f"Configuration loaded from {self.configpath}", RNS.LOG_VERBOSE)

        RNS.Identity.load_known_destinations()
        RNS.Transport.start(self)

        if self.use_af_unix:
            self.rpc_addr = f"\0rns/{self.local_socket_path}/rpc"
            self.rpc_type = "AF_UNIX"
        else:
            self.rpc_addr = ("127.0.0.1", self.local_control_port)
            self.rpc_type = "AF_INET"

        if self.rpc_key == None:
            self.rpc_key  = RNS.Identity.full_hash(RNS.Transport.identity.get_private_key())
        
        if self.is_shared_instance:
            self.rpc_listener = multiprocessing.connection.Listener(self.rpc_addr, family=self.rpc_type, authkey=self.rpc_key)
            thread = threading.Thread(target=self.rpc_loop)
            thread.daemon = True
            thread.start()

        atexit.register(Reticulum.exit_handler)
        signal.signal(signal.SIGINT, Reticulum.sigint_handler)
        signal.signal(signal.SIGTERM, Reticulum.sigterm_handler)

    def __start_jobs(self):
        if self.jobs_thread == None:
            RNS.Identity._clean_ratchets()
            self.jobs_thread = threading.Thread(target=self.__jobs)
            self.jobs_thread.daemon = True
            self.jobs_thread.start()

    def __jobs(self):
        while True:
            now = time.time()

            if now > self.last_cache_clean+Reticulum.CLEAN_INTERVAL:
                self.__clean_caches()
                self.last_cache_clean = time.time()

            if now > self.last_data_persist+Reticulum.PERSIST_INTERVAL:
                self.__persist_data()
            
            time.sleep(Reticulum.JOB_INTERVAL)

    def __start_local_interface(self):
        if self.share_instance:
            try:
                interface = LocalInterface.LocalServerInterface(
                    RNS.Transport,
                    self.local_interface_port,
                    socket_path=self.local_socket_path
                )
                interface.OUT = True
                if hasattr(Reticulum, "_force_shared_instance_bitrate"):
                    interface.bitrate = Reticulum._force_shared_instance_bitrate
                    interface._force_bitrate = Reticulum._force_shared_instance_bitrate
                    RNS.log(f"Forcing shared instance bitrate of {RNS.prettyspeed(interface.bitrate)}", RNS.LOG_WARNING)
                    interface.optimise_mtu()
                
                if self.require_shared == True:
                    interface.detach()
                    self.is_shared_instance = True
                    RNS.log("Existing shared instance required, but this instance started as shared instance. Aborting startup.", RNS.LOG_VERBOSE)

                else:
                    RNS.Transport.interfaces.append(interface)
                    self.shared_instance_interface = interface
                    self.is_shared_instance = True
                    RNS.log("Started shared instance interface: "+str(interface), RNS.LOG_DEBUG)
                    self.__start_jobs()

            except Exception as e:
                try:
                    interface = LocalInterface.LocalClientInterface(
                        RNS.Transport,
                        "Local shared instance",
                        self.local_interface_port,
                        socket_path=self.local_socket_path)
                    interface.target_port = self.local_interface_port
                    interface.OUT = True
                    if hasattr(Reticulum, "_force_shared_instance_bitrate"):
                        interface.bitrate = Reticulum._force_shared_instance_bitrate
                        interface._force_bitrate = True
                        RNS.log(f"Forcing shared instance bitrate of {RNS.prettyspeed(interface.bitrate)}", RNS.LOG_WARNING)
                        interface.optimise_mtu()
                    RNS.Transport.interfaces.append(interface)
                    self.is_shared_instance = False
                    self.is_standalone_instance = False
                    self.is_connected_to_shared_instance = True
                    Reticulum.__transport_enabled = False
                    Reticulum.__remote_management_enabled = False
                    Reticulum.__allow_probes = False
                    RNS.log("Connected to locally available Reticulum instance via: "+str(interface), RNS.LOG_DEBUG)
                except Exception as e:
                    RNS.log("Local shared instance appears to be running, but it could not be connected", RNS.LOG_ERROR)
                    RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                    self.is_shared_instance = False
                    self.is_standalone_instance = True
                    self.is_connected_to_shared_instance = False

            if self.is_shared_instance and self.require_shared:
                raise SystemError("No shared instance available, but application that started Reticulum required it")

        else:
            self.is_shared_instance = False
            self.is_standalone_instance = True
            self.is_connected_to_shared_instance = False
            self.__start_jobs()

    def __apply_config(self):
        if "logging" in self.config:
            for option in self.config["logging"]:
                value = self.config["logging"][option]
                if option == "loglevel" and self.requested_loglevel == None:
                    RNS.loglevel = int(value)
                    if self.requested_verbosity != None:
                        RNS.loglevel += self.requested_verbosity
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
                if RNS.vendor.platformutils.use_af_unix():
                    if option == "instance_name":
                        value = self.config["reticulum"][option]
                        self.local_socket_path = value
                if option == "shared_instance_type":
                    if self.shared_instance_type == None:
                        value = self.config["reticulum"][option].lower()
                        if value in ["tcp", "unix"]:
                            self.shared_instance_type = value
                if option == "shared_instance_port":
                    value = int(self.config["reticulum"][option])
                    self.local_interface_port = value
                if option == "instance_control_port":
                    value = int(self.config["reticulum"][option])
                    self.local_control_port = value
                if option == "rpc_key":
                    try:
                        value = bytes.fromhex(self.config["reticulum"][option])
                        self.rpc_key = value
                    except Exception as e:
                        RNS.log("Invalid shared instance RPC key specified, falling back to default key", RNS.LOG_ERROR)
                        self.rpc_key = None
                if option == "enable_transport":
                    v = self.config["reticulum"].as_bool(option)
                    if v == True:
                        Reticulum.__transport_enabled = True
                if option == "link_mtu_discovery":
                    v = self.config["reticulum"].as_bool(option)
                    if v == True:
                        Reticulum.__link_mtu_discovery = True
                if option == "enable_remote_management":
                    v = self.config["reticulum"].as_bool(option)
                    if v == True:
                        Reticulum.__remote_management_enabled = True
                if option == "remote_management_allowed":
                    v = self.config["reticulum"].as_list(option)
                    for hexhash in v:
                        dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH//8)*2
                        if len(hexhash) != dest_len:
                            raise ValueError("Identity hash length for remote management ACL "+str(hexhash)+" is invalid, must be {hex} hexadecimal characters ({byte} bytes).".format(hex=dest_len, byte=dest_len//2))
                        try:
                            allowed_hash = bytes.fromhex(hexhash)
                        except Exception as e:
                            raise ValueError("Invalid identity hash for remote management ACL: "+str(hexhash))

                        if not allowed_hash in RNS.Transport.remote_management_allowed:
                            RNS.Transport.remote_management_allowed.append(allowed_hash)
                if option == "respond_to_probes":
                    v = self.config["reticulum"].as_bool(option)
                    if v == True:
                        Reticulum.__allow_probes = True
                if option == "force_shared_instance_bitrate":
                    v = self.config["reticulum"].as_int(option)
                    Reticulum._force_shared_instance_bitrate = v
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

        if RNS.compiled: RNS.log("Reticulum running in compiled mode", RNS.LOG_DEBUG)
        else: RNS.log("Reticulum running in interpreted mode", RNS.LOG_DEBUG)

        if RNS.vendor.platformutils.use_af_unix():
            if self.shared_instance_type == "tcp": self.use_af_unix = False
            else:                                  self.use_af_unix = True
        else:
            self.shared_instance_type = "tcp"
            self.use_af_unix          = False

        if self.local_socket_path == None and self.use_af_unix:
            self.local_socket_path = "default"

        self.__start_local_interface()

        if self.is_shared_instance or self.is_standalone_instance:
            RNS.log("Bringing up system interfaces...", RNS.LOG_VERBOSE)
            interface_names = []
            if "interfaces" in self.config:
                for name in self.config["interfaces"]:
                    if not name in interface_names:
                        c = self.config["interfaces"][name]
                        interface_mode = Interface.Interface.MODE_FULL
                        
                        if "interface_mode" in c:
                            c["interface_mode"] = str(c["interface_mode"]).lower()
                            if c["interface_mode"] == "full":
                                interface_mode = Interface.Interface.MODE_FULL
                            elif c["interface_mode"] == "access_point" or c["interface_mode"] == "accesspoint" or c["interface_mode"] == "ap":
                                interface_mode = Interface.Interface.MODE_ACCESS_POINT
                            elif c["interface_mode"] == "pointtopoint" or c["interface_mode"] == "ptp":
                                interface_mode = Interface.Interface.MODE_POINT_TO_POINT
                            elif c["interface_mode"] == "roaming":
                                interface_mode = Interface.Interface.MODE_ROAMING
                            elif c["interface_mode"] == "boundary":
                                interface_mode = Interface.Interface.MODE_BOUNDARY
                            elif c["mode"] == "gateway" or c["mode"] == "gw":
                                interface_mode = Interface.Interface.MODE_GATEWAY

                        elif "mode" in c:
                            c["mode"] = str(c["mode"]).lower()
                            if c["mode"] == "full":
                                interface_mode = Interface.Interface.MODE_FULL
                            elif c["mode"] == "access_point" or c["mode"] == "accesspoint" or c["mode"] == "ap":
                                interface_mode = Interface.Interface.MODE_ACCESS_POINT
                            elif c["mode"] == "pointtopoint" or c["mode"] == "ptp":
                                interface_mode = Interface.Interface.MODE_POINT_TO_POINT
                            elif c["mode"] == "roaming":
                                interface_mode = Interface.Interface.MODE_ROAMING
                            elif c["mode"] == "boundary":
                                interface_mode = Interface.Interface.MODE_BOUNDARY
                            elif c["mode"] == "gateway" or c["mode"] == "gw":
                                interface_mode = Interface.Interface.MODE_GATEWAY

                        ifac_size = None
                        if "ifac_size" in c:
                            if c.as_int("ifac_size") >= Reticulum.IFAC_MIN_SIZE*8:
                                ifac_size = c.as_int("ifac_size")//8
                                
                        ifac_netname = None
                        if "networkname" in c:
                            if c["networkname"] != "":
                                ifac_netname = c["networkname"]
                        if "network_name" in c:
                            if c["network_name"] != "":
                                ifac_netname = c["network_name"]

                        ifac_netkey = None
                        if "passphrase" in c:
                            if c["passphrase"] != "":
                                ifac_netkey = c["passphrase"]
                        if "pass_phrase" in c:
                            if c["pass_phrase"] != "":
                                ifac_netkey = c["pass_phrase"]
                                
                        ingress_control = True
                        if "ingress_control" in c: ingress_control = c.as_bool("ingress_control")
                        ic_max_held_announces = None
                        if "ic_max_held_announces" in c: ic_max_held_announces = c.as_int("ic_max_held_announces")
                        ic_burst_hold = None
                        if "ic_burst_hold" in c: ic_burst_hold = c.as_float("ic_burst_hold")
                        ic_burst_freq_new = None
                        if "ic_burst_freq_new" in c: ic_burst_freq_new = c.as_float("ic_burst_freq_new")
                        ic_burst_freq = None
                        if "ic_burst_freq" in c: ic_burst_freq = c.as_float("ic_burst_freq")
                        ic_new_time = None
                        if "ic_new_time" in c: ic_new_time = c.as_float("ic_new_time")
                        ic_burst_penalty = None
                        if "ic_burst_penalty" in c: ic_burst_penalty = c.as_float("ic_burst_penalty")
                        ic_held_release_interval = None
                        if "ic_held_release_interval" in c: ic_held_release_interval = c.as_float("ic_held_release_interval")

                        configured_bitrate = None
                        if "bitrate" in c:
                            if c.as_int("bitrate") >= Reticulum.MINIMUM_BITRATE:
                                configured_bitrate = c.as_int("bitrate")

                        announce_rate_target = None
                        if "announce_rate_target" in c:
                            if c.as_int("announce_rate_target") > 0:
                                announce_rate_target = c.as_int("announce_rate_target")
                                
                        announce_rate_grace = None
                        if "announce_rate_grace" in c:
                            if c.as_int("announce_rate_grace") >= 0:
                                announce_rate_grace = c.as_int("announce_rate_grace")
                                
                        announce_rate_penalty = None
                        if "announce_rate_penalty" in c:
                            if c.as_int("announce_rate_penalty") >= 0:
                                announce_rate_penalty = c.as_int("announce_rate_penalty")

                        if announce_rate_target != None and announce_rate_grace == None:
                            announce_rate_grace = 0

                        if announce_rate_target != None and announce_rate_penalty == None:
                            announce_rate_penalty = 0

                        announce_cap = Reticulum.ANNOUNCE_CAP/100.0
                        if "announce_cap" in c:
                            if c.as_float("announce_cap") > 0 and c.as_float("announce_cap") <= 100:
                                announce_cap = c.as_float("announce_cap")/100.0
                                
                        try:
                            def interface_post_init(interface):
                                if interface != None:
                                    if "outgoing" in c and c.as_bool("outgoing") == False:
                                        interface.OUT = False
                                    else:
                                        interface.OUT = True

                                    interface.mode = interface_mode
                                    interface.announce_cap = announce_cap
                                    if configured_bitrate:
                                        interface.bitrate = configured_bitrate
                                    interface.optimise_mtu()
                                    if ifac_size != None:
                                        interface.ifac_size = ifac_size
                                    else:
                                        interface.ifac_size = interface.DEFAULT_IFAC_SIZE

                                    interface.announce_rate_target = announce_rate_target
                                    interface.announce_rate_grace = announce_rate_grace
                                    interface.announce_rate_penalty = announce_rate_penalty
                                    interface.ingress_control = ingress_control
                                    if ic_max_held_announces != None: interface.ic_max_held_announces = ic_max_held_announces
                                    if ic_burst_hold != None: interface.ic_burst_hold = ic_burst_hold
                                    if ic_burst_freq_new != None: interface.ic_burst_freq_new = ic_burst_freq_new
                                    if ic_burst_freq != None: interface.ic_burst_freq = ic_burst_freq
                                    if ic_new_time != None: interface.ic_new_time = ic_new_time
                                    if ic_burst_penalty != None: interface.ic_burst_penalty = ic_burst_penalty
                                    if ic_held_release_interval != None: interface.ic_held_release_interval = ic_held_release_interval

                                    interface.ifac_netname = ifac_netname
                                    interface.ifac_netkey = ifac_netkey

                                    if interface.ifac_netname != None or interface.ifac_netkey != None:
                                        ifac_origin = b""

                                        if interface.ifac_netname != None:
                                            ifac_origin += RNS.Identity.full_hash(interface.ifac_netname.encode("utf-8"))

                                        if interface.ifac_netkey != None:
                                            ifac_origin += RNS.Identity.full_hash(interface.ifac_netkey.encode("utf-8"))

                                        ifac_origin_hash = RNS.Identity.full_hash(ifac_origin)
                                        interface.ifac_key = RNS.Cryptography.hkdf(
                                            length=64,
                                            derive_from=ifac_origin_hash,
                                            salt=self.ifac_salt,
                                            context=None
                                        )

                                        interface.ifac_identity = RNS.Identity.from_bytes(interface.ifac_key)
                                        interface.ifac_signature = interface.ifac_identity.sign(RNS.Identity.full_hash(interface.ifac_key))

                                    RNS.Transport.interfaces.append(interface)
                                    interface.final_init()

                            interface = None
                            if (("interface_enabled" in c) and c.as_bool("interface_enabled") == True) or (("enabled" in c) and c.as_bool("enabled") == True):
                                interface_config = c
                                interface_config["name"] = name
                                interface_config["selected_interface_mode"] = interface_mode
                                interface_config["configured_bitrate"] = configured_bitrate

                                if c["type"] == "AutoInterface":
                                    interface = AutoInterface.AutoInterface(RNS.Transport, interface_config)
                                    interface_post_init(interface)

                                if c["type"] == "BackboneInterface" or c["type"] == "BackboneClientInterface":
                                    if "port" in c: c["listen_port"] = c["port"]
                                    if "port" in c: c["target_port"] = c["port"]
                                    if "remote" in c: c["target_host"] = c["remote"]
                                    if "listen_on" in c: c["listen_ip"] = c["listen_on"]

                                if c["type"] == "BackboneInterface":
                                    if "target_host" in c: interface = BackboneInterface.BackboneClientInterface(RNS.Transport, interface_config)
                                    else: interface = BackboneInterface.BackboneInterface(RNS.Transport, interface_config)
                                    interface_post_init(interface)

                                if c["type"] == "BackboneClientInterface":
                                    interface = BackboneInterface.BackboneClientInterface(RNS.Transport, interface_config)
                                    interface_post_init(interface)

                                if c["type"] == "UDPInterface":
                                    interface = UDPInterface.UDPInterface(RNS.Transport, interface_config)
                                    interface_post_init(interface)

                                if c["type"] == "TCPServerInterface":
                                    interface = TCPInterface.TCPServerInterface(RNS.Transport, interface_config)
                                    interface_post_init(interface)

                                if c["type"] == "TCPClientInterface":
                                    interface = TCPInterface.TCPClientInterface(RNS.Transport, interface_config)
                                    interface_post_init(interface)

                                if c["type"] == "I2PInterface":
                                    interface_config["storagepath"] = Reticulum.storagepath
                                    interface_config["ifac_netname"] = ifac_netname
                                    interface_config["ifac_netkey"] = ifac_netkey
                                    interface_config["ifac_size"] = ifac_size

                                    interface = I2PInterface.I2PInterface(RNS.Transport, interface_config)
                                    interface_post_init(interface)

                                if c["type"] == "SerialInterface":
                                    interface = SerialInterface.SerialInterface(RNS.Transport, interface_config)
                                    interface_post_init(interface)

                                if c["type"] == "PipeInterface":
                                    interface = PipeInterface.PipeInterface(RNS.Transport, interface_config)
                                    interface_post_init(interface)

                                if c["type"] == "KISSInterface":
                                    interface = KISSInterface.KISSInterface(RNS.Transport, interface_config)
                                    interface_post_init(interface)

                                if c["type"] == "AX25KISSInterface":
                                    interface = AX25KISSInterface.AX25KISSInterface(RNS.Transport, interface_config)
                                    interface_post_init(interface)

                                if c["type"] == "RNodeInterface":
                                    interface = RNodeInterface.RNodeInterface(RNS.Transport, interface_config)
                                    interface_post_init(interface)

                                if c["type"] == "RNodeMultiInterface":
                                    interface = RNodeMultiInterface.RNodeMultiInterface(RNS.Transport, interface_config)
                                    interface_post_init(interface)
                                    interface.start()

                                if interface == None:
                                    # Interface was not handled by any internal interface types,
                                    # attempt to load and initialise it from user-supplied modules
                                    interface_type = c["type"]
                                    interface_file = f"{interface_type}.py"
                                    interface_path = os.path.join(self.interfacepath, interface_file)
                                    if not os.path.isfile(interface_path):
                                        RNS.log(f"Could not locate external interface module \"{interface_file}\" in \"{self.interfacepath}\"", RNS.LOG_ERROR)
                                    
                                    else:
                                        try:
                                            RNS.log(f"Loading external interface \"{interface_file}\" from \"{self.interfacepath}\"", RNS.LOG_NOTICE)
                                            interface_globals = {}
                                            interface_globals["Interface"] = Interface.Interface
                                            interface_globals["RNS"] = RNS
                                            with open(interface_path) as class_file:
                                                interface_code = class_file.read()
                                                exec(interface_code, interface_globals)
                                                interface_class = interface_globals["interface_class"]
                                                
                                                if interface_class != None:
                                                    interface = interface_class(RNS.Transport, interface_config)
                                                    interface_post_init(interface)

                                        except Exception as e:
                                            RNS.log(f"External interface initialisation failed for {interface_type} / {name}", RNS.LOG_ERROR)
                                            RNS.trace_exception(e)

                            else:
                                RNS.log("Skipping disabled interface \""+name+"\"", RNS.LOG_DEBUG)

                        except Exception as e:
                            RNS.log("The interface \""+name+"\" could not be created. Check your configuration file for errors!", RNS.LOG_ERROR)
                            RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                            RNS.panic()
                    else:
                        RNS.log("The interface name \""+name+"\" was already used. Check your configuration file for errors!", RNS.LOG_ERROR)
                        RNS.panic()

            RNS.log("System interfaces are ready", RNS.LOG_VERBOSE)

    def _add_interface(self, interface, mode = None, configured_bitrate=None, ifac_size=None, ifac_netname=None, ifac_netkey=None, announce_cap=None, announce_rate_target=None, announce_rate_grace=None, announce_rate_penalty=None):
        if not self.is_connected_to_shared_instance:
            if interface != None and issubclass(type(interface), RNS.Interfaces.Interface.Interface):
                
                if mode == None:
                    mode = Interface.Interface.MODE_FULL
                interface.mode = mode

                if configured_bitrate:
                    interface.bitrate = configured_bitrate
                interface.optimise_mtu()

                if ifac_size != None:
                    interface.ifac_size = ifac_size
                else:
                    interface.ifac_size = 8

                interface.announce_cap = announce_cap if announce_cap != None else Reticulum.ANNOUNCE_CAP/100.0
                interface.announce_rate_target = announce_rate_target
                interface.announce_rate_grace = announce_rate_grace
                interface.announce_rate_penalty = announce_rate_penalty

                interface.ifac_netname = ifac_netname
                interface.ifac_netkey = ifac_netkey

                if interface.ifac_netname != None or interface.ifac_netkey != None:
                    ifac_origin = b""

                    if interface.ifac_netname != None:
                        ifac_origin += RNS.Identity.full_hash(interface.ifac_netname.encode("utf-8"))

                    if interface.ifac_netkey != None:
                        ifac_origin += RNS.Identity.full_hash(interface.ifac_netkey.encode("utf-8"))

                    ifac_origin_hash = RNS.Identity.full_hash(ifac_origin)
                    interface.ifac_key = RNS.Cryptography.hkdf(
                        length=64,
                        derive_from=ifac_origin_hash,
                        salt=self.ifac_salt,
                        context=None
                    )

                    interface.ifac_identity = RNS.Identity.from_bytes(interface.ifac_key)
                    interface.ifac_signature = interface.ifac_identity.sign(RNS.Identity.full_hash(interface.ifac_key))

                RNS.Transport.interfaces.append(interface)
                interface.final_init()

    def _should_persist_data(self):
        if time.time() > self.last_data_persist+Reticulum.GRACIOUS_PERSIST_INTERVAL:
            self.__persist_data()

    def __persist_data(self):
        RNS.Transport.persist_data()
        RNS.Identity.persist_data()
        self.last_data_persist = time.time()

    def __clean_caches(self):
        RNS.log("Cleaning resource and packet caches...", RNS.LOG_EXTREME)
        now = time.time()

        # Clean resource caches
        for filename in os.listdir(self.resourcepath):
            try:
                if len(filename) == (RNS.Identity.HASHLENGTH//8)*2:
                    filepath = self.resourcepath + "/" + filename
                    mtime = os.path.getmtime(filepath)
                    age = now - mtime
                    if age > Reticulum.RESOURCE_CACHE:
                        os.unlink(filepath)

            except Exception as e:
                RNS.log("Error while cleaning resources cache, the contained exception was: "+str(e), RNS.LOG_ERROR)

        # Clean packet caches
        for filename in os.listdir(self.cachepath):
            try:
                if len(filename) == (RNS.Identity.HASHLENGTH//8)*2:
                    filepath = self.cachepath + "/" + filename
                    mtime = os.path.getmtime(filepath)
                    age = now - mtime
                    if age > RNS.Transport.DESTINATION_TIMEOUT:
                        os.unlink(filepath)
            
            except Exception as e:
                RNS.log("Error while cleaning resources cache, the contained exception was: "+str(e), RNS.LOG_ERROR)

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

                    if path == "path_table":
                        mh = call["max_hops"]
                        rpc_connection.send(self.get_path_table(max_hops=mh))

                    if path == "rate_table":
                        rpc_connection.send(self.get_rate_table())

                    if path == "next_hop_if_name":
                        rpc_connection.send(self.get_next_hop_if_name(call["destination_hash"]))

                    if path == "next_hop":
                        rpc_connection.send(self.get_next_hop(call["destination_hash"]))

                    if path == "first_hop_timeout":
                        rpc_connection.send(self.get_first_hop_timeout(call["destination_hash"]))

                    if path == "link_count":
                        rpc_connection.send(self.get_link_count())

                    if path == "packet_rssi":
                        rpc_connection.send(self.get_packet_rssi(call["packet_hash"]))

                    if path == "packet_snr":
                        rpc_connection.send(self.get_packet_snr(call["packet_hash"]))

                    if path == "packet_q":
                        rpc_connection.send(self.get_packet_q(call["packet_hash"]))

                if "drop" in call:
                    path = call["drop"]

                    if path == "path":
                        rpc_connection.send(self.drop_path(call["destination_hash"]))

                    if path == "all_via":
                        rpc_connection.send(self.drop_all_via(call["destination_hash"]))

                    if path == "announce_queues":
                        rpc_connection.send(self.drop_announce_queues())

                rpc_connection.close()

            except Exception as e:
                RNS.log("An error ocurred while handling RPC call from local client: "+str(e), RNS.LOG_ERROR)

    def get_rpc_client(self): return multiprocessing.connection.Client(self.rpc_addr, family=self.rpc_type, authkey=self.rpc_key)

    def get_interface_stats(self):
        if self.is_connected_to_shared_instance:
            rpc_connection = self.get_rpc_client()
            rpc_connection.send({"get": "interface_stats"})
            response = rpc_connection.recv()
            return response
        else:
            interfaces = []
            for interface in RNS.Transport.interfaces:
                ifstats = {}
                
                if hasattr(interface, "clients"):
                    ifstats["clients"] = interface.clients
                else:
                    ifstats["clients"] = None

                if hasattr(interface, "parent_interface") and interface.parent_interface != None:
                    ifstats["parent_interface_name"] = str(interface.parent_interface)
                    ifstats["parent_interface_hash"] = interface.parent_interface.get_hash()

                if hasattr(interface, "i2p") and hasattr(interface, "connectable"):
                    if interface.connectable:
                        ifstats["i2p_connectable"] = True
                    else:
                        ifstats["i2p_connectable"] = False

                if hasattr(interface, "b32"):
                    if interface.b32 != None:
                        ifstats["i2p_b32"] = interface.b32+".b32.i2p"
                    else:
                        ifstats["i2p_b32"] = None

                if hasattr(interface, "i2p_tunnel_state"):
                    if interface.i2p_tunnel_state != None:
                        state_description = "Unknown State"
                        if interface.i2p_tunnel_state == I2PInterface.I2PInterfacePeer.TUNNEL_STATE_ACTIVE:
                            state_description = "Tunnel Active"
                        elif interface.i2p_tunnel_state == I2PInterface.I2PInterfacePeer.TUNNEL_STATE_INIT:
                            state_description = "Creating Tunnel"
                        elif interface.i2p_tunnel_state == I2PInterface.I2PInterfacePeer.TUNNEL_STATE_STALE:
                            state_description = "Tunnel Unresponsive"
                        ifstats["tunnelstate"] = state_description
                    else:
                        ifstats["tunnelstate"] = None

                if hasattr(interface, "r_airtime_short"):
                    ifstats["airtime_short"] = interface.r_airtime_short

                if hasattr(interface, "r_airtime_long"):
                    ifstats["airtime_long"] = interface.r_airtime_long

                if hasattr(interface, "r_channel_load_short"):
                    ifstats["channel_load_short"] = interface.r_channel_load_short

                if hasattr(interface, "r_channel_load_long"):
                    ifstats["channel_load_long"] = interface.r_channel_load_long

                if hasattr(interface, "r_noise_floor"):
                    ifstats["noise_floor"] = interface.r_noise_floor

                if hasattr(interface, "r_battery_state"):
                    if interface.r_battery_state != 0x00:
                        ifstats["battery_state"] = interface.get_battery_state_string()

                    if hasattr(interface, "r_battery_percent"):
                        ifstats["battery_percent"] = interface.r_battery_percent

                if hasattr(interface, "bitrate"):
                    if interface.bitrate != None:
                        ifstats["bitrate"] = interface.bitrate
                    else:
                        ifstats["bitrate"] = None

                if hasattr(interface, "current_rx_speed"):
                    if interface.current_rx_speed != None:
                        ifstats["rxs"] = interface.current_rx_speed
                    else:
                        ifstats["rxs"] = 0
                else:
                    ifstats["rxs"] = 0

                if hasattr(interface, "current_tx_speed"):
                    if interface.current_tx_speed != None:
                        ifstats["txs"] = interface.current_tx_speed
                    else:
                        ifstats["txs"] = 0
                else:
                    ifstats["txs"] = 0

                if hasattr(interface, "peers"):
                    if interface.peers != None:
                        ifstats["peers"] = len(interface.peers)
                    else:
                        ifstats["peers"] = None

                if hasattr(interface, "ifac_signature"):
                    ifstats["ifac_signature"] = interface.ifac_signature
                    ifstats["ifac_size"] = interface.ifac_size
                    ifstats["ifac_netname"] = interface.ifac_netname
                else:
                    ifstats["ifac_signature"] = None
                    ifstats["ifac_size"] = None
                    ifstats["ifac_netname"] = None

                if hasattr(interface, "announce_queue"):
                    if interface.announce_queue != None:
                        ifstats["announce_queue"] = len(interface.announce_queue)
                    else:
                        ifstats["announce_queue"] = None

                ifstats["name"] = str(interface)
                ifstats["short_name"] = str(interface.name)
                ifstats["hash"] = interface.get_hash()
                ifstats["type"] = str(type(interface).__name__)
                ifstats["rxb"] = interface.rxb
                ifstats["txb"] = interface.txb
                ifstats["incoming_announce_frequency"] = interface.incoming_announce_frequency()
                ifstats["outgoing_announce_frequency"] = interface.outgoing_announce_frequency()
                ifstats["held_announces"] = len(interface.held_announces)
                ifstats["status"] = interface.online
                ifstats["mode"] = interface.mode

                interfaces.append(ifstats)

            stats = {}
            stats["interfaces"] = interfaces
            stats["rxb"] = RNS.Transport.traffic_rxb
            stats["txb"] = RNS.Transport.traffic_txb
            stats["rxs"] = RNS.Transport.speed_rx
            stats["txs"] = RNS.Transport.speed_tx
            if Reticulum.transport_enabled():
                stats["transport_id"] = RNS.Transport.identity.hash
                stats["transport_uptime"] = time.time()-RNS.Transport.start_time
                if Reticulum.probe_destination_enabled():
                    stats["probe_responder"] = RNS.Transport.probe_destination.hash
                else:
                    stats["probe_responder"] = None

            if importlib.util.find_spec('psutil') != None:
                import psutil
                process = psutil.Process()
                stats["rss"] = process.memory_info().rss
            else:
                stats["rss"] = None

            return stats

    def get_path_table(self, max_hops=None):
        if self.is_connected_to_shared_instance:
            rpc_connection = self.get_rpc_client()
            rpc_connection.send({"get": "path_table", "max_hops": max_hops})
            response = rpc_connection.recv()
            return response

        else:
            path_table = []
            for dst_hash in RNS.Transport.path_table:
                path_hops = RNS.Transport.path_table[dst_hash][2]
                if max_hops == None or path_hops <= max_hops:
                    entry = {
                        "hash": dst_hash,
                        "timestamp": RNS.Transport.path_table[dst_hash][0],
                        "via": RNS.Transport.path_table[dst_hash][1],
                        "hops": path_hops,
                        "expires": RNS.Transport.path_table[dst_hash][3],
                        "interface": str(RNS.Transport.path_table[dst_hash][5]),
                    }
                    path_table.append(entry)

            return path_table

    def get_rate_table(self):
        if self.is_connected_to_shared_instance:
            rpc_connection = self.get_rpc_client()
            rpc_connection.send({"get": "rate_table"})
            response = rpc_connection.recv()
            return response

        else:
            rate_table = []
            for dst_hash in RNS.Transport.announce_rate_table:
                entry = {
                    "hash": dst_hash,
                    "last": RNS.Transport.announce_rate_table[dst_hash]["last"],
                    "rate_violations": RNS.Transport.announce_rate_table[dst_hash]["rate_violations"],
                    "blocked_until": RNS.Transport.announce_rate_table[dst_hash]["blocked_until"],
                    "timestamps": RNS.Transport.announce_rate_table[dst_hash]["timestamps"],
                }
                rate_table.append(entry)

            return rate_table

    def drop_path(self, destination):
        if self.is_connected_to_shared_instance:
            rpc_connection = self.get_rpc_client()
            rpc_connection.send({"drop": "path", "destination_hash": destination})
            response = rpc_connection.recv()
            return response

        else:
            return RNS.Transport.expire_path(destination)

    def drop_all_via(self, transport_hash):
        if self.is_connected_to_shared_instance:
            rpc_connection = self.get_rpc_client()
            rpc_connection.send({"drop": "all_via", "destination_hash": transport_hash})
            response = rpc_connection.recv()
            return response

        else:
            dropped_count = 0
            for destination_hash in RNS.Transport.path_table:
                if RNS.Transport.path_table[destination_hash][1] == transport_hash:
                    RNS.Transport.expire_path(destination_hash)
                    dropped_count += 1

            return dropped_count

    def drop_announce_queues(self):
        if self.is_connected_to_shared_instance:
            rpc_connection = self.get_rpc_client()
            rpc_connection.send({"drop": "announce_queues"})
            response = rpc_connection.recv()
            return response

        else:
            return RNS.Transport.drop_announce_queues()

    def get_next_hop_if_name(self, destination):
        if self.is_connected_to_shared_instance:
            rpc_connection = self.get_rpc_client()
            rpc_connection.send({"get": "next_hop_if_name", "destination_hash": destination})
            response = rpc_connection.recv()
            return response

        else:
            return str(RNS.Transport.next_hop_interface(destination))

    def get_first_hop_timeout(self, destination):
        if self.is_connected_to_shared_instance:
            try:
                rpc_connection = self.get_rpc_client()
                rpc_connection.send({"get": "first_hop_timeout", "destination_hash": destination})
                response = rpc_connection.recv()

                if self.is_connected_to_shared_instance and hasattr(self, "_force_shared_instance_bitrate") and self._force_shared_instance_bitrate:
                    simulated_latency = ((1/self._force_shared_instance_bitrate)*8)*RNS.Reticulum.MTU
                    RNS.log("Adding simulated latency of "+RNS.prettytime(simulated_latency)+" to first hop timeout", RNS.LOG_DEBUG)
                    response += simulated_latency

                return response
            except Exception as e:
                RNS.log("An error occurred while getting first hop timeout from shared instance: "+str(e), RNS.LOG_ERROR)
                return RNS.Reticulum.DEFAULT_PER_HOP_TIMEOUT

        else:
            return RNS.Transport.first_hop_timeout(destination)

    def get_next_hop(self, destination):
        if self.is_connected_to_shared_instance:
            rpc_connection = self.get_rpc_client()
            rpc_connection.send({"get": "next_hop", "destination_hash": destination})
            response = rpc_connection.recv()

            return response

        else:
            return RNS.Transport.next_hop(destination)

    def get_link_count(self):
        if self.is_connected_to_shared_instance:
            rpc_connection = self.get_rpc_client()
            rpc_connection.send({"get": "link_count"})
            response = rpc_connection.recv()
            return response

        else:
            return len(RNS.Transport.link_table)

    def get_packet_rssi(self, packet_hash):
        if self.is_connected_to_shared_instance:
            rpc_connection = self.get_rpc_client()
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
            rpc_connection = self.get_rpc_client()
            rpc_connection.send({"get": "packet_snr", "packet_hash": packet_hash})
            response = rpc_connection.recv()
            return response

        else:
            for entry in RNS.Transport.local_client_snr_cache:
                if entry[0] == packet_hash:
                    return entry[1]

            return None

    def get_packet_q(self, packet_hash):
        if self.is_connected_to_shared_instance:
            rpc_connection = self.get_rpc_client()
            rpc_connection.send({"get": "packet_q", "packet_hash": packet_hash})
            response = rpc_connection.recv()
            return response

        else:
            for entry in RNS.Transport.local_client_q_cache:
                if entry[0] == packet_hash:
                    return entry[1]

            return None

    def halt_interface(self, interface):
        pass

    def resume_interface(self, interface):
        pass

    def reload_interface(self, interface):
        pass

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

    @staticmethod
    def link_mtu_discovery():
        """
        Returns whether link MTU discovery is enabled for the running
        instance.

        When link MTU discovery is enabled, Reticulum will
        automatically upgrade link MTUs to the highest supported
        value, increasing transfer speed and efficiency.

        :returns: True if link MTU discovery is enabled, False if not.
        """
        return Reticulum.__link_mtu_discovery

    @staticmethod
    def remote_management_enabled():
        """
        Returns whether remote management is enabled for the
        running instance.

        When remote management is enabled, authenticated peers
        can remotely query and manage this instance.

        :returns: True if remote management is enabled, False if not.
        """
        return Reticulum.__remote_management_enabled

    @staticmethod
    def probe_destination_enabled():
        return Reticulum.__allow_probes

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
# This should only be done for systems that are suited to
# act as transport nodes, ie. if they are stationary and
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
# instance names for each. On platforms supporting domain
# sockets, this can be done with the instance_name option:

instance_name = default

# Some platforms don't support domain sockets, and if that
# is the case, you can isolate different instances by
# specifying a unique set of ports for each:

# shared_instance_port = 37428
# instance_control_port = 37429


# If you want to explicitly use TCP for shared instance
# communication, instead of domain sockets, this is also
# possible, by using the following option:

# shared_instance_type = tcp


# You can configure Reticulum to panic and forcibly close
# if an unrecoverable interface error occurs, such as the
# hardware device for an interface disappearing. This is
# an optional directive, and can be left out for brevity.
# This behaviour is disabled by default.

# panic_on_interface_error = No


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
    enabled = Yes

'''.splitlines()
