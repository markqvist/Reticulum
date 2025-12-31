import os
import RNS
import time
import threading
from .vendor import umsgpack as msgpack

NAME            = 0xFF
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

APP_NAME = "rnstransport"

class InterfaceAnnouncer():
    JOB_INTERVAL = 60
    DEFAULT_STAMP_VALUE = 14
    WORKBLOCK_EXPAND_ROUNDS = 20

    DISCOVERABLE_INTERFACE_TYPES = ["BackboneInterface", "TCPServerInterface", "TCPClientInterface", "RNodeInterface", "I2PInterface", "KISSInterface"]

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

        self.discovery_destination = RNS.Destination(self.owner.identity, RNS.Destination.IN, RNS.Destination.SINGLE,
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
                    RNS.log(f"Preparing interface discovery announce for {selected_interface.name}", RNS.LOG_VERBOSE)
                    app_data = self.get_interface_announce_data(selected_interface)
                    if not app_data: RNS.log(f"Could not generate interface discovery announce data for {selected_interface.name}", RNS.LOG_ERROR)
                    else:
                        RNS.log(f"Sending interface discovery announce for {selected_interface.name}", RNS.LOG_VERBOSE)
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
        stamp_value = interface.discovery_stamp_value if interface.discovery_stamp_value else self.DEFAULT_STAMP_VALUE
        if not interface_type in self.DISCOVERABLE_INTERFACE_TYPES: return None
        else:
            info = {INTERFACE_TYPE: interface_type,
                    TRANSPORT:      RNS.Reticulum.transport_enabled(),
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

            if interface_type == "KISSInterface" or (interface_type == "TCPClientInterface" and interface.kiss_framing):
                info[INTERFACE_TYPE]  = "KISSInterface"
                info[FREQUENCY]       = interface.discovery_frequency
                info[BANDWIDTH]       = interface.discovery_bandwidth
                info[MODULATION]      = self.sanitize(interface.discovery_modulation)

            if interface.discovery_publish_ifac == True:
                info[IFAC_NETNAME]    = self.sanitize(interface.ifac_netname)
                info[IFAC_NETKEY]     = self.sanitize(interface.ifac_netkey)

            packed   = msgpack.packb(info)
            infohash = RNS.Identity.full_hash(packed)

            if infohash in self.stamp_cache: return packed+self.stamp_cache[infohash]
            else: stamp, v = self.stamper.generate_stamp(infohash, stamp_cost=stamp_value, expand_rounds=self.WORKBLOCK_EXPAND_ROUNDS)

            if not stamp: return None
            else:
                self.stamp_cache[infohash] = stamp
                return bytes([0x00])+packed+stamp

class InterfaceAnnounceHandler:
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
            if app_data and len(app_data) > self.stamper.STAMP_SIZE+1:
                app_data  = app_data[1:]
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
                        interface_type     = unpacked[INTERFACE_TYPE]
                        info = {"type":      interface_type,
                                "transport": unpacked[TRANSPORT],
                                "name":      unpacked[NAME] or f"Discovered {interface_type}",
                                "received":  time.time(),
                                "stamp":     stamp,
                                "value":     value,
                                "identity":  RNS.hexrep(announced_identity.hash, delimit=False),
                                "hops":      RNS.Transport.hops_to(destination_hash),
                                "latitude":  unpacked[LATITUDE],
                                "longitude": unpacked[LONGITUDE],
                                "height":    unpacked[HEIGHT]}

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
                            cfg_identity         = info["identity"]
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
                            cfg_identity         = info["identity"]
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
                            cfg_identity         = info["identity"]
                            cfg_netname          = info["ifac_netname"] if "ifac_netname" in info else None
                            cfg_netkey           = info["ifac_netkey"] if "ifac_netkey" in info else None
                            cfg_netname_str      = f"\n  network_name = {cfg_netname}" if cfg_netname else ""
                            cfg_netkey_str       = f"\n  passphrase = {cfg_netkey}" if cfg_netkey else ""
                            cfg_identity_str     = f"\n  transport_identity = {cfg_identity}"
                            info["config_entry"] = f"[[{cfg_name}]]\n  type = RNodeInterface\n  enabled = yes\n  port = \n  frequency = {cfg_frequency}\n  bandwidth = {cfg_bandwidth}\n  spreadingfactor = {cfg_sf}\n  codingrate = {cfg_cr}\n  txpower = {cfg_netname_str}{cfg_netkey_str}"

                        if interface_type == "KISSInterface":
                            info["frequency"]    = unpacked[FREQUENCY]
                            info["bandwidth"]    = unpacked[BANDWIDTH]
                            info["modulation"]   = unpacked[MODULATION]
                            cfg_name             = info["name"]
                            cfg_frequency        = info["frequency"]
                            cfg_bandwidth        = info["bandwidth"]
                            cfg_modulation       = info["modulation"]
                            cfg_identity         = info["identity"]
                            cfg_netname          = info["ifac_netname"] if "ifac_netname" in info else None
                            cfg_netkey           = info["ifac_netkey"] if "ifac_netkey" in info else None
                            cfg_netname_str      = f"\n  network_name = {cfg_netname}" if cfg_netname else ""
                            cfg_netkey_str       = f"\n  passphrase = {cfg_netkey}" if cfg_netkey else ""
                            cfg_identity_str     = f"\n  transport_identity = {cfg_identity}"
                            info["config_entry"] = f"[[{cfg_name}]]\n  type = KISSInterface\n  enabled = yes\n  port = \n  # Frequency: {cfg_frequency}\n  # Bandwidth: {cfg_bandwidth}\n  # Modulation: {cfg_modulation}{cfg_identity_str}{cfg_netname_str}{cfg_netkey_str}"

                        discovery_hash_material = info["identity"]+info["name"]
                        info["discovery_hash"] = RNS.Identity.full_hash(discovery_hash_material.encode("utf-8"))

                    RNS.log(f"Discovered interface with stamp value {value}: {info}", RNS.LOG_DEBUG)
                    if self.callback and callable(self.callback): self.callback(info)

        except Exception as e:
            RNS.log(f"An error occurred while trying to decode discovered interface. The contained exception was: {e}", RNS.LOG_ERROR)

class InterfaceDiscovery():
    THRESHOLD_UNKNOWN = 24*60*60
    THRESHOLD_STALE   = 7*24*60*60
    THRESHOLD_REMOVE  = 30*24*60*60

    STATUS_STALE      = 0
    STATUS_UNKNOWN    = 100
    STATUS_AVAILABLE  = 1000

    STATUS_CODE_MAP   = {"available": STATUS_AVAILABLE, "unknown": STATUS_UNKNOWN, "stale": STATUS_STALE}

    def __init__(self, required_value=InterfaceAnnouncer.DEFAULT_STAMP_VALUE, callback=None, discover_interfaces=True):
        if not required_value: required_value = InterfaceAnnouncer.DEFAULT_STAMP_VALUE

        self.required_value     = required_value
        self.discovery_callback = callback
        self.rns_instance       = RNS.Reticulum.get_instance()

        if not self.rns_instance: raise SystemError("Attempt to start interface discovery listener without an active RNS instance")
        self.storagepath = os.path.join(RNS.Reticulum.storagepath, "discovery", "interfaces")
        if not os.path.isdir(self.storagepath): os.makedirs(self.storagepath)
        
        if discover_interfaces:
            self.handler = InterfaceAnnounceHandler(callback=self.interface_discovered, required_value=self.required_value)
            RNS.Transport.register_announce_handler(self.handler)

    def list_discovered_interfaces(self):
        now = time.time()
        discovered_interfaces = []
        for filename in os.listdir(self.storagepath):
            try:
                filepath = os.path.join(self.storagepath, filename)
                with open(filepath, "rb") as f: info = msgpack.unpackb(f.read())
                heard_delta = now-info["last_heard"]
                if heard_delta > self.THRESHOLD_REMOVE:
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
                RNS.trace_exception(e)

        discovered_interfaces.sort(key=lambda info: (info["status_code"], info["value"], info["last_heard"]), reverse=True)
        return discovered_interfaces

    def interface_discovered(self, info):
        try:
            name = info["name"]
            discovery_hash = info["discovery_hash"]
            hops = info["hops"]; ms = "" if hops == 1 else "s"
            filename = RNS.hexrep(discovery_hash, delimit=False)
            filepath = os.path.join(self.storagepath, filename)
            RNS.log(f"Discovered interface {RNS.prettyhexrep(discovery_hash)} {hops} hop{ms} away: {name}", RNS.LOG_DEBUG)
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

        if self.discovery_callback and callable(self.discovery_callback): self.discovery_callback(info)
