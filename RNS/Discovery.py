import os
import RNS
import time
import threading
from .vendor import umsgpack as msgpack

NAME            = 0xFF
TRANSPORT_ID    = 0xFE
INTERFACE_TYPE  = 0x00
TRANSPORT       = 0x01
REACHABLE_ON    = 0x02
LATITUDE        = 0x03
LONGITUDE       = 0x04
HEIGHT          = 0x05
PORT            = 0x06
IFAC_NETNAME    = 0x07
IFAC_NETKEY     = 0x08
FREQUENCY       = 0x09
BANDWIDTH       = 0x0A
SPREADINGFACTOR = 0x0B
CODINGRATE      = 0x0C
MODULATION      = 0x0D
CHANNEL         = 0x0E

APP_NAME = "rnstransport"

class InterfaceAnnouncer():
    JOB_INTERVAL = 60
    DEFAULT_STAMP_VALUE = 14
    WORKBLOCK_EXPAND_ROUNDS = 20

    DISCOVERABLE_INTERFACE_TYPES = ["BackboneInterface", "TCPServerInterface", "TCPClientInterface",
                                    "RNodeInterface", "WeaveInterface", "I2PInterface", "KISSInterface"]

    def __init__(self, owner):
        import importlib.util
        if importlib.util.find_spec('LXMF') != None: from LXMF import LXStamper
        else:
            RNS.log("Using on-network interface discovery requires the LXMF module to be installed.", RNS.LOG_CRITICAL)
            RNS.log("You can install it with the command: pip install lxmf", RNS.LOG_CRITICAL)
            RNS.panic()

        self.owner        = owner
        self.should_run   = False
        self.job_interval = self.JOB_INTERVAL
        self.stamper      = LXStamper
        self.stamp_cache  = {}

        if self.owner.has_network_identity(): identity = self.owner.network_identity
        else:                                 identity = self.owner.identity

        self.discovery_destination = RNS.Destination(identity, RNS.Destination.IN, RNS.Destination.SINGLE,
                                                     APP_NAME, "discovery", "interface")

    def start(self):
        if not self.should_run:
            self.should_run = True
            threading.Thread(target=self.job, daemon=True).start()

    def stop(self): self.should_run = False

    def job(self):
        while self.should_run:
            time.sleep(self.job_interval)
            try:
                now = time.time()
                due_interfaces = [i for i in self.owner.interfaces if i.supports_discovery and i.discoverable and now > (i.last_discovery_announce+i.discovery_announce_interval)]
                due_interfaces.sort(key=lambda i: now-i.last_discovery_announce, reverse=True)

                if len(due_interfaces) > 0:
                    selected_interface = due_interfaces[0]
                    selected_interface.last_discovery_announce = time.time()
                    RNS.log(f"Preparing interface discovery announce for {selected_interface.name}", RNS.LOG_DEBUG)
                    app_data = self.get_interface_announce_data(selected_interface)
                    if not app_data: RNS.log(f"Could not generate interface discovery announce data for {selected_interface.name}", RNS.LOG_ERROR)
                    else:
                        RNS.log(f"Sending interface discovery announce for {selected_interface.name} with {len(app_data)}B payload", RNS.LOG_DEBUG)
                        self.discovery_destination.announce(app_data=app_data)

            except Exception as e:
                RNS.log(f"Error while preparing interface discovery announces: {e}", RNS.LOG_ERROR)
                RNS.trace_exception(e)

    def sanitize(self, in_str):
        sanitized = in_str.replace("\n", "")
        sanitized = sanitized.replace("\r", "")
        sanitized = sanitized.strip()
        return sanitized

    def get_interface_announce_data(self, interface):
        interface_type = type(interface).__name__
        stamp_value    = interface.discovery_stamp_value if interface.discovery_stamp_value else self.DEFAULT_STAMP_VALUE

        if not interface_type in self.DISCOVERABLE_INTERFACE_TYPES: return None
        else:
            flags = 0x00
            info  = {INTERFACE_TYPE: interface_type,
                     TRANSPORT:      RNS.Reticulum.transport_enabled(),
                     TRANSPORT_ID:   RNS.Transport.identity.hash,
                     NAME:           self.sanitize(interface.discovery_name),
                     LATITUDE:       interface.discovery_latitude,
                     LONGITUDE:      interface.discovery_longitude,
                     HEIGHT:         interface.discovery_height}

            if interface_type in ["BackboneInterface", "TCPServerInterface"]:
                info[REACHABLE_ON]    = self.sanitize(interface.reachable_on)
                info[PORT]            = interface.bind_port

            if interface_type == "I2PInterface" and interface.connectable and interface.b32:
                info[REACHABLE_ON]    = interface.b32

            if interface_type == "RNodeInterface":
                info[FREQUENCY]       = interface.frequency
                info[BANDWIDTH]       = interface.bandwidth
                info[SPREADINGFACTOR] = interface.sf
                info[CODINGRATE]      = interface.cr

            if interface_type == "WeaveInterface":
                info[FREQUENCY]       = interface.discovery_frequency
                info[BANDWIDTH]       = interface.discovery_bandwidth
                info[CHANNEL]         = interface.discovery_channel
                info[MODULATION]      = interface.discovery_modulation

            if interface_type == "KISSInterface" or (interface_type == "TCPClientInterface" and interface.kiss_framing):
                info[INTERFACE_TYPE]  = "KISSInterface"
                info[FREQUENCY]       = interface.discovery_frequency
                info[BANDWIDTH]       = interface.discovery_bandwidth
                info[MODULATION]      = self.sanitize(interface.discovery_modulation)

            if interface.discovery_publish_ifac == True:
                info[IFAC_NETNAME]    = self.sanitize(interface.ifac_netname)
                info[IFAC_NETKEY]     = self.sanitize(interface.ifac_netkey)

            packed    = msgpack.packb(info)
            infohash  = RNS.Identity.full_hash(packed)

            if infohash in self.stamp_cache: stamp = self.stamp_cache[infohash]
            else: stamp, v = self.stamper.generate_stamp(infohash, stamp_cost=stamp_value, expand_rounds=self.WORKBLOCK_EXPAND_ROUNDS)
            if not stamp: return None
            else: self.stamp_cache[infohash] = stamp

            if interface.discovery_encrypt:
                flags |= InterfaceAnnounceHandler.FLAG_ENCRYPTED
                if not self.owner.has_network_identity():
                    RNS.log(f"Discovery encryption requested for {interface}, but no network identity configured. Aborting discovery announce.", RNS.LOG_ERROR)
                    return None
                
                else: payload = self.owner.network_identity.encrypt(packed+stamp)
                    
            else: payload = packed+stamp

            return bytes([flags])+payload

class InterfaceAnnounceHandler:
    FLAG_SIGNED       = 0b00000001
    FLAG_ENCRYPTED    = 0b00000010

    def __init__(self, required_value=InterfaceAnnouncer.DEFAULT_STAMP_VALUE, callback=None):
        import importlib.util
        if importlib.util.find_spec('LXMF') != None: from LXMF import LXStamper
        else:
            RNS.log("Using on-network interface discovery requires the LXMF module to be installed.", RNS.LOG_CRITICAL)
            RNS.log("You can install it with the command: pip install lxmf", RNS.LOG_CRITICAL)
            RNS.panic()

        self.aspect_filter  = APP_NAME+".discovery.interface"
        self.required_value = required_value
        self.callback       = callback
        self.stamper        = LXStamper

    def received_announce(self, destination_hash, announced_identity, app_data):
        try:
            discovery_sources = RNS.Reticulum.interface_discovery_sources()
            if discovery_sources and not announced_identity.hash in discovery_sources:
                RNS.log(f"Interface discovered from non-authorized network identity {RNS.prettyhexrep(announced_identity.hash)}, ignoring", RNS.LOG_DEBUG)
                return

            if app_data and len(app_data) > self.stamper.STAMP_SIZE+1:
                flags     = app_data[0]
                app_data  = app_data[1:]
                signed    = flags & self.FLAG_SIGNED
                encrypted = flags & self.FLAG_ENCRYPTED

                if encrypted:
                    if not RNS.Transport.has_network_identity(): return
                    app_data = RNS.Transport.network_identity.decrypt(app_data)
                    if not app_data: return

                stamp     = app_data[-self.stamper.STAMP_SIZE:]
                packed    = app_data[:-self.stamper.STAMP_SIZE]
                infohash  = RNS.Identity.full_hash(packed)
                workblock = self.stamper.stamp_workblock(infohash, expand_rounds=InterfaceAnnouncer.WORKBLOCK_EXPAND_ROUNDS)
                value     = self.stamper.stamp_value(workblock, stamp)
                valid     = self.stamper.stamp_valid(stamp, self.required_value, workblock)

                if not valid:
                    RNS.log(f"Ignored discovered interface with invalid stamp", RNS.LOG_DEBUG)
                    return

                if value < self.required_value: RNS.log(f"Ignored discovered interface with stamp value {value}", RNS.LOG_DEBUG)
                else:
                    info     = None
                    unpacked = msgpack.unpackb(packed)
                    if INTERFACE_TYPE in unpacked:
                        interface_type        = unpacked[INTERFACE_TYPE]
                        info = {"type":         interface_type,
                                "transport":    unpacked[TRANSPORT],
                                "name":         unpacked[NAME] or f"Discovered {interface_type}",
                                "received":     time.time(),
                                "stamp":        stamp,
                                "value":        value,
                                "transport_id": RNS.hexrep(unpacked[TRANSPORT_ID], delimit=False),
                                "network_id":   RNS.hexrep(announced_identity.hash, delimit=False),
                                "hops":         RNS.Transport.hops_to(destination_hash),
                                "latitude":     unpacked[LATITUDE],
                                "longitude":    unpacked[LONGITUDE],
                                "height":       unpacked[HEIGHT]}

                        if IFAC_NETNAME in unpacked: info["ifac_netname"] = unpacked[IFAC_NETNAME]
                        if IFAC_NETKEY  in unpacked: info["ifac_netkey"]  = unpacked[IFAC_NETKEY]

                        if interface_type in ["BackboneInterface", "TCPServerInterface"]:
                            backbone_support     = not RNS.vendor.platformutils.is_windows()
                            info["reachable_on"] = unpacked[REACHABLE_ON]
                            info["port"]         = unpacked[PORT]
                            connection_interface = "BackboneInterface" if backbone_support else "TCPClientInterface"
                            remote_str           = "remote" if backbone_support else "target_host"
                            cfg_name             = info["name"]
                            cfg_remote           = info["reachable_on"]
                            cfg_port             = info["port"]
                            cfg_identity         = info["transport_id"]
                            cfg_netname          = info["ifac_netname"] if "ifac_netname" in info else None
                            cfg_netkey           = info["ifac_netkey"] if "ifac_netkey" in info else None
                            cfg_netname_str      = f"\n  network_name = {cfg_netname}" if cfg_netname else ""
                            cfg_netkey_str       = f"\n  passphrase = {cfg_netkey}" if cfg_netkey else ""
                            cfg_identity_str     = f"\n  transport_identity = {cfg_identity}"
                            info["config_entry"] = f"[[{cfg_name}]]\n  type = {connection_interface}\n  enabled = yes\n  {remote_str} = {cfg_remote}\n  target_port = {cfg_port}{cfg_identity_str}{cfg_netname_str}{cfg_netkey_str}"

                        if interface_type == "I2PInterface":
                            info["reachable_on"] = unpacked[REACHABLE_ON]
                            cfg_name             = info["name"]
                            cfg_remote           = info["reachable_on"]
                            cfg_identity         = info["transport_id"]
                            cfg_netname          = info["ifac_netname"] if "ifac_netname" in info else None
                            cfg_netkey           = info["ifac_netkey"] if "ifac_netkey" in info else None
                            cfg_netname_str      = f"\n  network_name = {cfg_netname}" if cfg_netname else ""
                            cfg_netkey_str       = f"\n  passphrase = {cfg_netkey}" if cfg_netkey else ""
                            cfg_identity_str     = f"\n  transport_identity = {cfg_identity}"
                            info["config_entry"] = f"[[{cfg_name}]]\n  type = I2PInterface\n  enabled = yes\n  peers = {cfg_remote}{cfg_identity_str}{cfg_netname_str}{cfg_netkey_str}"

                        if interface_type == "RNodeInterface":
                            info["frequency"]    = unpacked[FREQUENCY]
                            info["bandwidth"]    = unpacked[BANDWIDTH]
                            info["sf"]           = unpacked[SPREADINGFACTOR]
                            info["cr"]           = unpacked[CODINGRATE]
                            cfg_name             = info["name"]
                            cfg_frequency        = info["frequency"]
                            cfg_bandwidth        = info["bandwidth"]
                            cfg_sf               = info["sf"]
                            cfg_cr               = info["cr"]
                            cfg_identity         = info["transport_id"]
                            cfg_netname          = info["ifac_netname"] if "ifac_netname" in info else None
                            cfg_netkey           = info["ifac_netkey"] if "ifac_netkey" in info else None
                            cfg_netname_str      = f"\n  network_name = {cfg_netname}" if cfg_netname else ""
                            cfg_netkey_str       = f"\n  passphrase = {cfg_netkey}" if cfg_netkey else ""
                            cfg_identity_str     = f"\n  transport_identity = {cfg_identity}"
                            info["config_entry"] = f"[[{cfg_name}]]\n  type = RNodeInterface\n  enabled = yes\n  port = \n  frequency = {cfg_frequency}\n  bandwidth = {cfg_bandwidth}\n  spreadingfactor = {cfg_sf}\n  codingrate = {cfg_cr}\n  txpower = {cfg_netname_str}{cfg_netkey_str}"

                        if interface_type == "WeaveInterface":
                            info["frequency"]    = unpacked[FREQUENCY]
                            info["bandwidth"]    = unpacked[BANDWIDTH]
                            info["channel"]      = unpacked[CHANNEL]
                            info["modulation"]   = unpacked[MODULATION]
                            cfg_name             = info["name"]
                            cfg_identity         = info["transport_id"]
                            cfg_netname          = info["ifac_netname"] if "ifac_netname" in info else None
                            cfg_netkey           = info["ifac_netkey"] if "ifac_netkey" in info else None
                            cfg_netname_str      = f"\n  network_name = {cfg_netname}" if cfg_netname else ""
                            cfg_netkey_str       = f"\n  passphrase = {cfg_netkey}" if cfg_netkey else ""
                            cfg_identity_str     = f"\n  transport_identity = {cfg_identity}"
                            info["config_entry"] = f"[[{cfg_name}]]\n  type = WeaveInterface\n  enabled = yes\n  port = {cfg_netname_str}{cfg_netkey_str}"

                        if interface_type == "KISSInterface":
                            info["frequency"]    = unpacked[FREQUENCY]
                            info["bandwidth"]    = unpacked[BANDWIDTH]
                            info["modulation"]   = unpacked[MODULATION]
                            cfg_name             = info["name"]
                            cfg_frequency        = info["frequency"]
                            cfg_bandwidth        = info["bandwidth"]
                            cfg_modulation       = info["modulation"]
                            cfg_identity         = info["transport_id"]
                            cfg_netname          = info["ifac_netname"] if "ifac_netname" in info else None
                            cfg_netkey           = info["ifac_netkey"] if "ifac_netkey" in info else None
                            cfg_netname_str      = f"\n  network_name = {cfg_netname}" if cfg_netname else ""
                            cfg_netkey_str       = f"\n  passphrase = {cfg_netkey}" if cfg_netkey else ""
                            cfg_identity_str     = f"\n  transport_identity = {cfg_identity}"
                            info["config_entry"] = f"[[{cfg_name}]]\n  type = KISSInterface\n  enabled = yes\n  port = \n  # Frequency: {cfg_frequency}\n  # Bandwidth: {cfg_bandwidth}\n  # Modulation: {cfg_modulation}{cfg_identity_str}{cfg_netname_str}{cfg_netkey_str}"

                        discovery_hash_material = info["transport_id"]+info["name"]
                        info["discovery_hash"] = RNS.Identity.full_hash(discovery_hash_material.encode("utf-8"))

                    if self.callback and callable(self.callback): self.callback(info)

        except Exception as e:
            RNS.log(f"An error occurred while trying to decode discovered interface. The contained exception was: {e}", RNS.LOG_ERROR)

class InterfaceDiscovery():
    THRESHOLD_UNKNOWN = 24*60*60
    THRESHOLD_STALE   = 3*24*60*60
    THRESHOLD_REMOVE  = 7*24*60*60

    MONITOR_INTERVAL  = 5
    DETACH_THRESHOLD  = 12

    STATUS_STALE      = 0
    STATUS_UNKNOWN    = 100
    STATUS_AVAILABLE  = 1000
    STATUS_CODE_MAP   = {"available": STATUS_AVAILABLE, "unknown": STATUS_UNKNOWN, "stale": STATUS_STALE}
    AUTOCONNECT_TYPES = ["BackboneInterface", "TCPServerInterface"]

    def __init__(self, required_value=InterfaceAnnouncer.DEFAULT_STAMP_VALUE, callback=None, discover_interfaces=True):
        if not required_value: required_value = InterfaceAnnouncer.DEFAULT_STAMP_VALUE

        self.required_value          = required_value
        self.discovery_callback      = callback
        self.rns_instance            = RNS.Reticulum.get_instance()
        self.monitored_interfaces    = []
        self.monitoring_autoconnects = False
        self.monitor_interval        = self.MONITOR_INTERVAL
        self.detach_threshold        = self.DETACH_THRESHOLD

        if not self.rns_instance: raise SystemError("Attempt to start interface discovery listener without an active RNS instance")
        self.storagepath = os.path.join(RNS.Reticulum.storagepath, "discovery", "interfaces")
        if not os.path.isdir(self.storagepath): os.makedirs(self.storagepath)
        
        if discover_interfaces:
            self.handler = InterfaceAnnounceHandler(callback=self.interface_discovered, required_value=self.required_value)
            RNS.Transport.register_announce_handler(self.handler)
            threading.Thread(target=self.connect_discovered, daemon=True).start()

    def list_discovered_interfaces(self):
        now = time.time()
        discovered_interfaces = []
        discovery_sources = RNS.Reticulum.interface_discovery_sources()
        for filename in os.listdir(self.storagepath):
            try:
                filepath = os.path.join(self.storagepath, filename)
                with open(filepath, "rb") as f: info = msgpack.unpackb(f.read())
                should_remove = False
                heard_delta = now-info["last_heard"]
                
                if heard_delta > self.THRESHOLD_REMOVE: should_remove = True
                elif discovery_sources and not "network_id" in info: should_remove = True
                elif discovery_sources and not bytes.fromhex(info["network_id"]) in discovery_sources: should_remove = True

                if should_remove:
                    os.unlink(filepath)
                    continue
                
                else:
                    if   heard_delta > self.THRESHOLD_STALE:   info["status"] = "stale"
                    elif heard_delta > self.THRESHOLD_UNKNOWN: info["status"] = "unknown"
                    else:                                      info["status"] = "available"

                    info["status_code"] = self.STATUS_CODE_MAP[info["status"]]
                    discovered_interfaces.append(info)

            except Exception as e:
                RNS.log(f"Error while loading discovered interface data: {e}", RNS.LOG_ERROR)
                RNS.log(f"The interface data file {os.path.join(self.storagepath, filename)} may be corrupt", RNS.LOG_ERROR)
                RNS.trace_exception(e)

        discovered_interfaces.sort(key=lambda info: (info["status_code"], info["value"], info["last_heard"]), reverse=True)
        return discovered_interfaces

    def interface_discovered(self, info):
        try:
            name = info["name"]
            value = info["value"]
            interface_type = info["type"]
            discovery_hash = info["discovery_hash"]
            hops = info["hops"]; ms = "" if hops == 1 else "s"
            filename = RNS.hexrep(discovery_hash, delimit=False)
            filepath = os.path.join(self.storagepath, filename)
            RNS.log(f"Discovered {interface_type} {hops} hop{ms} away with stamp value {value}: {name}", RNS.LOG_DEBUG)
            if not os.path.isfile(filepath):
                try:
                    with open(filepath, "wb") as f:
                        info["discovered"]  = info["received"]
                        info["last_heard"]  = info["received"]
                        info["heard_count"] = 0
                        f.write(msgpack.packb(info))
                
                except Exception as e:
                    RNS.log(f"Error while persisting discovered interface data: {e}", RNS.LOG_ERROR)
                    RNS.trace_exception(e)
                    return

            else:
                discovered  = None
                heard_count = None
                try:
                    with open(filepath, "rb") as f:
                        last_info   = msgpack.unpackb(f.read())
                        discovered  = last_info["discovered"]
                        heard_count = last_info["heard_count"]

                    if discovered  == None: discovered  = info["discovered"]
                    if heard_count == None: heard_count = 0

                    with open(filepath, "wb") as f:
                        info["discovered"] = discovered
                        info["last_heard"] = info["received"]
                        info["heard_count"] = heard_count+1
                        f.write(msgpack.packb(info))

                except Exception as e:
                    RNS.log(f"Error while persisting discovered interface data: {e}", RNS.LOG_ERROR)
                    RNS.trace_exception(e)
                    return

        except Exception as e:
            RNS.log(f"Error processing discovered interface data: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)
            return

        self.autoconnect(info)

        try:
            if self.discovery_callback and callable(self.discovery_callback): self.discovery_callback(info)
        except Exception as e: RNS.log(f"Error while processing external interface discovery callback: {e}", RNS.LOG_ERROR)

    def monitor_interface(self, interface):
        if not interface in self.monitored_interfaces:
            self.monitored_interfaces.append(interface)

        if not self.monitoring_autoconnects:
            self.monitoring_autoconnects = True
            threading.Thread(target=self.__monitor_job, daemon=True).start()

    def __monitor_job(self):
        while self.monitoring_autoconnects:
            time.sleep(self.monitor_interval)
            detached_interfaces = []
            online_interfaces = 0
            for interface in self.monitored_interfaces:
                try:
                    if interface.online:
                        online_interfaces += 1
                        if hasattr(interface, "autoconnect_down") and interface.autoconnect_down != None:
                            RNS.log(f"Auto-discovered interface {interface} reconnected")
                            interface.autoconnect_down = None

                    else:
                        if not hasattr(interface, "autoconnect_down") or interface.autoconnect_down == None:
                            RNS.log(f"Auto-discovered interface {interface} disconnected", RNS.LOG_DEBUG)
                            interface.autoconnect_down = time.time()

                        else:
                            down_for = time.time()-interface.autoconnect_down
                            if down_for >= self.detach_threshold:
                                RNS.log(f"Auto-discovered interface {interface} has been down for {RNS.prettytime(down_for)}, detaching", RNS.LOG_DEBUG)
                                detached_interfaces.append(interface)

                except Exception as e:
                    RNS.log(f"Error while checking auto-connected interface state for {interface}: {e}", RNS.LOG_ERROR)

            if online_interfaces >= RNS.Reticulum.max_autoconnected_interfaces():
                for interface in RNS.Transport.interfaces:
                    if hasattr(interface, "bootstrap_only") and interface.bootstrap_only == True:
                        RNS.log(f"Tearing down bootstrap-only {interface} since target connected auto-discovered interface count has been reached", RNS.LOG_INFO)
                        if not interface in detached_interfaces: detached_interfaces.append(interface)

            if online_interfaces == 0:
                RNS.log(f"No auto-discovered interfaces connected, re-enabling bootstrap interfaces", RNS.LOG_NOTICE)
                # TODO: Implement
                RNS.log(f"Available bootstrap configs:\n{RNS.Reticulum.get_instance().bootstrap_configs}", RNS.LOG_DEBUG)

            for interface in detached_interfaces:
                try: self.teardown_interface(interface)
                except Exception as e:
                    RNS.log(f"Error while de-registering auto-connected interface from transport: {e}", RNS.LOG_ERROR)

    def teardown_interface(self, interface):
        interface.detach()
        RNS.Transport.interfaces.remove(interface)
        self.monitored_interfaces.remove(interface)

    def autoconnect_count(self):
        return len([i for i in RNS.Transport.interfaces if hasattr(i, "autoconnect_hash")])
        
    def connect_discovered(self):
        if RNS.Reticulum.should_autoconnect_discovered_interfaces():
            try:
                discovered_interfaces = self.list_discovered_interfaces()
                for info in discovered_interfaces:
                    if self.autoconnect_count() >= RNS.Reticulum.max_autoconnected_interfaces(): break
                    self.autoconnect(info)

            except Exception as e:
                RNS.log(f"Error while reconnecting discovered interfaces: {e}", RNS.LOG_ERROR)

    def autoconnect(self, info):
        try:
            if RNS.Reticulum.should_autoconnect_discovered_interfaces():
                autoconnected_count = self.autoconnect_count()
                if autoconnected_count < RNS.Reticulum.max_autoconnected_interfaces():
                    interface_type = info["type"]
                    if interface_type in self.AUTOCONNECT_TYPES:
                        endpoint_specifier = ""
                        if "reachable_on" in info: endpoint_specifier += str(info["reachable_on"])
                        if "port" in info:         endpoint_specifier += str(info["port"])
                        endpoint_hash = RNS.Identity.full_hash(endpoint_specifier.encode("utf-8"))
                        exists = False
                        for interface in RNS.Transport.interfaces:
                            if hasattr(interface, "autoconnect_hash") and interface.autoconnect_hash:
                                exists = True
                                break
                            
                            else:
                                dest_match = "reachable_on" in info and hasattr(interface, "target_ip") and interface.target_ip == info["reachable_on"]
                                port_match = not "port" in info or (hasattr(interface, "target_port") and "port" in info and interface.target_port == info["port"])
                                b32d_match = "reachable_on" in info and hasattr(interface, "b32") and interface.b32 == info["reachable_on"]

                                if (dest_match and port_match) or b32d_match:
                                    exists = True
                                    break

                        if exists: RNS.log(f"Discovered {interface_type} already exists, not auto-connecting", RNS.LOG_DEBUG)
                        else:
                            if interface_type == "TCPClientInterface":
                                RNS.log(f"Your operating system does not support the Backbone interface type, and must degrade to using TCPClientInterface instead", RNS.LOG_WARNING)
                                RNS.log(f"Auto-connecting discovered TCPClient interfaces is not yet implemented, aborting auto-connect", RNS.LOG_WARNING)
                                RNS.log(f"You can obtain the configuration entry and add this interface manually instead using rnstatus -D", RNS.LOG_WARNING)
                                return

                            if interface_type == "I2PInterface":
                                RNS.log(f"Auto-connecting discovered I2P interfaces is not yet implemented, aborting auto-connect", RNS.LOG_WARNING)
                                RNS.log(f"You can obtain the configuration entry and add this interface manually instead using rnstatus -D", RNS.LOG_WARNING)
                                return

                            RNS.log(f"Auto-connecting discovered {interface_type}")
                            config_entry = info["config_entry"]
                            interface_config = {}
                            interface_name = info["name"]
                            interface_config["name"] = f"{interface_name}"
                            ifac_netname = info["ifac_netname"] if "ifac_netname" in info else None
                            ifac_netkey  = info["ifac_netkey"]  if "ifac_netkey"  in info else None
                            interface    = None

                            if interface_type == "BackboneInterface":
                                from RNS.Interfaces import BackboneInterface
                                interface_config["target_host"] = info["reachable_on"]
                                interface_config["target_port"] = info["port"]
                                interface = BackboneInterface.BackboneClientInterface(RNS.Transport, interface_config)

                            if interface:
                                interface.autoconnect_hash = endpoint_hash
                                interface.autoconnect_source = info["network_id"]
                                RNS.Reticulum.get_instance()._add_interface(interface, ifac_netname=ifac_netname, ifac_netkey=ifac_netkey, configured_bitrate=5E6)
                                self.monitor_interface(interface)

        except Exception as e:
            RNS.log(f"Error while auto-connecting discovered interface: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

class BlackholeUpdater():
    INITIAL_WAIT    = 20
    JOB_INTERVAL    = 60
    UPDATE_INTERVAL = 1*60*60
    SOURCE_TIMEOUT  = 25

    def __init__(self):
        self.last_updates = {}
        self.should_run   = False
        self.job_interval = self.JOB_INTERVAL
        self.update_lock  = threading.Lock()

    def start(self):
        if not self.should_run:
            source_count = len(RNS.Reticulum.blackhole_sources())
            ms = "" if source_count == 1 else "s"
            RNS.log(f"Starting blackhole updater with {source_count} source{ms}", RNS.LOG_DEBUG)
            self.should_run = True
            threading.Thread(target=self.job, daemon=True).start()

    def stop(self): self.should_run = False

    def update_link_established(self, link):
        remote_identity = link.get_remote_identity()
        RNS.log(f"Link established for blackhole list update from {RNS.prettyhexrep(remote_identity.hash)}", RNS.LOG_DEBUG)
        receipt = link.request("/list")
        while not receipt.concluded(): time.sleep(0.2)
        response = receipt.get_response()
        link.teardown()
        
        if type(response) == dict: blackhole_list = response
        else:                      blackhole_list = None

        if blackhole_list:
            added = 0
            for identity_hash in blackhole_list:
                entry = blackhole_list[identity_hash]
                if not identity_hash in RNS.Transport.blackholed_identities:
                    RNS.Transport.blackholed_identities[identity_hash] = entry
                    added += 1

            if added > 0:
                spec = "identity" if added == 1 else "identities"
                RNS.log(f"Added {added} blackholed {spec} from {RNS.prettyhexrep(remote_identity.hash)}", RNS.LOG_DEBUG)

                try:
                    sourcelistpath = os.path.join(RNS.Reticulum.blackholepath, RNS.hexrep(remote_identity.hash, delimit=False))
                    tmppath = f"{sourcelistpath}.tmp"
                    with open(tmppath, "wb") as f: f.write(msgpack.packb(blackhole_list))
                    if os.path.isfile(sourcelistpath): os.unlink(sourcelistpath)
                    os.rename(tmppath, sourcelistpath)
                
                except Exception as e:
                    RNS.log(f"Error while persisting blackhole list from {RNS.prettyhexrep(remote_identity.hash)}: {e}", RNS.LOG_ERROR)

        RNS.log(f"Blackhole list update from {RNS.prettyhexrep(remote_identity.hash)} completed", RNS.LOG_DEBUG)

    def job(self):
        time.sleep(self.INITIAL_WAIT)
        while self.should_run:
            try:
                now = time.time()
                for identity_hash in RNS.Reticulum.blackhole_sources():
                    if identity_hash in self.last_updates: last_update = self.last_updates[identity_hash]
                    else:                                  last_update = 0

                    if now > last_update+self.UPDATE_INTERVAL:
                        try:
                            destination_hash = RNS.Destination.hash_from_name_and_identity("rnstransport.info.blackhole", identity_hash)
                            RNS.log(f"Attempting blackhole list update from {RNS.prettyhexrep(identity_hash)}...", RNS.LOG_DEBUG)
                            if not RNS.Transport.await_path(destination_hash): RNS.log(f"No path available for blackhole list update from {RNS.prettyhexrep(identity_hash)}, retrying later", RNS.LOG_VERBOSE)
                            else:
                                remote_identity = RNS.Identity.recall(destination_hash)
                                destination = RNS.Destination(remote_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "rnstransport", "info", "blackhole")
                                RNS.Link(destination, established_callback=self.update_link_established)
                                self.last_updates[identity_hash] = time.time()

                        except Exception as e:
                            RNS.log(f"Error while establishing link for blackhole list update from {RNS.prettyhexrep(identity_hash)}: {e}", RNS.LOG_ERROR)

            except Exception as e:
                RNS.log(f"Error in blackhole list updater job: {e}", RNS.LOG_ERROR)
                RNS.trace_exception(e)

            time.sleep(self.job_interval)