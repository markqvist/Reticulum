# Reticulum License
#
# Copyright (c) 2016-2026 Mark Qvist
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

import os
import gc
import RNS
import time
import math
import ctypes
import ctypes.util
import struct
import inspect
import threading
from time import sleep
from collections import deque
from queue import Full, Empty
from threading import Lock, Condition
from .vendor import umsgpack as umsgpack
from RNS.Interfaces.BackboneInterface import BackboneInterface
from RNS.Storage import AnnounceRateTable, PacketHashlist, AnnounceCache
from RNS.Stamps import generate_stamp, stamp_workblock, stamp_valid, stamp_value, cancel_work

class InboundQueues:
    __slots__ = ("_cond", "_queues", "_sizes", "_dropped", "_hw_mark")

    def __init__(self, sizes, hw_mark=None):
        self._cond    = Condition()
        self._queues  = [deque() for _ in sizes]
        self._sizes   = sizes
        self._dropped = [0 for _ in sizes]
        self._hw_mark = hw_mark or max(128, BackboneInterface.DP_IC_HIGH_WM)

    def put(self, traffic_class, item, block=False, timeout=None):
        with self._cond:
            q = self._queues[traffic_class]; ql = len(q)
            if traffic_class == Transport.TC_DATA and ql >= self._hw_mark:
                BackboneInterface._throttle_immediate(ql)
            if ql >= self._sizes[traffic_class]:
                self._dropped[traffic_class] += 1
                raise Full
            q.append(item)
            # For single drainer, notify() suffices, but will
            # need to move this to notify_all for the future
            # transition to free-threaded drainers.
            self._cond.notify()

    def get(self, block=True, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._cond:
            while True:
                # Scan queues in priority order
                for q in self._queues:
                    if q: return q.popleft()
                if not block: raise Empty
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0: raise Empty
                self._cond.wait(remaining)

    # Approximate queue height, this is an approximate value,
    # reads without locking and never blocks.
    def qsize(self, traffic_class=None):
        if traffic_class is None: return sum(len(q) for q in self._queues)
        return len(self._queues[traffic_class])

    # Consistent-time, single-instant height snapshot.
    def snapshot(self):
        with self._cond:
            heights = tuple(len(q) for q in self._queues)
            dropped = tuple(d for d in self._dropped)
        return (sum(heights), heights, dropped)

class WorkerQueues:
    __slots__ = ("_cond", "_queues", "_sizes")

    def __init__(self, sizes):
        self._cond    = Condition()
        self._queues  = [deque() for _ in sizes]
        self._sizes   = sizes

    def put(self, priority, key, item):
        with self._cond:
            q = self._queues[priority]

            if key != None:
                i = 0
                while i < len(q):
                    if q[i][0] == key: del q[i]
                    else:              i += 1

            if len(q) >= self._sizes[priority]: raise Full

            q.append((key, item))
            self._cond.notify()

    def get(self, block=True, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._cond:
            while True:
                # Scan queues in priority order
                for q in self._queues:
                    if q: return q.popleft()
                if not block: raise Empty
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0: raise Empty
                self._cond.wait(remaining)

    def qsize(self, priority=None):
        with self._cond:
            if priority != None: return len(self._queues[priority])
            else:                return sum(len(q) for q in self._queues)

class Transport:
    """
    Through static methods of this class you can interact with the
    Transport system of Reticulum.
    """
    # Constants
    BROADCAST                   = 0x00;
    TRANSPORT                   = 0x01;
    RELAY                       = 0x02;
    TUNNEL                      = 0x03;
    types                       = [BROADCAST, TRANSPORT, RELAY, TUNNEL]

    REACHABILITY_UNREACHABLE    = 0x00
    REACHABILITY_DIRECT         = 0x01
    REACHABILITY_TRANSPORT      = 0x02

    TC_DATA                     = 0x00
    TC_ANNOUNCE                 = 0x01
    TC_PATH_REQUEST             = 0x02
    TC_INGRESS_LIMITED          = 0x03

    APP_NAME = "rnstransport"

    PATHFINDER_M                = 128          # Max hops
    """
    Maximum amount of hops that Reticulum will transport a packet.
    """
    
    PATHFINDER_R                = 1            # Retransmit retries
    PATHFINDER_G                = 5            # Retry grace period
    PATHFINDER_RW               = 0.5          # Random window for announce rebroadcast
    AP_PATH_TIME                = 60*60*24     # Path expiration of one day for Access Point paths
    ROAMING_PATH_TIME           = 60*60*6      # Path expiration of 6 hours for Roaming paths

    # TODO: Calculate an optimal number for this in
    # various situations
    LOCAL_REBROADCASTS_MAX      = 2            # How many local rebroadcasts of an announce is allowed

    PATH_REQUEST_TIMEOUT        = 15           # Default timeout for client path requests in seconds
    PATH_REQUEST_GATE_TIMEOUT   = 45           # Default timeout for client path request gate control in seconds
    PATH_REQUEST_GRACE          = 0.4          # Grace time before a path announcement is made, allows directly reachable peers to respond first
    PATH_REQUEST_RG             = 1.5          # Extra grace time for roaming-mode interfaces to allow more suitable peers to respond first
    PATH_REQUEST_MI             = 20           # Minimum interval in seconds for automated path requests

    TRANSPORT_WORKERS           = 1
    USE_INBOUND_QUEUE           = True
    USE_OUTBOUND_QUEUE          = False
    INBOUND_DA_QUEUE_LENGTH     = 1024
    INBOUND_AN_QUEUE_LENGTH     = 128
    INBOUND_PR_QUEUE_LENGTH     = 128
    INBOUND_IL_QUEUE_LENGTH     = 8

    STAMPS_ENABLED              = True         # Whether to check for and validate stamps on announces and path requests
    STAMPS_ENFORCED             = False        # Whether to enforce stamp requirements
    LR_STAMPS_ENFORCED          = False        # Whether to enforce link request stamp requirements
    STAMP_DESTINATIONS          = False        # Whether to stamp destination announces emitted from this instance
    STAMP_PRS                   = False        # Whether to stamp path requests emitted from this instance
    STAMP_LRS                   = True         # Whether to stamp link requests emitted from this instance
    ALWAYS_STAMP_LRS            = False        # Whether to stamp link requests even when no link cost is announced
    STAMP_COST_CAP              = 100          # Global hard cap on stamp cost to ensure search-space viability at 14-byte stamp sizes
    LINK_COST_CAP               = 40           # Global hard cap on link request cost, separate from detached stamps
    DESTINATION_COST            = 23.5         # Default required announce cost if no specifics configured or determined
    DESTINATION_VALUE           = 25.0         # Default target stamp value for emitted announces
    PR_COST                     = 15.8         # Default required path request cost if no specifics configured or determined
    PR_VALUE                    = 15.8         # Default target stamp value for emitted path requests
    LR_COST                     = 12.5         # Default required link request cost if not explicitly announced or configured
    LINK_STAMP_TIMEOUT          = 15           # Default link request stamp generation timeout
    PR_STAMP_TIMEOUT            = 15           # Default path request stamp generation timeout
    HOP_LIMITER                 = PATHFINDER_M

    STAMPER_PR_QUEUE_LENGTH     = 32           # TODO: Provisional, wire to config
    STAMPER_AN_QUEUE_LENGTH     = 32           # TODO: Provisional, wire to config
    STAMP_PR_PRIORITY           = 0
    STAMP_DST_PRIORITY          = 1
    stamper_thread              = None
    stamper_thread_lock         = Lock()
    stamp_queues                = WorkerQueues((STAMPER_PR_QUEUE_LENGTH, STAMPER_AN_QUEUE_LENGTH))
    pr_stamp_cache              = {}           # Cache of generated path request stamps, keyed on stamp material
    pr_stamp_cache_max          = 256          # Maximum number of cached path request stamps
    pr_stamp_cache_lock         = Lock()

    STATE_UNKNOWN               = 0x00
    STATE_UNRESPONSIVE          = 0x01
    STATE_RESPONSIVE            = 0x02

    LINK_TIMEOUT                = RNS.Link.STALE_TIME * 1.25
    ALLOW_LINK_PATH_REBALANCE   = True
    REVERSE_TIMEOUT             = 8*60         # Reverse table entries are removed after 8 minutes
    PATH_TIMEOUT                = 60*60*24*7   # Path table entry retainment after last cryptographically verifiable liveness event
    UNUSED_PATH_LINGER          = 60*60*1.75   # Linger time for never used paths
    UNUSED_PATH_LINGER_LEAF     = 60*12        # Linger time for never used paths on non-transport instances
    UNUSED_DESTINATION_LINGER   = 60*6         # Linger time for pathless and never used destinations
    PATH_POOL_UNUSED_TARGET     = 2048         # Max unused path table pool target, unused destinations are culled to reach it
    PATH_SLOW_BITRATE           = 25000        # Bitrate threshold for interfaces to be considered slow
    PATH_SLOW_LINGER_FACTOR     = 10           # Linger time multiplier for never used paths on slow interfaces
    TUNNEL_TIMEOUT              = 60*60*8      # Tunnel table entries are removed if unused for eight hours
    TUNNEL_PATH_TIMEOUT         = 60*60*8      # Tunnel path table entries are removed if unused for eight hours
    RATE_TABLE_RETAIN           = 60*60        # Default announce rate table retainment, increased dynamically
    MAX_RECEIPTS                = 1024         # Maximum number of receipts to keep track of
    MAX_RATE_TIMESTAMPS         = 16           # Maximum number of announce timestamps to keep per destination
    PERSIST_RANDOM_BLOBS        = 32           # Maximum number of random blobs per destination to persist to disk
    MAX_RANDOM_BLOBS            = 64           # Maximum number of random blobs per destination to keep in memory
    READY_WAIT                  = 60           # Maximum wait time for inbound packets received before transport core was ready

    interfaces                  = []           # All active interfaces
    destinations                = []           # All active destinations
    destinations_map            = {}           # Destination hash map of active destinations
    pending_links               = []           # Links that are being established
    active_links                = []           # Links that are active
    pending_links_map           = {}           # Link ID hash map of pending links
    active_links_map            = {}           # Link ID hash map of active links
    receipts                    = []           # Receipts of all outgoing packets for proof processing
    packet_hashlist             = PacketHashlist(hash_width=RNS.Identity.HASHLENGTH//8)

    # Notes on memory usage: 1 megabyte of memory can store approximately
    # 55.100 path table entries or approximately 22.300 link table entries.

    announce_table              = {}           # A table for storing announces currently waiting to be retransmitted
    path_table                  = {}           # A lookup table containing the next hop to a given destination
    reverse_table               = {}           # A lookup table for storing packet hashes used to return proofs and replies
    link_table                  = {}           # A lookup table containing hops for links
    held_announces              = {}           # A table containing temporarily held announce-table entries
    announce_handlers           = {}           # A table storing externally registered announce handlers
    pending_callbacks           = []           # A table storing pending callbacks
    tunnels                     = {}           # A table storing tunnels to other transport instances
    path_requests               = {}           # A table for storing path request timestamps
    inflight_path_requests      = {}           # A table for tracking in-flight path request
    path_states                 = {}           # A table for keeping track of path states
    blackholed_identities       = {}           # A table for keeping track of blackholed identities
    blocked_destination_types   = {}           # A table for keeping track of ignored destination types
    allowed_destination_types   = {}           # A table for keeping track of allowed destination types
    client_destination_types    = {}           # A table for keeping track of destination types needed by applications
    destination_type_map        = {}           # Lookup table for destination type names
    required_destinations_only  = False
    announce_rate_table         = AnnounceRateTable(max_timestamps=MAX_RATE_TIMESTAMPS)
    
    discovery_path_requests     = {}           # A table for keeping track of path requests on behalf of other nodes
    discovery_pr_tags           = set()        # A table for keeping track of tagged path requests
    discovery_pr_tags_prev      = set()
    max_pr_tags                 = 16000        # Maximum amount of unique path request tags to remember
    max_queued_discovery_prs    = 32           # Maximum amount of queued discovery path requests
    pr_destination_hash         = None         # Destination hash of the local path request destination

    inbound_queues              = None
    interfaces_lock             = Lock()
    destinations_lock           = Lock()
    destinations_map_lock       = Lock()
    inbound_announce_lock       = Lock()
    announce_table_lock         = Lock()
    announce_rate_table_lock    = Lock()
    announce_handler_lock       = Lock()
    path_table_lock             = Lock()
    reverse_table_lock          = Lock()
    link_table_lock             = Lock()
    active_links_lock           = Lock()
    pending_links_lock          = Lock()
    tunnels_lock                = Lock()
    receipts_lock               = Lock()
    discovery_pr_lock           = Lock()
    discovery_pr_tags_lock      = Lock()
    path_requests_lock          = Lock()
    inflight_path_requests_lock = Lock()
    pending_local_prs_lock      = Lock()
    path_states_lock            = Lock()
    jobs_lock                   = Lock()
    cache_clean_lock            = Lock()
    persist_lock                = Lock()

    # Transport control destinations are used
    # for control purposes like path requests
    control_destinations        = []
    control_hashes              = []
    mgmt_destinations           = []
    mgmt_hashes                 = []
    remote_management_allowed   = []

    # Interfaces for communicating with
    # local clients connected to a shared
    # Reticulum instance
    local_client_interfaces     = []

    local_client_rssi_cache     = []
    local_client_snr_cache      = []
    local_client_q_cache        = []
    local_hops_delta            = 0
    LOCAL_CLIENT_CACHE_MAXSIZE  = 512

    pending_local_path_requests = {}

    ready                       = False
    start_time                  = None
    hashlist_maxsize            = 1000000
    job_interval                = 0.250
    links_last_checked          = 0.0
    links_check_interval        = 1.0
    receipts_last_checked       = 0.0
    receipts_check_interval     = 1.0
    announces_last_checked      = 0.0
    announces_check_interval    = 1.0
    pending_prs_last_checked    = 0.0
    pending_prs_check_interval  = 30.0
    cache_last_cleaned          = 0.0
    cache_clean_interval        = 5*60
    destinations_last_cleaned   = 0.0
    known_destinations_interval = 5*60
    tables_last_culled          = 0.0
    tables_cull_interval        = 5.0
    rate_table_last_culled      = 0.0
    rate_table_cull_interval    = 5.0
    rate_table_cull_chunk       = 1024
    pool_size_last_checked      = 0.0
    pool_size_check_interval    = 5*60
    kd_flush_interval           = 10.0
    announce_cache              = None
    ac_flush_interval           = 15.0
    ac_last_flush               = 0.0
    announce_cache_max_pending  = 10000
    kd_last_flush               = 0.0
    interface_last_jobs         = 0.0
    interface_jobs_interval     = 5.0
    last_mgmt_announce          = 0
    mem_trim_throttle           = 300
    last_mem_trim               = 0
    collect_throttle            = 1440
    last_collect                = 0
    mem_trim_pad                = 0
    mem_trim_gate_mb            = 8
    last_trim_rss_kb            = -1
    mgmt_announce_interval      = 2*60*60
    blackhole_last_checked      = 0
    blackhole_check_interval    = 60
    should_collect              = False
    mem_dirty                   = False
    unused_path_linger          = None
    interface_announcer         = None
    discovery_handler           = None
    blackhole_updater           = None

    traffic_rxb                 = 0
    traffic_txb                 = 0
    announce_rxc                = 0
    announce_txc                = 0
    announce_rxb                = 0
    announce_txb                = 0
    pr_rxc                      = 0
    pr_txc                      = 0
    pr_rxb                      = 0
    pr_txb                      = 0
    speed_rx                    = 0
    speed_tx                    = 0
    announce_speed_rx           = 0
    announce_speed_tx           = 0
    announce_freq_rx            = 0
    announce_freq_tx            = 0
    pr_speed_rx                 = 0
    pr_speed_tx                 = 0
    pr_freq_rx                  = 0
    pr_freq_tx                  = 0
    rx_packets                  = 0
    tx_packets                  = 0
    rx_pps                      = 0
    tx_pps                      = 0
    traffic_captured            = None
    lowest_interface_bitrate    = None
    highest_interface_bitrate   = None

    identity                    = None
    network_identity            = None
    application_identity        = None

    _identity                   = None
    _should_run                 = True
    _unused_path_count_estimate = 0

    @staticmethod
    def internal_identity(): return Transport._identity

    @staticmethod
    def start(reticulum_instance):
        Transport.owner = reticulum_instance

        Transport.INBOUND_DA_QUEUE_LENGTH = RNS.Reticulum.default_data_queue_length()     or Transport.INBOUND_DA_QUEUE_LENGTH
        Transport.INBOUND_AN_QUEUE_LENGTH = RNS.Reticulum.default_announce_queue_length() or Transport.INBOUND_AN_QUEUE_LENGTH
        Transport.INBOUND_PR_QUEUE_LENGTH = RNS.Reticulum.default_pr_queue_length()       or Transport.INBOUND_PR_QUEUE_LENGTH
        Transport.INBOUND_IL_QUEUE_LENGTH = RNS.Reticulum.default_il_queue_length()       or Transport.INBOUND_IL_QUEUE_LENGTH
        Transport.inbound_queues = InboundQueues((Transport.INBOUND_DA_QUEUE_LENGTH,
                                                  Transport.INBOUND_AN_QUEUE_LENGTH,
                                                  Transport.INBOUND_PR_QUEUE_LENGTH,
                                                  Transport.INBOUND_IL_QUEUE_LENGTH))

        if Transport.identity == None:
            transport_identity_path = RNS.Reticulum.storagepath+"/transport_identity"
            if os.path.isfile(transport_identity_path):
                Transport.identity = RNS.Identity.from_file(transport_identity_path)                

            if Transport.identity == None:
                RNS.log("No valid Transport Identity in storage, creating...", RNS.LOG_VERBOSE) if RNS.sl(RNS.LOG_VERBOSE) else None
                Transport.identity = RNS.Identity()
                Transport.identity.to_file(transport_identity_path)
            else:
                RNS.log("Loaded Transport Identity from storage", RNS.LOG_VERBOSE) if RNS.sl(RNS.LOG_VERBOSE) else None

            Transport._identity = Transport.identity
            if not RNS.Reticulum.transport_enabled() and not RNS.Reticulum.static_transport_identity():
                Transport._identity = Transport.identity
                Transport.identity   = RNS.Identity()
                RNS.log(f"Initialized ephemeral transport identity {RNS.prettyhexrep(Transport.identity.hash)}", RNS.LOG_VERBOSE) if RNS.sl(RNS.LOG_VERBOSE) else None

            if RNS.Reticulum.local_hops_delta(): Transport.local_hops_delta = (ord(os.urandom(1))%6)+2

        if Transport.application_identity == None: Transport.application_identity = RNS.Identity()

        if not RNS.Reticulum.transport_enabled() or Transport.owner.is_connected_to_shared_instance:
            Transport.unused_path_linger = Transport.UNUSED_PATH_LINGER_LEAF
        else:
            Transport.unused_path_linger = Transport.UNUSED_PATH_LINGER
        RNS.log(f"Unused path linger time is {RNS.prettytime(Transport.unused_path_linger)}", RNS.LOG_DEBUG)

        packet_hashlist_path = RNS.Reticulum.storagepath+"/packet_hashlist.raw"
        if RNS.Reticulum.transport_enabled() and not Transport.owner.is_connected_to_shared_instance:
            if os.path.isfile(packet_hashlist_path):
                try:
                    with open(packet_hashlist_path, "rb") as file:
                        hashlen = RNS.Identity.HASHLENGTH//8
                        done = False
                        while not done:
                            packet_hash = file.read(hashlen)
                            if len(packet_hash) == hashlen: Transport.packet_hashlist.add(packet_hash)
                            else: done = True

                except Exception as e: RNS.log("Could not load packet hashlist from storage, the contained exception was: "+str(e), RNS.LOG_ERROR)

        Transport.reload_blackhole()

        # Create transport-specific destinations
        Transport.path_request_destination = RNS.Destination(None, RNS.Destination.IN, RNS.Destination.PLAIN, Transport.APP_NAME, "path", "request")
        Transport.path_request_destination.set_packet_callback(Transport.path_request_handler)
        Transport.control_destinations.append(Transport.path_request_destination)
        Transport.control_hashes.append(Transport.path_request_destination.hash)
        Transport.pr_destination_hash = Transport.path_request_destination.hash

        Transport.tunnel_synthesize_destination = RNS.Destination(None, RNS.Destination.IN, RNS.Destination.PLAIN, Transport.APP_NAME, "tunnel", "synthesize")
        Transport.tunnel_synthesize_destination.set_packet_callback(Transport.tunnel_synthesize_handler)
        Transport.control_destinations.append(Transport.tunnel_synthesize_handler)
        Transport.control_hashes.append(Transport.tunnel_synthesize_destination.hash)

        if RNS.Reticulum.remote_management_enabled() and not Transport.owner.is_connected_to_shared_instance:
            Transport.remote_management_destination = RNS.Destination(Transport.identity, RNS.Destination.IN, RNS.Destination.SINGLE, Transport.APP_NAME, "remote", "management")
            Transport.remote_management_destination.register_request_handler("/status", response_generator = Transport.remote_status_handler, allow = RNS.Destination.ALLOW_LIST, allowed_list=Transport.remote_management_allowed)
            Transport.remote_management_destination.register_request_handler("/path", response_generator = Transport.remote_path_handler, allow = RNS.Destination.ALLOW_LIST, allowed_list=Transport.remote_management_allowed)
            Transport.mgmt_destinations.append(Transport.remote_management_destination)
            Transport.mgmt_hashes.append(Transport.remote_management_destination.hash)
            RNS.log("Enabled remote management on "+str(Transport.remote_management_destination), RNS.LOG_NOTICE)

        if RNS.Reticulum.publish_blackhole_enabled() and not Transport.owner.is_connected_to_shared_instance:
            Transport.blackhole_destination = RNS.Destination(Transport.identity, RNS.Destination.IN, RNS.Destination.SINGLE, Transport.APP_NAME, "info", "blackhole")
            Transport.blackhole_destination.set_link_cost(5.25)
            Transport.blackhole_destination.register_request_handler("/list", response_generator = Transport.blackhole_list_handler, allow=RNS.Destination.ALLOW_ALL)
            Transport.mgmt_destinations.append(Transport.blackhole_destination)
            Transport.mgmt_hashes.append(Transport.blackhole_destination.hash)
            RNS.log(f"Enabled blackhole list publishing for transport identity {RNS.prettyhexrep(Transport.identity.hash)}", RNS.LOG_NOTICE)

        if Transport.network_identity and not Transport.owner.is_connected_to_shared_instance:
            Transport.instance_destination = RNS.Destination(Transport.network_identity, RNS.Destination.IN, RNS.Destination.SINGLE, Transport.APP_NAME, "network", "instance", RNS.hexrep(Transport.network_identity.hash, delimit=False))
            Transport.network_destination  = RNS.Destination(Transport.network_identity, RNS.Destination.IN, RNS.Destination.SINGLE, Transport.APP_NAME, "network")
            Transport.mgmt_destinations.append(Transport.instance_destination)
            Transport.mgmt_destinations.append(Transport.network_destination)
            Transport.mgmt_hashes.append(Transport.instance_destination)
            Transport.mgmt_hashes.append(Transport.network_destination)

        # Defer cleaning packet cache for 60 seconds
        Transport.cache_last_cleaned = time.time() + 60
        
        # Defer cleaning known destinations
        Transport.destinations_last_cleaned = time.time()

        # Defer path table unused pool cull
        Transport.pool_size_last_checked = time.time()

        # Defer memory trim
        Transport.last_collect  = time.time()
        Transport.last_mem_trim = time.time()

        # Defer sending management announces for 15 seconds
        Transport.last_mgmt_announce = time.time() - Transport.mgmt_announce_interval + 15
        
        # Start job loops
        threading.Thread(target=Transport.jobloop, daemon=True).start()
        threading.Thread(target=Transport.count_traffic_loop, daemon=True).start()

        # Load transport-related data
        if not Transport.owner.is_connected_to_shared_instance: Transport.init_announce_cache()

        if Transport.HOP_LIMITER != Transport.PATHFINDER_M: RNS.log(f"Transport hop limit set to {Transport.HOP_LIMITER}", RNS.LOG_VERBOSE)

        if RNS.Reticulum.transport_enabled():
            path_table_path = RNS.Reticulum.storagepath+"/destination_table"
            tunnel_table_path = RNS.Reticulum.storagepath+"/tunnels"

            if os.path.isfile(path_table_path) and not Transport.owner.is_connected_to_shared_instance:
                serialised_destinations = []
                try:
                    file = open(path_table_path, "rb")
                    serialised_destinations = umsgpack.unpackb(file.read())
                    file.close()

                    now = time.time()
                    for serialised_entry in serialised_destinations:
                        destination_hash = serialised_entry[0]

                        if len(destination_hash) == RNS.Reticulum.TRUNCATED_HASHLENGTH//8:
                            timestamp = serialised_entry[1]
                            received_from = serialised_entry[2]
                            hops = serialised_entry[3]
                            expires = serialised_entry[4]
                            random_blobs = serialised_entry[5]
                            receiving_interface = Transport.find_interface_from_hash(serialised_entry[6])
                            announce_packet = Transport.get_cached_packet(serialised_entry[7], packet_type="announce")
                            used = serialised_entry[8] if len(serialised_entry) > 8 else now
                            blackholed = False

                            if len(Transport.blackholed_identities) > 0:
                                path_identity = RNS.Identity.recall(destination_hash, _no_use=True)
                                if path_identity in Transport.blackholed_identities: blackholed = True
                                del path_identity

                            if announce_packet != None and receiving_interface != None and blackholed == False:
                                if not announce_packet.unpack(): continue
                                # We increase the hops, since reading a packet
                                # from cache is equivalent to receiving it again
                                # over an interface. It is cached with it's non-
                                # increased hop-count.
                                announce_packet.hops += 1
                                with Transport.path_table_lock:
                                    Transport.path_table[destination_hash] = [timestamp, received_from, hops, expires,
                                                                              random_blobs, receiving_interface,
                                                                              announce_packet.packet_hash, used]

                                RNS.log(f"Loaded path table entry for {RNS.prettyhexrep(destination_hash)} from storage", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                            else:
                                RNS.log(f"Could not reconstruct path table entry from storage for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                if announce_packet == None:     RNS.log("The announce packet could not be loaded from cache", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                if receiving_interface == None: RNS.log("The interface is no longer available", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                if blackholed:                  RNS.log("The associated identity is blackholed", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None

                    if len(Transport.path_table) == 1: specifier = "entry"
                    else:                              specifier = "entries"

                    RNS.log("Loaded "+str(len(Transport.path_table))+" path table "+specifier+" from storage", RNS.LOG_VERBOSE) if RNS.sl(RNS.LOG_VERBOSE) else None
                    garbage_collect()

                except Exception as e:
                    RNS.log("Could not load destination table from storage, the contained exception was: "+str(e), RNS.LOG_ERROR)
                    garbage_collect()

            if os.path.isfile(tunnel_table_path) and not Transport.owner.is_connected_to_shared_instance:
                serialised_tunnels = []
                try:
                    file = open(tunnel_table_path, "rb")
                    serialised_tunnels = umsgpack.unpackb(file.read())
                    file.close()

                    now = time.time()
                    for serialised_tunnel in serialised_tunnels:
                        tunnel_id = serialised_tunnel[IDX_TT_TUNNEL_ID]
                        interface_hash = serialised_tunnel[IDX_TT_IF]
                        serialised_paths = serialised_tunnel[IDX_TT_PATHS]
                        expires = serialised_tunnel[IDX_TT_EXPIRES]

                        tunnel_paths = {}
                        for serialised_entry in serialised_paths:
                            destination_hash = serialised_entry[0]
                            timestamp = serialised_entry[1]
                            received_from = serialised_entry[2]
                            hops = serialised_entry[3]
                            path_expires = serialised_entry[4]
                            random_blobs = list(set(serialised_entry[5]))
                            receiving_interface = Transport.find_interface_from_hash(serialised_entry[6])
                            announce_packet = Transport.get_cached_packet(serialised_entry[7], packet_type="announce")
                            used = serialised_entry[8] if len(serialised_entry) > 8 else now

                            if announce_packet != None:
                                if not announce_packet.unpack(): continue
                                # We increase the hops, since reading a packet
                                # from cache is equivalent to receiving it again
                                # over an interface. It is cached with it's non-
                                # increased hop-count.
                                announce_packet.hops += 1

                                tunnel_path = [timestamp, received_from, hops, path_expires, random_blobs, receiving_interface, announce_packet.packet_hash, used]
                                tunnel_paths[destination_hash] = tunnel_path

                        if len(tunnel_paths) > 0:
                            tunnel = [tunnel_id, None, tunnel_paths, expires]
                            with Transport.tunnels_lock: Transport.tunnels[tunnel_id] = tunnel

                    if len(Transport.tunnels) == 1: specifier = "entry"
                    else:                           specifier = "entries"

                    RNS.log("Loaded "+str(len(Transport.tunnels))+" tunnel table "+specifier+" from storage", RNS.LOG_VERBOSE) if RNS.sl(RNS.LOG_VERBOSE) else None
                    garbage_collect()

                except Exception as e:
                    RNS.log("Could not load tunnel table from storage, the contained exception was: "+str(e), RNS.LOG_ERROR)
                    garbage_collect()

            if RNS.Reticulum.probe_destination_enabled():
                Transport.probe_destination = RNS.Destination(Transport.identity, RNS.Destination.IN, RNS.Destination.SINGLE, Transport.APP_NAME, "probe")
                Transport.probe_destination.accepts_links(False)
                Transport.probe_destination.set_proof_strategy(RNS.Destination.PROVE_ALL)
                Transport.mgmt_destinations.append(Transport.probe_destination)
                RNS.log("Transport Instance will respond to probe requests on "+str(Transport.probe_destination), RNS.LOG_NOTICE)
            else:
                Transport.probe_destination = None

            RNS.log("Transport instance "+str(Transport.identity)+" started", RNS.LOG_VERBOSE) if RNS.sl(RNS.LOG_VERBOSE) else None
        Transport.start_time = time.time()

        # Sort interfaces according to bitrate
        Transport.prioritize_interfaces()

        # Spawn queue workers
        for n in range(Transport.TRANSPORT_WORKERS):
            if Transport.USE_INBOUND_QUEUE:  threading.Thread(target=Transport.inbound_job,  daemon=True).start()
            if Transport.USE_OUTBOUND_QUEUE: threading.Thread(target=Transport.outbound_job, daemon=True).start()

        # Spawn the stamp worker
        Transport.ensure_stamper()

        Transport.ready = True

        # Synthesize tunnels for any interfaces wanting it
        for interface in Transport.interfaces:
            interface.tunnel_id = None
            if hasattr(interface, "wants_tunnel") and interface.wants_tunnel:
                Transport.synthesize_tunnel(interface)

        garbage_collect()

    @staticmethod
    def add_interface(interface):
        with Transport.interfaces_lock:
            if not interface in Transport.interfaces:
                Transport.interfaces.append(interface)
                if interface.announce_rate_target and interface.announce_rate_target > Transport.RATE_TABLE_RETAIN:
                    Transport.RATE_TABLE_RETAIN = interface.announce_rate_target
                    RNS.log(f"Increased announce rate table retainment time to {RNS.prettytime(Transport.RATE_TABLE_RETAIN)}", RNS.LOG_DEBUG)

    @staticmethod
    def remove_interface(interface):
        with Transport.interfaces_lock:
            if interface in Transport.interfaces:
                Transport.interfaces.remove(interface)

    @staticmethod
    def set_network_identity(identity):
        if not Transport.network_identity:
            Transport.network_identity = identity

    @staticmethod
    def has_network_identity():
        if Transport.network_identity: return True
        else:                          return False

    @staticmethod
    def prioritize_interfaces():
        with Transport.interfaces_lock:
            try: Transport.interfaces.sort(key=lambda interface: interface.bitrate, reverse=True)
            except Exception as e: RNS.log(f"Could not prioritize interfaces according to bitrate. The contained exception was: {e}", RNS.LOG_ERROR)
            try: Transport.lowest_interface_bitrate = min((interface.bitrate for interface in Transport.interfaces if interface.online and interface.bitrate))
            except Exception as e: RNS.log(f"Could not get lowest interface bitrate. The contained exception was: {e}", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
            try: Transport.highest_interface_bitrate = max((interface.bitrate for interface in Transport.interfaces if interface.online and interface.bitrate))
            except Exception as e: RNS.log(f"Could not get highest interface bitrate. The contained exception was: {e}", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

    @staticmethod
    def enable_discovery():
        if not Transport.interface_announcer:
            Transport.interface_announcer = RNS.Discovery.InterfaceAnnouncer(Transport)
            Transport.interface_announcer.start()

    @staticmethod
    def discover_interfaces():
        if not Transport.discovery_handler:
            Transport.discovery_handler = RNS.Discovery.InterfaceDiscovery(required_value=RNS.Reticulum.required_discovery_value(), discover_interfaces=True)

    @staticmethod
    def enable_blackhole_updater():
        if not Transport.blackhole_updater:
            Transport.blackhole_updater = RNS.Discovery.BlackholeUpdater()
            Transport.blackhole_updater.start()

    @staticmethod
    def count_traffic_loop():
        rxp = 0; txp = 0; cts = None

        while True:
            time.sleep(1)
            try:
                rxb  = 0; txb  = 0; rxs  = 0; txs  = 0;
                arxb = 0; atxb = 0; arxs = 0; atxs = 0;
                prxb = 0; ptxb = 0; prxs = 0; ptxs = 0;
                iafreq = 0; oafreq = 0; ipfreq = 0; opfreq = 0

                for interface in Transport.interfaces:
                    if not hasattr(interface, "parent_interface") or interface.parent_interface == None:
                        if hasattr(interface, "is_local_shared_instance"): continue
                        if hasattr(interface, "transport_traffic_counter"):
                            now = time.time()

                            irxb  = interface.rxb;  itxb  = interface.txb
                            iarxb = interface.arxb; iatxb = interface.atxb
                            iprxb = interface.prxb; iptxb = interface.ptxb

                            tc = interface.transport_traffic_counter
                            ts_diff = now  - tc["ts"]

                            rx_diff  = irxb - tc["rxb"];   tx_diff  = itxb - tc["txb"]
                            arx_diff = iarxb - tc["arxb"]; atx_diff = iatxb - tc["atxb"]
                            prx_diff = iprxb - tc["prxb"]; ptx_diff = iptxb - tc["ptxb"]

                            rxb    += rx_diff;  crxs  = (rx_diff*8)/ts_diff
                            txb    += tx_diff;  ctxs  = (tx_diff*8)/ts_diff
                            arxb   += arx_diff; carxs = (arx_diff*8)/ts_diff
                            atxb   += atx_diff; catxs = (atx_diff*8)/ts_diff
                            prxb   += prx_diff; cprxs = (prx_diff*8)/ts_diff
                            ptxb   += ptx_diff; cptxs = (ptx_diff*8)/ts_diff

                            iafreq += interface.incoming_announce_frequency()
                            oafreq += interface.outgoing_announce_frequency()
                            ipfreq += interface.incoming_pr_frequency()
                            opfreq += interface.outgoing_pr_frequency()

                            interface.current_rx_speed  = crxs;  rxs  += crxs
                            interface.current_tx_speed  = ctxs;  txs  += ctxs
                            interface.current_arx_speed = carxs; arxs += carxs
                            interface.current_atx_speed = catxs; atxs += catxs
                            interface.current_prx_speed = cprxs; prxs += cprxs
                            interface.current_ptx_speed = cptxs; ptxs += cptxs
                            
                            tc["ts"]   = now
                            tc["rxb"]  = irxb;  tc["txb"]  = itxb
                            tc["arxb"] = iarxb; tc["atxb"] = iatxb
                            tc["prxb"] = iprxb; tc["ptxb"] = iptxb

                        else:
                            interface.transport_traffic_counter = { "ts": time.time(), "rxb": interface.rxb, "txb": interface.txb,
                                                                    "arxb": interface.arxb, "atxb": interface.atxb,
                                                                    "prxb": interface.prxb, "ptxb": interface.ptxb }
                if not Transport.start_time: rpps = 0; tpps = 0
                else:
                    if not cts: ts = Transport.start_time
                    else:       ts = cts
                    cts  = time.time(); td = cts - ts
                    rpps = (Transport.rx_packets - rxp) / td
                    tpps = (Transport.tx_packets - txp) / td
                    rxp  = Transport.rx_packets
                    txp  = Transport.tx_packets

                Transport.rx_pps             = int(round(rpps))
                Transport.tx_pps             = int(round(tpps))
                Transport.traffic_rxb       += rxb
                Transport.traffic_txb       += txb
                Transport.speed_rx           = rxs
                Transport.speed_tx           = txs
                Transport.announce_rxb      += arxb
                Transport.announce_txb      += atxb
                Transport.announce_speed_rx  = arxs
                Transport.announce_speed_tx  = atxs
                Transport.announce_freq_rx   = iafreq
                Transport.announce_freq_tx   = oafreq
                Transport.pr_rxb            += prxb
                Transport.pr_txb            += ptxb
                Transport.pr_speed_rx        = prxs
                Transport.pr_speed_tx        = ptxs
                Transport.pr_freq_rx         = ipfreq
                Transport.pr_freq_tx         = opfreq
            
            except Exception as e: RNS.log(f"An error occurred while counting interface traffic: {e}", RNS.LOG_ERROR)

    ##################
    # Transport Jobs #
    ##################

    @staticmethod
    def jobloop():
        while (Transport._should_run):
            Transport.jobs()
            sleep(Transport.job_interval)

    @staticmethod
    def jobs():
        outgoing = []
        path_requests = {}
        blocked_if = None

        try:
            with Transport.jobs_lock:
                # Process active and pending link lists
                if time.time() > Transport.links_last_checked+Transport.links_check_interval:

                    with Transport.pending_links_lock:
                        closed_pending_links = []
                        for link in Transport.pending_links:
                            if link.status == RNS.Link.CLOSED:
                                # If we are not a Transport Instance, finding a pending link
                                # that was never activated will trigger an expiry of the path
                                # to the destination, and an attempt to rediscover the path.
                                if not RNS.Reticulum.transport_enabled():
                                    Transport.expire_path(link.destination.hash)

                                    # If we are connected to a shared instance, it will take
                                    # care of sending out a new path request. If not, we will
                                    # send one directly.
                                    if not Transport.owner.is_connected_to_shared_instance:
                                        last_path_request = 0
                                        with Transport.path_requests_lock:
                                            if link.destination.hash in Transport.path_requests:
                                                last_path_request = Transport.path_requests[link.destination.hash]

                                        if time.time() - last_path_request > Transport.PATH_REQUEST_MI:
                                            RNS.log("Trying to rediscover path for "+RNS.prettyhexrep(link.destination.hash)+" since an attempted link was never established", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                            if not link.destination.hash in path_requests:
                                                blocked_if = None
                                                path_requests[link.destination.hash] = blocked_if

                                closed_pending_links.append(link)

                        for closed_link in closed_pending_links:
                            Transport.pending_links.remove(closed_link)
                            Transport.pending_links_map.pop(closed_link.link_id, None)

                    with Transport.active_links_lock:
                        closed_links = []
                        for link in Transport.active_links:
                            if link.status == RNS.Link.CLOSED: closed_links.append(link)

                        for closed_link in closed_links:
                            Transport.active_links.remove(closed_link)
                            Transport.active_links_map.pop(closed_link.link_id, None)

                    Transport.links_last_checked = time.time()

                # Process receipts list for timed-out packets
                if time.time() > Transport.receipts_last_checked+Transport.receipts_check_interval:
                    # TODO: The pop(0) is expensive under the lock.
                    # Could improve contention via an initial reverse(),
                    # then pop() trick or similar.
                    with Transport.receipts_lock:
                        while len(Transport.receipts) > Transport.MAX_RECEIPTS:
                            culled_receipt = Transport.receipts.pop(0)
                            culled_receipt.timeout = -1
                            culled_receipt.check_timeout()
                            Transport.should_collect = True

                    # TODO: Actually, this whole thing might need re-
                    # thinking a bit, but may require moving receipts
                    # to a dict or something else entirely.
                    with Transport.receipts_lock:
                        expired_receipts = []
                        for receipt in Transport.receipts:
                            receipt.check_timeout()
                            if receipt.status != RNS.PacketReceipt.SENT: expired_receipts.append(receipt)

                        for expired_receipt in expired_receipts:
                            if expired_receipt in Transport.receipts: Transport.receipts.remove(expired_receipt)

                    Transport.receipts_last_checked = time.time()

                # Process announces needing retransmission
                if time.time() > Transport.announces_last_checked+Transport.announces_check_interval:
                    completed_announces = []
                    
                    with Transport.announce_table_lock:
                        for destination_hash in Transport.announce_table:
                            announce_entry = Transport.announce_table[destination_hash]
                            if announce_entry[IDX_AT_RETRIES] > 0 and announce_entry[IDX_AT_RETRIES] >= Transport.LOCAL_REBROADCASTS_MAX:
                                RNS.log("Completed announce processing for "+RNS.prettyhexrep(destination_hash)+", local rebroadcast limit reached", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                                completed_announces.append(destination_hash)
                            elif announce_entry[IDX_AT_RETRIES] > Transport.PATHFINDER_R:
                                RNS.log("Completed announce processing for "+RNS.prettyhexrep(destination_hash)+", retry limit reached", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                                completed_announces.append(destination_hash)
                            else:
                                if time.time() > announce_entry[IDX_AT_RTRNS_TMO]:
                                    announce_entry[IDX_AT_RTRNS_TMO] = time.time() + Transport.PATHFINDER_G + Transport.PATHFINDER_RW
                                    announce_entry[IDX_AT_RETRIES] += 1
                                    packet = announce_entry[IDX_AT_PACKET]
                                    block_rebroadcasts = announce_entry[IDX_AT_BLCK_RBRD]
                                    attached_interface = announce_entry[IDX_AT_ATTCHD_IF]
                                    announce_context = RNS.Packet.NONE
                                    if block_rebroadcasts: announce_context = RNS.Packet.PATH_RESPONSE
                                    announce_data = packet.data
                                    announce_identity = RNS.Identity.recall(packet.destination_hash, _no_use=True)
                                    if not announce_identity:
                                        RNS.log("Completed announce processing for "+RNS.prettyhexrep(destination_hash)+", the path was cleaned while waiting for announce rebroadcast", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                        completed_announces.append(destination_hash)

                                    else:
                                        announce_destination = RNS.Destination(announce_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "unknown", "unknown");
                                        announce_destination.hash = packet.destination_hash
                                        announce_destination.hexhash = announce_destination.hash.hex()
                                        
                                        new_packet = RNS.Packet(announce_destination,
                                                                announce_data,
                                                                RNS.Packet.ANNOUNCE,
                                                                context = announce_context,
                                                                header_type = RNS.Packet.HEADER_2,
                                                                transport_type = Transport.TRANSPORT,
                                                                transport_id = Transport.identity.hash,
                                                                attached_interface = attached_interface,
                                                                context_flag = packet.context_flag)

                                        new_packet.hops = announce_entry[4]
                                        if block_rebroadcasts: RNS.log("Rebroadcasting announce as path response for "+RNS.prettyhexrep(announce_destination.hash)+" with hop count "+str(new_packet.hops), RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                        else: RNS.log("Rebroadcasting announce for "+RNS.prettyhexrep(announce_destination.hash)+" with hop count "+str(new_packet.hops), RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                        
                                        outgoing.append(new_packet)

                                        # This handles an edge case where a peer sends a path
                                        # request for a destination just after an announce for
                                        # said destination has arrived, but before it has been
                                        # rebroadcast locally. In such a case the actual announce
                                        # is temporarily held, and then reinserted when the path
                                        # request has been served to the peer.
                                        if destination_hash in Transport.held_announces:
                                            held_entry = Transport.held_announces.pop(destination_hash)
                                            Transport.announce_table[destination_hash] = held_entry
                                            RNS.log("Reinserting held announce into table", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None

                        for destination_hash in completed_announces:
                            if destination_hash in Transport.announce_table: Transport.announce_table.pop(destination_hash)

                    Transport.announces_last_checked = time.time()


                # Swap the packet hashlist generations if it has reached its max size
                if len(Transport.packet_hashlist) > Transport.hashlist_maxsize//2:
                    Transport.packet_hashlist.swap()

                # Cull invalidated path requests
                if time.time() > Transport.pending_prs_last_checked+Transport.pending_prs_check_interval:
                    stale_local_prs = []
                    with Transport.pending_local_prs_lock:
                        for destination_hash in Transport.pending_local_path_requests:
                            if not Transport.pending_local_path_requests[destination_hash] in Transport.interfaces:
                                stale_local_prs.append(destination_hash)
                        
                        for destination_hash in stale_local_prs:
                            Transport.pending_local_path_requests.pop(destination_hash)

                    Transport.pending_prs_last_checked = time.time()

                # Cull the path request tags list if it has reached its max size
                if len(Transport.discovery_pr_tags) > Transport.max_pr_tags:
                    with Transport.discovery_pr_tags_lock:
                        Transport.discovery_pr_tags_prev = Transport.discovery_pr_tags
                        Transport.discovery_pr_tags = set()

                # Incrementally cull stale announce rate table entries
                if time.time() > Transport.rate_table_last_culled+Transport.rate_table_cull_interval:
                    with Transport.announce_rate_table_lock:
                        Transport.announce_rate_table.cull(time.time(), Transport.RATE_TABLE_RETAIN,
                                                           Transport.rate_table_cull_chunk, Transport.rate_table_cull_chunk)

                    Transport.rate_table_last_culled = time.time()

                # Flush pending known destinations to storage
                if RNS.Identity.known_destinations_store != None and time.time() > Transport.kd_last_flush+Transport.kd_flush_interval:
                    Transport.kd_last_flush = time.time()
                    RNS.Identity.flush_known_destinations()

                # Flush pending cached announces to storage
                if Transport.announce_cache != None and (time.time() > Transport.ac_last_flush+Transport.ac_flush_interval or Transport.announce_cache.pending_count() > Transport.announce_cache_max_pending):
                    Transport.ac_last_flush = time.time()
                    Transport.announce_cache.flush()

                if time.time() > Transport.tables_last_culled + Transport.tables_cull_interval:
                    # Remove unneeded path state entries
                    stale_path_states = []
                    with Transport.path_states_lock:
                        for destination_hash in Transport.path_states:
                            if not destination_hash in Transport.path_table:
                                stale_path_states.append(destination_hash)

                    # Cull the reverse table according to timeout
                    stale_reverse_entries = []
                    with Transport.reverse_table_lock:
                        for truncated_packet_hash in Transport.reverse_table:
                            reverse_entry = Transport.reverse_table[truncated_packet_hash]
                            if time.time() > reverse_entry[IDX_RT_TIMESTAMP] + Transport.REVERSE_TIMEOUT: stale_reverse_entries.append(truncated_packet_hash)
                            elif not reverse_entry[IDX_RT_OUTB_IF] in Transport.interfaces:               stale_reverse_entries.append(truncated_packet_hash)
                            elif not reverse_entry[IDX_RT_RCVD_IF] in Transport.interfaces:               stale_reverse_entries.append(truncated_packet_hash)

                    # Cull the link table according to timeout
                    stale_links = []
                    with Transport.link_table_lock:
                        for link_id in Transport.link_table:
                            link_entry = Transport.link_table[link_id]

                            if link_entry[IDX_LT_VALIDATED] == True:
                                if time.time() > link_entry[IDX_LT_TIMESTAMP] + Transport.LINK_TIMEOUT: stale_links.append(link_id)
                                elif not link_entry[IDX_LT_NH_IF] in Transport.interfaces:              stale_links.append(link_id)
                                elif not link_entry[IDX_LT_RCVD_IF] in Transport.interfaces:            stale_links.append(link_id)
                            
                            else:
                                if time.time() > link_entry[IDX_LT_PROOF_TMO]:
                                    stale_links.append(link_id)
                                    blocked_if = None

                                    last_path_request = 0
                                    with Transport.path_requests_lock:
                                        if link_entry[IDX_LT_DSTHASH] in Transport.path_requests:
                                            last_path_request = Transport.path_requests[link_entry[IDX_LT_DSTHASH]]

                                    lr_taken_hops = link_entry[IDX_LT_HOPS]

                                    path_request_throttle = time.time() - last_path_request < Transport.PATH_REQUEST_MI
                                    path_request_conditions = False
                                    
                                    # If the path has been invalidated between the time of
                                    # making the link request and now, try to rediscover it
                                    if not Transport.has_path(link_entry[IDX_LT_DSTHASH]):
                                        RNS.log("Trying to rediscover path for "+RNS.prettyhexrep(link_entry[IDX_LT_DSTHASH])+" since an attempted link was never established, and path is now missing", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                        path_request_conditions = True

                                    # If this link request was originated from a local client
                                    # attempt to rediscover a path to the destination, if this
                                    # has not already happened recently.
                                    elif not path_request_throttle and lr_taken_hops == 0:
                                        RNS.log("Trying to rediscover path for "+RNS.prettyhexrep(link_entry[IDX_LT_DSTHASH])+" since an attempted local client link was never established", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                        path_request_conditions = True

                                    # If the link destination was previously only 1 hop
                                    # away, this likely means that it was local to one
                                    # of our interfaces, and that it roamed somewhere else.
                                    # In that case, try to discover a new path, and mark
                                    # the old one as unresponsive.
                                    elif not path_request_throttle and Transport.hops_to(link_entry[IDX_LT_DSTHASH]) == 1:
                                        RNS.log("Trying to rediscover path for "+RNS.prettyhexrep(link_entry[IDX_LT_DSTHASH])+" since an attempted link was never established, and destination was previously local to an interface on this instance", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                        path_request_conditions = True
                                        blocked_if = link_entry[IDX_LT_RCVD_IF]

                                        # TODO: This might result in the path re-resolution
                                        # only being able to happen once, since new path found
                                        # after allowing update from higher hop-count path, after
                                        # marking old path unresponsive, might be more than 1 hop away,
                                        # thus dealocking us into waiting for a new announce all-together.
                                        # Is this problematic, or does it actually not matter?
                                        # Best would be to have full support for alternative paths,
                                        # and score them according to number of unsuccessful tries or
                                        # similar.
                                        if RNS.Reticulum.transport_enabled():
                                            if hasattr(link_entry[IDX_LT_RCVD_IF], "mode") and link_entry[IDX_LT_RCVD_IF].mode != RNS.Interfaces.Interface.Interface.MODE_BOUNDARY:
                                                Transport.mark_path_unresponsive(link_entry[IDX_LT_DSTHASH])

                                    # If the link initiator is only 1 hop away,
                                    # this likely means that network topology has
                                    # changed. In that case, we try to discover a new path,
                                    # and mark the old one as potentially unresponsive.
                                    elif not path_request_throttle and lr_taken_hops == 1:
                                        RNS.log("Trying to rediscover path for "+RNS.prettyhexrep(link_entry[IDX_LT_DSTHASH])+" since an attempted link was never established, and link initiator is local to an interface on this instance", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                        path_request_conditions = True
                                        blocked_if = link_entry[IDX_LT_RCVD_IF]

                                        if RNS.Reticulum.transport_enabled():
                                            if hasattr(link_entry[IDX_LT_RCVD_IF], "mode") and link_entry[IDX_LT_RCVD_IF].mode != RNS.Interfaces.Interface.Interface.MODE_BOUNDARY:
                                                Transport.mark_path_unresponsive(link_entry[IDX_LT_DSTHASH])

                                    if path_request_conditions:
                                        with Transport.path_requests_lock:
                                            if not link_entry[IDX_LT_DSTHASH] in path_requests:
                                                path_requests[link_entry[IDX_LT_DSTHASH]] = blocked_if

                                        if not RNS.Reticulum.transport_enabled():
                                            # Drop current path if we are not a transport instance, to
                                            # allow using higher-hop count paths or reused announces
                                            # from newly adjacent transport instances.
                                            Transport.expire_path(link_entry[IDX_LT_DSTHASH])

                    # Cull the path table
                    stale_paths = []
                    with Transport.path_table_lock:
                        now = time.time()
                        check_unused = now > Transport.pool_size_last_checked+Transport.pool_size_check_interval
                        unused_paths = []

                        for destination_hash in Transport.path_table:
                            path_entry         = Transport.path_table[destination_hash]
                            attached_interface = path_entry[IDX_PT_RVCD_IF]
                            path_timestamp     = path_entry[IDX_PT_TIMESTAMP]
                            path_expiry        = path_entry[IDX_PT_EXPIRES]
                            path_used          = path_entry[IDX_PT_USED]

                            interface_bitrate  = getattr(attached_interface, "bitrate", None)
                            slow_interface     = interface_bitrate != None and 0 < interface_bitrate < Transport.PATH_SLOW_BITRATE

                            if check_unused and not path_used:
                                unused_paths.append(((1 if slow_interface else 0), path_expiry, destination_hash))

                            if now > path_expiry:
                                stale_paths.append(destination_hash)
                                Transport.should_collect = True
                                RNS.log(f"Path to {RNS.prettyhexrep(destination_hash)} timed out and was removed", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                            elif not attached_interface in Transport.interfaces:
                                stale_paths.append(destination_hash)
                                Transport.should_collect = True
                                RNS.log(f"Path to {RNS.prettyhexrep(destination_hash)} was removed since the attached interface no longer exists", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                            elif path_used == 0 and now > path_timestamp + (Transport.unused_path_linger * (Transport.PATH_SLOW_LINGER_FACTOR if slow_interface else 1)):
                                stale_paths.append(destination_hash)
                                Transport.should_collect = True
                                RNS.log(f"Removing never used path to {RNS.prettyhexrep(destination_hash)}", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None

                        if len(unused_paths) > Transport.PATH_POOL_UNUSED_TARGET:
                            cull_count = len(unused_paths) - Transport.PATH_POOL_UNUSED_TARGET
                            RNS.log(f"Culling {cull_count} never used path table entries to reach pool size target {Transport.PATH_POOL_UNUSED_TARGET}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                            unused_paths.sort()
                            for cull_entry in unused_paths[:cull_count]:
                                stale_paths.append(cull_entry[2])

                        if check_unused:
                            Transport._unused_path_count_estimate = len(unused_paths)
                            Transport.pool_size_last_checked = time.time()

                    # Cull the pending path requests table
                    stale_path_requests = []
                    try:
                        path_requests_snapshot = Transport.path_requests.copy()
                        for destination_hash in path_requests_snapshot:
                            if time.time() > path_requests_snapshot[destination_hash] + Transport.PATH_REQUEST_GATE_TIMEOUT:
                                stale_path_requests.append(destination_hash)
                                RNS.log("Path request entry for "+RNS.prettyhexrep(destination_hash)+" timed out and was removed", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                    except Exception as e:
                        RNS.log(f"Could not complete stale path request enumeration in this job round, retrying later: {e}", RNS.LOG_WARNING)

                    # Cull the pending in-flight path requests table
                    stale_inflight_path_requests = []
                    try:
                        inflight_path_requests_snapshot = Transport.inflight_path_requests.copy()
                        for destination_hash in inflight_path_requests_snapshot:
                            if time.time() > inflight_path_requests_snapshot[destination_hash] + Transport.PATH_REQUEST_GATE_TIMEOUT:
                                stale_inflight_path_requests.append(destination_hash)
                                RNS.log("In-flight path request entry for "+RNS.prettyhexrep(destination_hash)+" timed out and was removed", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                    except Exception as e:
                        RNS.log(f"Could not complete stale in-flight path request enumeration in this job round, retrying later: {e}", RNS.LOG_WARNING)

                    # Cull the pending discovery path requests table
                    stale_discovery_path_requests = []
                    with Transport.discovery_pr_lock:
                        for destination_hash in Transport.discovery_path_requests:
                            entry = Transport.discovery_path_requests[destination_hash]

                            if time.time() > entry["timeout"]:
                                stale_discovery_path_requests.append(destination_hash)
                                Transport.should_collect = True
                                RNS.log("Waiting path request for "+RNS.prettyhexrep(destination_hash)+" timed out and was removed", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                    # Cull the tunnel table
                    stale_tunnels = []; ti = 0
                    with Transport.tunnels_lock:
                        for tunnel_id in Transport.tunnels:
                            tunnel_entry = Transport.tunnels[tunnel_id]

                            expires = tunnel_entry[IDX_TT_EXPIRES]
                            if expires > time.time() + Transport.TUNNEL_TIMEOUT*2:
                                stale_tunnels.append(tunnel_id); Transport.should_collect = True
                                RNS.log("Tunnel "+RNS.prettyhexrep(tunnel_id)+" with excessive expiry was removed", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                            elif time.time() > expires:
                                stale_tunnels.append(tunnel_id); Transport.should_collect = True
                                RNS.log("Tunnel "+RNS.prettyhexrep(tunnel_id)+" timed out and was removed", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                            
                            else:
                                if tunnel_entry[IDX_TT_IF] and not tunnel_entry[IDX_TT_IF] in Transport.interfaces:
                                    RNS.log(f"Removing non-existent tunnel interface {tunnel_entry[IDX_TT_IF]}", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                                    tunnel_entry[IDX_TT_IF] = None

                                stale_tunnel_paths = []
                                tunnel_paths = tunnel_entry[IDX_TT_PATHS]
                                for tunnel_path in tunnel_paths:
                                    tunnel_path_entry = tunnel_paths[tunnel_path]

                                    if time.time() > tunnel_path_entry[0] + Transport.TUNNEL_PATH_TIMEOUT:
                                        stale_tunnel_paths.append(tunnel_path); Transport.should_collect = True
                                        RNS.log("Tunnel path to "+RNS.prettyhexrep(tunnel_path)+" timed out and was removed", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                                    else:
                                        active_path = None
                                        with Transport.path_table_lock:
                                            if tunnel_path in Transport.path_table: active_path = Transport.path_table[tunnel_path]
                                        
                                        if active_path:
                                            random_blobs             = tunnel_path_entry[4]
                                            current_random_blobs     = active_path[IDX_PT_RANDBLOBS]
                                            current_path_timebase    = Transport.timebase_from_random_blobs(current_random_blobs)
                                            tunnel_announce_timebase = Transport.timebase_from_random_blobs(random_blobs)
                                            
                                            if current_path_timebase > tunnel_announce_timebase:
                                                stale_tunnel_paths.append(tunnel_path); Transport.should_collect = True
                                                RNS.log("Tunnel path to "+RNS.prettyhexrep(tunnel_path)+" was removed due to more recent active path", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                                for tunnel_path in stale_tunnel_paths:
                                    tunnel_paths.pop(tunnel_path)
                                    ti += 1

                    if ti > 0:
                        if ti == 1: RNS.log("Removed "+str(ti)+" tunnel path", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        else: RNS.log("Removed "+str(ti)+" tunnel paths", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                    i = 0
                    with Transport.reverse_table_lock:
                        for truncated_packet_hash in stale_reverse_entries:
                            if truncated_packet_hash in Transport.reverse_table: Transport.reverse_table.pop(truncated_packet_hash)
                            i += 1

                    if i > 0:
                        if i == 1: RNS.log("Released "+str(i)+" reverse table entry", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        else: RNS.log("Released "+str(i)+" reverse table entries", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                    i = 0
                    with Transport.link_table_lock:
                        for link_id in stale_links:
                            Transport.link_table.pop(link_id)
                            i += 1

                    if i > 0:
                        if i == 1: RNS.log("Released "+str(i)+" link", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        else: RNS.log("Released "+str(i)+" links", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                    i = 0
                    with Transport.path_table_lock:
                        for destination_hash in stale_paths:
                            if destination_hash in Transport.path_table: Transport.path_table.pop(destination_hash)
                            i += 1

                    if i > 0:
                        if i == 1: RNS.log("Removed "+str(i)+" path", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        else: RNS.log("Removed "+str(i)+" paths", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                    i = 0
                    with Transport.path_requests_lock:
                        for destination_hash in stale_path_requests:
                            Transport.path_requests.pop(destination_hash)
                            i += 1

                    if i > 0:
                        if i == 1: RNS.log("Removed "+str(i)+" path request entry", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        else: RNS.log("Removed "+str(i)+" path request entries", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                    i = 0
                    with Transport.inflight_path_requests_lock:
                        for destination_hash in stale_inflight_path_requests:
                            Transport.inflight_path_requests.pop(destination_hash)
                            i += 1

                    if i > 0:
                        if i == 1: RNS.log("Removed "+str(i)+" in-flight path request entry", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        else: RNS.log("Removed "+str(i)+" in-flight path request entries", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                    i = 0
                    with Transport.discovery_pr_lock:
                        for destination_hash in stale_discovery_path_requests:
                            Transport.discovery_path_requests.pop(destination_hash)
                            i += 1

                    if i > 0:
                        if i == 1: RNS.log("Removed "+str(i)+" waiting path request", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        else: RNS.log("Removed "+str(i)+" waiting path requests", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                    i = 0
                    with Transport.tunnels_lock:
                        for tunnel_id in stale_tunnels:
                            Transport.tunnels.pop(tunnel_id)
                            i += 1

                    if i > 0:
                        if i == 1: RNS.log("Removed "+str(i)+" tunnel", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        else: RNS.log("Removed "+str(i)+" tunnels", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                    i = 0
                    with Transport.path_states_lock:
                        for destination_hash in stale_path_states:
                            Transport.path_states.pop(destination_hash)
                            i += 1

                    if i > 0:
                        if i == 1: RNS.log("Removed "+str(i)+" path state entry", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        else: RNS.log("Removed "+str(i)+" path state entries", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                    Transport.tables_last_culled = time.time()

                # Run interface-related jobs
                if time.time() > Transport.interface_last_jobs + Transport.interface_jobs_interval:
                    Transport.prioritize_interfaces()
                    try:
                        for interface in Transport.interfaces:
                            interface.should_ingress_limit()
                            interface.should_ingress_limit_pr()
                            interface.process_held_announces()
                            if interface.phy_keepalive: interface.send_keepalive()
                        Transport.interface_last_jobs = time.time()
                    except Exception as e:
                        RNS.log(f"Error while processing held per-interface announces: {e}", RNS.LOG_WARNING)
                        RNS.log(f"Postponing until next job run", RNS.LOG_WARNING)

                # Clean packet caches
                if time.time() > Transport.cache_last_cleaned+Transport.cache_clean_interval:
                    Transport.cache_last_cleaned = time.time()
                    def job(): Transport.clean_cache()
                    threading.Thread(target=job, daemon=True).start()

                # Clean known destinations
                if time.time() > Transport.destinations_last_cleaned+Transport.known_destinations_interval:
                    Transport.destinations_last_cleaned = time.time()
                    def job():
                        try: RNS.Identity.clean_known_destinations(background=True)
                        except Exception as e: RNS.log(f"Error while running scheduled known destinations cleaning: {e}", RNS.LOG_ERROR)
                        finally: Transport.destinations_last_cleaned = time.time()
                    threading.Thread(target=job, daemon=True).start()

                # Send announces for management destinations
                if time.time() > Transport.last_mgmt_announce+Transport.mgmt_announce_interval:
                    try:
                        Transport.last_mgmt_announce = time.time()
                        def job():
                            for destination in Transport.mgmt_destinations: destination.announce()
                        threading.Thread(target=job, daemon=True).start()

                    except Exception as e:
                        RNS.log(f"Error while sending management announces: {e}", RNS.LOG_ERROR)

                # Check expired blackhole entries
                if time.time() > Transport.blackhole_last_checked+Transport.blackhole_check_interval:
                    try:
                        Transport.blackhole_last_checked = time.time()
                        stale_blackhole_entries = []
                        for identity_hash in Transport.blackholed_identities.copy():
                            try:
                                until = Transport.blackholed_identities[identity_hash]["until"]
                                if until and time.time() > until: stale_blackhole_entries.append(identity_hash)

                            except Exception as e:
                                RNS.log(f"Error while checking blackhole expiry for {RNS.prettyhexrep(identity_hash)}: {e}", RNS.LOG_ERROR)

                        i = 0
                        for identity_hash in stale_blackhole_entries:
                            if identity_hash in Transport.blackholed_identities:
                                Transport.blackholed_identities.pop(identity_hash)
                                i += 1

                        if i > 0:
                            if i == 1: RNS.log("Removed "+str(i)+" blackholed identity", RNS.LOG_VERBOSE) if RNS.sl(RNS.LOG_VERBOSE) else None
                            else: RNS.log("Removed "+str(i)+" blackholed identities", RNS.LOG_VERBOSE) if RNS.sl(RNS.LOG_VERBOSE) else None

                    except Exception as e:
                        RNS.log(f"Error while checking blackholed identities: {e}", RNS.LOG_ERROR)

                # Launch deferred callbacks
                while Transport.pending_callbacks:
                    try: Transport.pending_callbacks.pop(0).start()
                    except Exception as e: RNS.log(f"Could not launch pending callback: {e}", RNS.LOG_WARNING)

            if Transport.should_collect:
                Transport.mem_dirty = True
                if time.time() > Transport.last_collect+Transport.collect_throttle:
                    garbage_collect()

            trim_surplus = _trim_due(time.time())
            if trim_surplus is not None:
                Transport.mem_dirty = False; trim_heap()
                Transport.last_mem_trim = time.time()

        except Exception as e:
            RNS.log("An exception occurred while running Transport jobs.", RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)

        try:
            if outgoing:
                def job(): Transport.handle_outgoing_announces(outgoing)
                threading.Thread(target=job).start()

            if path_requests:
                with Transport.discovery_pr_tx_lock:
                    queued_destinations = [entry[0] for entry in Transport.pending_discovery_prs]
                    for destination_hash in path_requests:
                        if destination_hash not in queued_destinations:
                            if not len(Transport.pending_discovery_prs) >= Transport.max_queued_discovery_prs:
                                Transport.pending_discovery_prs.append([destination_hash, path_requests[destination_hash]])

            if len(Transport.pending_discovery_prs):
                def job(): Transport.handle_disovery_path_requests()
                threading.Thread(target=job).start()

        except Exception as e:
            RNS.log(f"Error while finalizing transport jobs: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

    @staticmethod
    def handle_outgoing_announces(outgoing):
        for packet in sorted(outgoing, key=lambda p: p.hops): packet.send()

    #########################
    # Stamp Work Management #
    #########################

    @staticmethod
    def ensure_stamper():
        if Transport.stamper_thread != None and Transport.stamper_thread.is_alive(): return
        with Transport.stamper_thread_lock:
            if Transport.stamper_thread == None or not Transport.stamper_thread.is_alive():
                Transport.stamper_thread = threading.Thread(target=Transport.stamper_job, daemon=True)
                RNS.log("Starting stamp worker", RNS.LOG_DEBUG)
                Transport.stamper_thread.start()

    @staticmethod
    def enqueue_stamped_announce(destination, app_data=None, path_response=False, attached_interface=None, tag=None):
        priority = Transport.STAMP_PR_PRIORITY if path_response else Transport.STAMP_DST_PRIORITY
        key      = None if path_response else destination.hash

        try: Transport.stamp_queues.put(priority, key, ("announce", destination, app_data, path_response, attached_interface, tag))
        except Full:
            RNS.log(f"Stamp queue full, dropping announce for {RNS.prettyhexrep(destination.hash)}", RNS.LOG_DEBUG)
            return

        Transport.ensure_stamper()

    @staticmethod
    def enqueue_stamped_pr(destination_hash, on_interface=None, tag=None, recursive=False):
        key = destination_hash if on_interface == None else destination_hash+on_interface.get_hash()
        try: Transport.stamp_queues.put(Transport.STAMP_PR_PRIORITY, key, ("pr", destination_hash, on_interface, tag, recursive))
        except Full:
            RNS.log(f"Stamp queue full, dropping path request for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_DEBUG)
            return

        Transport.ensure_stamper()

    @staticmethod
    def stamper_job():
        while Transport._should_run:
            try: key, job = Transport.stamp_queues.get(block=True, timeout=1)
            except Empty: continue
            job_type = job[0]

            try:
                if job_type == "pr":
                    jt, destination_hash, on_interface, tag, recursive = job
                    Transport.stamp_path_request(destination_hash, on_interface=on_interface, tag=tag, recursive=recursive)
                else:
                    jt, destination, app_data, path_response, attached_interface, tag = job
                    destination._announce(app_data=app_data, path_response=path_response, attached_interface=attached_interface, tag=tag, send=True)
            
            except Exception as e:
                target = RNS.prettyhexrep(job[1]) if job_type == "pr" else RNS.prettyhexrep(job[1].hash)
                RNS.log(f"Error while stamping and emitting {job_type} for {target}: {e}", RNS.LOG_ERROR)
                RNS.trace_exception(e)

    ############
    # Core I/O #
    ############

    @staticmethod
    def handle_outgoing_ifac(interface, raw):
        # Calculate packet access code
        ifac_size = interface.ifac_size
        ifac = interface.ifac_identity.sign(raw)[-ifac_size:]

        # Generate mask
        mask = RNS.Cryptography.hkdf(length=len(raw) + ifac_size, derive_from=ifac,
                                     salt=interface.ifac_key, context=None)

        # Set IFAC flag and assemble new payload with IFAC
        new_raw = bytes([raw[0] | 0x80, raw[1]]) + ifac + raw[2:]

        # Mask header bytes and payload with a single bignum XOR, leaving
        # the IFAC itself untouched, then ensure the IFAC flag is set.
        n = len(new_raw)
        x = int.from_bytes(new_raw, "big") ^ int.from_bytes(mask, "big")
        if ifac_size: x ^= int.from_bytes(mask[2:2 + ifac_size], "big") << (8 * (n - 2 - ifac_size))
        x |= 1 << (8 * n - 1)
        return x.to_bytes(n, "big")

    @staticmethod
    def handle_outgoing_ifac_legacy(interface, raw):
        # Calculate packet access code
        ifac = interface.ifac_identity.sign(raw)[-interface.ifac_size:]

        # Generate mask
        mask = RNS.Cryptography.hkdf(length=len(raw)+interface.ifac_size, derive_from=ifac,
                                     salt=interface.ifac_key, context=None)
        # Set IFAC flag
        new_header = bytes([raw[0] | 0x80, raw[1]])

        # Assemble new payload with IFAC
        new_raw    = new_header+ifac+raw[2:]

        # Mask payload
        i = 0; masked_raw = b""
        for byte in new_raw:
            # Mask first header byte, but make sure the
            # IFAC flag is still set
            if i == 0: masked_raw += bytes([byte ^ mask[i] | 0x80])

            # Mask second header byte and payload
            elif i == 1 or i > interface.ifac_size+1: masked_raw += bytes([byte ^ mask[i]])

            # Don't mask the IFAC itself
            else: masked_raw += bytes([byte])

            i += 1

        return masked_raw

    @staticmethod
    def transmit(interface, raw):
        try:
            if hasattr(interface, "ifac_identity") and interface.ifac_identity != None:
                interface.process_outgoing(Transport.handle_outgoing_ifac(interface, raw))
            else: interface.process_outgoing(raw)
            Transport.tx_packets += 1

        except Exception as e: RNS.log("Error while transmitting on "+str(interface)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

    @staticmethod
    def outbound(packet):
        if not Transport.USE_OUTBOUND_QUEUE: return Transport._outbound(packet)
        else:
            raise NotImplementedError("Outbound queue-based processing not available")
            # try: Transport.outbound_queue.put(packet, block=False)
            # except Full: RNS.log(f"Dropping outbound packet, TX queue is full", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
            # except Exception as e: RNS.log(f"Error while inserting into outbound queue: {e}", RNS.LOG_ERROR)
            # return False

    @staticmethod
    def outbound_job():
        raise NotImplementedError("Outbound queue-based processing not available")
        while Transport._should_run:
            try: Transport._outbound(Transport.outbound_queue.get())
            except Exception as e:
                RNS.log(f"Error while draining outbound queue: {e}", RNS.LOG_ERROR)
                RNS.trace_exception(e)

    @staticmethod
    def _outbound(packet):
        sent = False
        outbound_time = time.time()
        if packet.hops > Transport.PATHFINDER_M-1: return False

        generate_receipt = False
        if (packet.create_receipt == True and
            # Only generate receipts for DATA packets
            packet.packet_type == RNS.Packet.DATA and
            # Don't generate receipts for PLAIN destinations
            packet.destination.type != RNS.Destination.PLAIN and
            # Don't generate receipts for link-related packets
            not (packet.context >= RNS.Packet.KEEPALIVE and packet.context <= RNS.Packet.LRPROOF) and
            # Don't generate receipts for resource packets
            not (packet.context >= RNS.Packet.RESOURCE and packet.context <= RNS.Packet.RESOURCE_RCL)):

            generate_receipt = True

        def packet_sent(packet):
            packet.sent = True
            packet.sent_at = time.time()

            if generate_receipt:
                packet.receipt = RNS.PacketReceipt(packet)
                with Transport.receipts_lock: Transport.receipts.append(packet.receipt)
            
            # TODO: Enable when caching has been redesigned
            # Transport.cache(packet)

        # Check if we have a known path for the destination in the path table
        if packet.packet_type != RNS.Packet.ANNOUNCE and packet.destination.type != RNS.Destination.PLAIN and packet.destination.type != RNS.Destination.GROUP and packet.destination_hash in Transport.path_table:
            path_entry = Transport.path_table.get(packet.destination_hash)
            if not path_entry:
                RNS.log(f"Dropped packet since path table entry disappeared during outbound processing", RNS.LOG_WARNING)
                return False

            outbound_interface = path_entry[IDX_PT_RVCD_IF]
            path_entry[IDX_PT_USED] = outbound_time

            # If there's more than one hop to the destination, and we know
            # a path, we insert the packet into transport by adding the next
            # transport nodes address to the header, and modifying the flags.
            # This rule applies both for "normal" transport, and when connected
            # to a local shared Reticulum instance.
            if path_entry[IDX_PT_HOPS] > 1:
                if packet.header_type == RNS.Packet.HEADER_1:
                    # Insert packet into transport
                    new_flags = (RNS.Packet.HEADER_2) << 6 | (Transport.TRANSPORT) << 4 | (packet.flags & 0b00001111)
                    new_raw = struct.pack("!B", new_flags)
                    new_raw += packet.raw[1:2] if not Transport.should_apply_delta(packet, outbound_interface) else struct.pack("!B", Transport.local_hops_delta)
                    new_raw += path_entry[IDX_PT_NEXT_HOP]
                    new_raw += packet.raw[2:]
                    packet_sent(packet)
                    Transport.transmit(outbound_interface, new_raw)
                    sent = True

            # In the special case where we are connected to a local shared
            # Reticulum instance, and the destination is one hop away, we
            # also add transport headers to inject the packet into transport
            # via the shared instance. Normally a packet for a destination
            # one hop away would just be broadcast directly, but since we
            # are "behind" a shared instance, we need to get that instance
            # to transport it onto the network.
            elif path_entry[IDX_PT_HOPS] == 1 and Transport.owner.is_connected_to_shared_instance:
                if packet.header_type == RNS.Packet.HEADER_1:
                    # Insert packet into transport
                    new_flags = (RNS.Packet.HEADER_2) << 6 | (Transport.TRANSPORT) << 4 | (packet.flags & 0b00001111)
                    new_raw = struct.pack("!B", new_flags)
                    new_raw += packet.raw[1:2] if not Transport.should_apply_delta(packet, outbound_interface) else struct.pack("!B", Transport.local_hops_delta)
                    new_raw += path_entry[IDX_PT_NEXT_HOP]
                    new_raw += packet.raw[2:]
                    packet_sent(packet)
                    Transport.transmit(outbound_interface, new_raw)
                    sent = True

            # If none of the above applies, we know the destination is
            # directly reachable, and also on which interface, so we
            # simply transmit the packet directly on that one.
            else:
                packet_sent(packet)
                if not Transport.should_apply_delta(packet, outbound_interface): raw = packet.raw
                else: raw = Transport.mangle_hops(packet.raw, Transport.local_hops_delta)
                Transport.transmit(outbound_interface, raw)
                sent = True

        # If we don't have a known path for the destination, we'll
        # broadcast the packet on all outgoing interfaces, or the
        # just the relevant interface if the packet has an attached
        # interface, or belongs to a link.
        else:
            stored_hash = False
            if packet.attached_interface: potential_interfaces = [packet.attached_interface]
            else:                         potential_interfaces = Transport.interfaces

            for interface in potential_interfaces:
                if interface.OUT and interface.online:
                    should_transmit = True

                    if packet.destination.type == RNS.Destination.LINK:
                        if packet.destination.status == RNS.Link.CLOSED:       continue
                        if interface != packet.destination.attached_interface: continue

                    if packet.attached_interface != None and interface != packet.attached_interface: continue

                    if packet.packet_type == RNS.Packet.ANNOUNCE:
                        if packet.attached_interface == None:
                            ac_loglevel = RNS.LOG_PATHING
                            from_interface = Transport.next_hop_interface(packet.destination_hash)
                            local_destination = None
                            with Transport.destinations_map_lock:
                                if packet.destination_hash in Transport.destinations_map:
                                    local_destination = Transport.destinations_map[packet.destination_hash]

                            if not local_destination and from_interface == None:
                                RNS.log("Blocking announce broadcast on "+str(interface)+" since next hop interface doesn't exist", ac_loglevel) if RNS.sl(ac_loglevel) else None
                                should_transmit = False

                            elif not local_destination and interface.announces_from_internal == False and from_interface.mode == RNS.Interfaces.Interface.Interface.MODE_INTERNAL:
                                RNS.log("Blocking announce broadcast on "+str(interface)+" due to internal-mode next hop interface", ac_loglevel) if RNS.sl(ac_loglevel) else None
                                should_transmit = False

                            elif interface.mode == RNS.Interfaces.Interface.Interface.MODE_ACCESS_POINT:
                                RNS.log("Blocking announce broadcast on "+str(interface)+" due to AP mode", ac_loglevel) if RNS.sl(ac_loglevel) else None
                                should_transmit = False

                            elif not local_destination and interface.mode == RNS.Interfaces.Interface.Interface.MODE_INTERNAL:
                                if not hasattr(from_interface, "mode"):
                                    should_transmit = False
                                    RNS.log("Blocking announce broadcast on "+str(interface)+" since next hop interface has no mode configured", ac_loglevel) if RNS.sl(ac_loglevel) else None
                                else:
                                    if from_interface.announces_to_internal == True: pass
                                    elif from_interface.mode == RNS.Interfaces.Interface.Interface.MODE_BOUNDARY:
                                        RNS.log("Blocking announce broadcast on "+str(interface)+" due to boundary-mode next-hop interface", ac_loglevel) if RNS.sl(ac_loglevel) else None
                                        should_transmit = False

                            elif interface.mode == RNS.Interfaces.Interface.Interface.MODE_ROAMING:
                                if local_destination != None:
                                    # RNS.log("Allowing announce broadcast on roaming-mode interface from instance-local destination", ac_loglevel) if RNS.sl(ac_loglevel) else None
                                    pass
                                else:
                                    if not hasattr(from_interface, "mode"):
                                        should_transmit = False
                                        RNS.log("Blocking announce broadcast on "+str(interface)+" since next hop interface has no mode configured", ac_loglevel) if RNS.sl(ac_loglevel) else None
                                    else:
                                        if from_interface.mode == RNS.Interfaces.Interface.Interface.MODE_ROAMING:
                                            RNS.log("Blocking announce broadcast on "+str(interface)+" due to roaming-mode next-hop interface", ac_loglevel) if RNS.sl(ac_loglevel) else None
                                            should_transmit = False
                                        elif from_interface.mode == RNS.Interfaces.Interface.Interface.MODE_BOUNDARY:
                                            RNS.log("Blocking announce broadcast on "+str(interface)+" due to boundary-mode next-hop interface", ac_loglevel) if RNS.sl(ac_loglevel) else None
                                            should_transmit = False

                            elif interface.mode == RNS.Interfaces.Interface.Interface.MODE_BOUNDARY:
                                if local_destination != None:
                                    # RNS.log("Allowing announce broadcast on boundary-mode interface from instance-local destination", ac_loglevel) if RNS.sl(ac_loglevel) else None
                                    pass
                                else:
                                    if not hasattr(from_interface, "mode"):
                                        should_transmit = False
                                        RNS.log("Blocking announce broadcast on "+str(interface)+" since next hop interface has no mode configured", ac_loglevel) if RNS.sl(ac_loglevel) else None
                                    else:
                                        if from_interface.mode == RNS.Interfaces.Interface.Interface.MODE_ROAMING:
                                            RNS.log("Blocking announce broadcast on "+str(interface)+" due to roaming-mode next-hop interface", ac_loglevel) if RNS.sl(ac_loglevel) else None
                                            should_transmit = False

                            else:
                                # Currently, annouces originating locally are always
                                # allowed, and do not conform to bandwidth caps.
                                # TODO: Rethink whether this is actually optimal.
                                if packet.hops > 0:

                                    if not hasattr(interface, "announce_cap"):        interface.announce_cap = RNS.Reticulum.ANNOUNCE_CAP/100.0
                                    if not hasattr(interface, "announce_allowed_at"): interface.announce_allowed_at = 0
                                    if not hasattr(interface, "announce_queue"):      interface.announce_queue = []

                                    queued_announces = True if len(interface.announce_queue) > 0 else False
                                    if not queued_announces and outbound_time > interface.announce_allowed_at and interface.bitrate != None and interface.bitrate != 0:
                                        tx_time   = (len(packet.raw)*8) / interface.bitrate
                                        wait_time = (tx_time / interface.announce_cap)
                                        interface.announce_allowed_at = outbound_time + wait_time
                                    
                                    else:
                                        should_transmit = False
                                        if not len(interface.announce_queue) >= RNS.Reticulum.MAX_QUEUED_ANNOUNCES:
                                            should_queue = True

                                            already_queued = False
                                            for e in interface.announce_queue:
                                                if e["destination"] == packet.destination_hash:
                                                    already_queued = True
                                                    existing_entry = e
                                                    break

                                            emission_timestamp = Transport.announce_emitted(packet)
                                            if already_queued:
                                                should_queue = False

                                                if emission_timestamp > existing_entry["emitted"]:
                                                    existing_entry["time"] = outbound_time
                                                    existing_entry["hops"] = packet.hops
                                                    existing_entry["emitted"] = emission_timestamp
                                                    existing_entry["raw"] = packet.raw

                                            if should_queue:
                                                entry = { "destination": packet.destination_hash,
                                                          "time": outbound_time,
                                                          "hops": packet.hops,
                                                          "emitted": Transport.announce_emitted(packet),
                                                          "raw": packet.raw }

                                                queued_announces = True if len(interface.announce_queue) > 0 else False
                                                interface.announce_queue.append(entry)

                                                if not queued_announces:
                                                    wait_time = max(interface.announce_allowed_at - time.time(), 0)
                                                    timer = threading.Timer(wait_time, interface.process_announce_queue)
                                                    timer.start()

                                                    if RNS.sl(RNS.LOG_EXTREME):
                                                        if wait_time < 1: wait_time_str = str(round(wait_time*1000,2))+"ms"
                                                        else:             wait_time_str = str(round(wait_time*1,2))+"s"
                                                        ql_str = str(len(interface.announce_queue))
                                                        RNS.log("Added announce to queue (height "+ql_str+") on "+str(interface)+" for processing in "+wait_time_str, RNS.LOG_EXTREME)

                                                else:
                                                    if RNS.sl(RNS.LOG_EXTREME):
                                                        wait_time = max(interface.announce_allowed_at - time.time(), 0)
                                                        if wait_time < 1: wait_time_str = str(round(wait_time*1000,2))+"ms"
                                                        else:             wait_time_str = str(round(wait_time*1,2))+"s"
                                                        ql_str = str(len(interface.announce_queue))
                                                        RNS.log("Added announce to queue (height "+ql_str+") on "+str(interface)+" for processing in "+wait_time_str, RNS.LOG_EXTREME)

                                        else: pass
                                
                                else: pass

                    if should_transmit:
                        if not stored_hash:
                            Transport.add_packet_hash(packet.packet_hash)
                            stored_hash = True

                        if not Transport.should_apply_delta(packet, interface): raw = packet.raw
                        else:
                            if packet.packet_type != RNS.Packet.ANNOUNCE: raw = Transport.mangle_hops(packet.raw, Transport.local_hops_delta)
                            else: raw = Transport.mangle_hops(packet.raw, Transport.local_hops_delta, transport_insert=packet.header_type==RNS.Packet.HEADER_1)

                        Transport.transmit(interface, raw)
                        if packet.packet_type == RNS.Packet.ANNOUNCE: interface.sent_announce(size=len(raw)); Transport.announce_txc += 1
                        if packet.destination.type == RNS.Destination.PLAIN and packet.is_outbound_pr: interface.sent_path_request(size=len(raw)); Transport.pr_txc += 1
                        packet_sent(packet)
                        sent = True

        return sent

    @staticmethod
    def should_apply_delta(packet, interface):
        return not Transport.owner.is_connected_to_shared_instance and packet.hops == 0 and Transport.local_hops_delta != 0 \
               and not packet.destination.type == RNS.Destination.PLAIN and not packet.destination.type == RNS.Destination.GROUP \
               and not interface in Transport.local_client_interfaces and not Transport.is_shared_instance(interface)

    @staticmethod
    def mangle_hops(raw, hops, transport_insert=False):
        if not transport_insert: return raw[0:1]+struct.pack("!B", hops)+raw[2:]
        else: return struct.pack("!B", ord(raw[0:1]) | (RNS.Packet.HEADER_2<<6) | (Transport.TRANSPORT<<4))+struct.pack("!B", hops)+Transport.identity.hash+raw[2:]

    @staticmethod
    def add_packet_hash(packet_hash):
        if not Transport.owner.is_connected_to_shared_instance:
            Transport.packet_hashlist.add(packet_hash)

    @staticmethod
    def packet_filter(packet):
        # If connected to a shared instance, it will handle
        # packet filtering
        if Transport.owner.is_connected_to_shared_instance: return True

        # Filter packets intended for other transport instances
        if packet.transport_id != None and packet.packet_type != RNS.Packet.ANNOUNCE:
            if packet.transport_id != Transport.identity.hash:
                RNS.log("Ignored packet "+RNS.prettyhexrep(packet.packet_hash)+" in transport for other transport instance", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                return False

        if packet.context == RNS.Packet.KEEPALIVE:     return True
        if packet.context == RNS.Packet.RESOURCE_REQ:  return True
        if packet.context == RNS.Packet.RESOURCE_PRF:  return True
        if packet.context == RNS.Packet.RESOURCE:      return True
        if packet.context == RNS.Packet.CACHE_REQUEST: return True
        if packet.context == RNS.Packet.CHANNEL:       return True

        if packet.destination_type == RNS.Destination.PLAIN:
            if packet.packet_type != RNS.Packet.ANNOUNCE:
                if packet.hops > 1:
                    RNS.log("Dropped PLAIN packet "+RNS.prettyhexrep(packet.packet_hash)+" with "+str(packet.hops)+" hops", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                    if packet.receiving_interface: packet.receiving_interface.protocol_violation(f"Transported PLAIN packet with {str(packet.hops)} hops")
                    return False
                else:
                    return True
            else:
                RNS.log("Dropped invalid PLAIN announce packet", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                if packet.receiving_interface: packet.receiving_interface.protocol_violation("Announce packet with PLAIN type")
                return False

        if packet.destination_type == RNS.Destination.GROUP:
            if packet.packet_type != RNS.Packet.ANNOUNCE:
                if packet.hops > 1:
                    RNS.log("Dropped GROUP packet "+RNS.prettyhexrep(packet.packet_hash)+" with "+str(packet.hops)+" hops", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                    if packet.receiving_interface: packet.receiving_interface.protocol_violation(f"Transported GROUP packet with {str(packet.hops)} hops")
                    return False
                else:
                    return True
            else:
                RNS.log("Dropped invalid GROUP announce packet", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                if packet.receiving_interface: packet.receiving_interface.protocol_violation("Announce packet with GROUP type")
                return False

        if not packet.packet_hash in Transport.packet_hashlist: return True
        else:
            if packet.packet_type == RNS.Packet.ANNOUNCE:
                if packet.destination_type == RNS.Destination.SINGLE:
                    return True
                else:
                    RNS.log("Dropped invalid announce packet", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                    if packet.receiving_interface: packet.receiving_interface.protocol_violation("Announce packet with invalid destination type")
                    return False

        RNS.log("Filtered packet with hash "+RNS.prettyhexrep(packet.packet_hash), RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
        return False

    @staticmethod
    def inbound(raw, interface=None, tc=None, ifac_handled=False):
        try: Transport.preprocess_inbound(raw=raw, interface=interface, tc=tc, ifac_handled=ifac_handled)
        except Exception as e:
            RNS.log(f"Error while processing inbound on {interface}: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

    @staticmethod
    def handle_ifac(raw, interface):
        # Extract IFAC
        ifac_size = interface.ifac_size
        ifac = raw[2:2 + ifac_size]

        # Generate mask
        mask = RNS.Cryptography.hkdf(length=len(raw), derive_from=ifac,
                                     salt=interface.ifac_key, context=None)

        # Unmask header bytes and payload with a single bignum XOR,
        # leaving the IFAC tag itself untouched, then drop the IFAC
        # flag and strip to actual frame payload.
        n = len(raw)
        x = int.from_bytes(raw, "big") ^ int.from_bytes(mask, "big")
        if ifac_size: x ^= int.from_bytes(mask[2:2 + ifac_size], "big") << (8 * (n - 2 - ifac_size))
        unmasked = x.to_bytes(n, "big")

        # Unset IFAC flag and re-assemble packet
        new_raw = bytes([unmasked[0] & 0x7f, unmasked[1]]) + unmasked[2 + ifac_size:]

        # Calculate expected IFAC
        expected_ifac = interface.ifac_identity.sign(new_raw)[-ifac_size:]

        # Check it
        if ifac == expected_ifac: return True, new_raw
        else:
            interface.ifac_violation("Invalid IFAC on packet")
            return False, None

    @staticmethod
    def handle_ifac_legacy(raw, interface):
        # Extract IFAC
        ifac = raw[2:2+interface.ifac_size]

        # Generate mask
        mask = RNS.Cryptography.hkdf(length=len(raw), derive_from=ifac,
                                     salt=interface.ifac_key, context=None)
        # Unmask payload
        i = 0; unmasked_raw = b""
        for byte in raw:
            # Unmask header bytes and payload
            if i <= 1 or i > interface.ifac_size+1: unmasked_raw += bytes([byte ^ mask[i]])
            # Don't unmask IFAC itself
            else: unmasked_raw += bytes([byte])
            i += 1

        raw = unmasked_raw

        # Unset IFAC flag
        new_header = bytes([raw[0] & 0x7f, raw[1]])

        # Re-assemble packet
        new_raw = new_header+raw[2+interface.ifac_size:]

        # Calculate expected IFAC
        expected_ifac = interface.ifac_identity.sign(new_raw)[-interface.ifac_size:]

        # Check it
        if ifac == expected_ifac: return True, new_raw
        else:
            interface.ifac_violation("Invalid IFAC on packet")
            return False, None

    @staticmethod
    def preprocess_inbound(raw, interface=None, tc=None, ifac_handled=False):
        if not Transport.ready:
            wait_start = time.time()
            while not Transport.ready:
                time.sleep(0.25)
                if time.time() > wait_start + Transport.READY_WAIT:
                    RNS.log("Inbound packet timed out waiting for transport startup, dropping", RNS.LOG_WARNING)
                    return

        # If interface access codes are enabled,
        # we must authenticate each packet.
        if len(raw) > 2:
            if interface != None and hasattr(interface, "ifac_identity") and interface.ifac_identity != None:
                if not ifac_handled:
                    # Check that IFAC flag is set
                    if raw[0] & 0x80 == 0x80:
                        if len(raw) > 2+interface.ifac_size:
                            ifac_valid, raw = Transport.handle_ifac(raw, interface)
                            if not ifac_valid: return

                        else: return interface.ifac_violation("Insufficient packet size for IFAC packet")

                    # If the IFAC flag is not set, but should be,
                    # drop the packet.
                    else: return interface.ifac_violation("Missing IFAC flag on packet for IFAC-enabled interface")

            else:
                # If the interface does not have IFAC enabled,
                # check the received packet IFAC flag.
                # If the flag is set, drop the packet
                if raw[0] & 0x80 == 0x80:
                    return interface.ifac_violation("IFAC flag set on packet for interface without IFAC enabled") if interface else None

        else: return interface.protocol_violation("Insufficient packet size for IFAC processing") if interface else None

        if Transport.identity == None: return

        if interface and len(raw) > interface.HW_MTU + (interface.ifac_size or 0):
            return interface.protocol_violation(f"Frame size exceeded MTU of {interface.HW_MTU} on {interface}")

        packet = RNS.Packet(None, raw)
        if not packet.unpack(): return interface.protocol_violation(f"Malformed packet ({len(raw)} bytes)") if interface else None
        if not packet.hops < Transport.HOP_LIMITER: return interface.hop_limiter_hit()
        if not Transport.packet_filter(packet): return interface.packet_filter_hit()
        traffic_class = tc or Transport.TC_DATA

        Transport.rx_packets += 1
        packet.receiving_interface = interface
        packet.hops += 1

        # Ingress limit announces early
        if packet.packet_type == RNS.Packet.ANNOUNCE:
            name_hash = packet.data[RNS.Identity.KEYSIZE//8:RNS.Identity.KEYSIZE//8+RNS.Identity.NAME_HASH_LENGTH//8]
            if len(name_hash) != RNS.Identity.NAME_HASH_LENGTH//8: return packet.receiving_interface.protocol_violation(f"Malformed announce packet with size {len(packet.data)}")

            if Transport.blocked_destination_types and name_hash in Transport.blocked_destination_types: return
            if Transport.required_destinations_only:
                if   name_hash in Transport.allowed_destination_types:                   allowed = True
                elif name_hash in Transport.client_destination_types:                    allowed = True
                elif Transport.is_local_client_interface(packet.receiving_interface):    allowed = True if packet.hops == 1 else False # 1 == 0 really, yes it's weird  ~. . .~
                elif Transport.interface_to_shared_instance(packet.receiving_interface): allowed = True if packet.hops == 1 else False # 1 == 0 really, yes it's weird    `-`
                else:                                                                    allowed = False
                if not allowed: return

            if len(raw) > RNS.Reticulum.MTU: return packet.receiving_interface.protocol_violation(f"Excessive announce packet frame size of {len(raw)} bytes") if packet.receiving_interface else None
            if traffic_class < Transport.TC_ANNOUNCE: traffic_class = Transport.TC_ANNOUNCE
            announce_signature_valid = RNS.Identity.validate_announce(packet, only_validate_signature=True, signal_blackholed=True, signal_stamp=True)
            if   announce_signature_valid == "blackholed":    return None
            elif announce_signature_valid == "no_stamp":      return None
            elif announce_signature_valid == "invalid_stamp": return None
            elif not announce_signature_valid:
                return packet.receiving_interface.protocol_violation(f"Invalid announce signature for {RNS.prettyhexrep(packet.destination_hash)}") if packet.receiving_interface else None

            elif packet.receiving_interface != None: packet.receiving_interface.received_announce(size=len(packet.raw))
            Transport.announce_rxc += 1

            announced_destination_known = packet.destination_hash in Transport.path_table
            if not announced_destination_known:
                # This is an unknown destination, and we'll apply
                # potential ingress limiting. Already known
                # destinations will have re-announces controlled
                # by normal announce rate limiting.
                if packet.destination_hash in Transport.path_requests or packet.destination_hash in Transport.discovery_path_requests:
                    # RNS.log(f"Skipping ingress limit check for {RNS.prettyhexrep(packet.destination_hash)} due to waiting path requests", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                    pass

                elif packet.receiving_interface.should_ingress_limit():
                    packet.receiving_interface.hold_announce(packet)
                    return

        # Ingress limit path requests early
        elif packet.destination_hash == Transport.pr_destination_hash:
            if traffic_class < Transport.TC_PATH_REQUEST: traffic_class = Transport.TC_PATH_REQUEST
            if not len(packet.data) >= RNS.Identity.TRUNCATED_HASHLENGTH//8: return
            elif len(packet.data) > Transport.PR_STAMPED_LENGTH: return packet.receiving_interface.protocol_violation(f"Excessive path request size of {len(packet.data)} bytes") if packet.receiving_interface else None
            else:
                pr = Transport.parse_path_request(packet.data)
                if pr == None: return packet.receiving_interface.protocol_violation("Tagless path request", level=RNS.LOG_PATHING) if packet.receiving_interface else None
                else:
                    destination_hash = pr[0]
                    tag_bytes        = pr[2]
                    ext_payload      = pr[3]
                    tag_valid        = False

                    pr_length = len(packet.data)
                    if pr_length != Transport.PR_STAMPED_LENGTH and pr_length != Transport.PR_LENGTH and pr_length != Transport.PR_LEGACY_LENGTH: # TODO: Only allow stamped size after transition
                        if packet.receiving_interface: return packet.receiving_interface.protocol_violation(f"Invalid path request size {pr_length}", level=RNS.LOG_PATHING)

                    unique_tag = destination_hash+tag_bytes

                    with Transport.discovery_pr_tags_lock:
                        if not unique_tag in Transport.discovery_pr_tags and not unique_tag in Transport.discovery_pr_tags_prev:
                            Transport.discovery_pr_tags.add(unique_tag)
                            tag_valid = True

                    if not tag_valid:
                        RNS.log(f"Ignoring duplicate path request for {RNS.prettyhexrep(destination_hash)} with tag {RNS.prettyhexrep(unique_tag)}", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        return

                    if Transport.STAMPS_ENABLED:
                        stamp_ok = False
                        if ext_payload != None:
                            if ext_payload[0] == RNS.Identity.EXTPAYLOADMARKER:
                                required_value = packet.receiving_interface.pr_cost
                                stamp = ext_payload[Transport.PR_EXT_HEADERLENGTH:]
                                stamp_ok = Transport.validate_pr_stamp(stamp, destination_hash, tag_bytes, required_value=required_value)

                                # TODO: Remove debug block #################################################
                                dval = None
                                if RNS.sl(RNS.LOG_PATHING):
                                    workblock = stamp_workblock(Transport.pr_stamp_material(destination_hash, tag_bytes), expand_rounds=0) # TODO: Remove
                                    dval = stamp_value(workblock, ext_payload[Transport.PR_EXT_HEADERLENGTH:])
                                    if not ext_payload[1] == 0xFF: RNS.log(f"Stamped path request for {RNS.prettyhexrep(destination_hash)} with value {dval}", RNS.LOG_PATHING)
                                    else:                          RNS.log(f"Lenient-relayed path request for {RNS.prettyhexrep(destination_hash)} with value {dval}", RNS.LOG_PATHING)
                                ############################################################################

                                if not stamp_ok:
                                    if ext_payload[1] == 0xFF: RNS.log(f"Unstamped relayed path request from stamp-aware node for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None # TODO: Remove this transitory diagnostics check once enforcement is enabled
                                    # else: RNS.log(f"Invalid or insufficient path request stamp for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                                    # TODO: Reset else block to collapsed LOG_EXTREME message commented out above #####
                                    else:
                                        if RNS.sl(RNS.LOG_PATHING):
                                            if dval: RNS.log(f"Invalid or insufficient (v:{dval}) path request stamp for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                            else:    RNS.log(f"Invalid or insufficient path request stamp for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                    ########################################################################
                            else: RNS.log(f"Unrecognized stamp payload in path request for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                        else: RNS.log(f"Unstamped path request for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None # TODO: Remove after transition, simply drop

                        if not stamp_ok:
                            if Transport.STAMPS_ENFORCED: return

                    if packet.receiving_interface: packet.receiving_interface.received_path_request(size=len(raw))
                    Transport.pr_rxc += 1
                    if interface.should_ingress_limit_pr():
                        traffic_class = Transport.TC_INGRESS_LIMITED

                    path_request_inflight = False
                    with Transport.inflight_path_requests_lock:
                        if destination_hash in Transport.inflight_path_requests: path_request_inflight = True

                    if not path_request_inflight:
                        # Early registration to immediately batch duplicates
                        with Transport.inflight_path_requests_lock: Transport.inflight_path_requests[destination_hash] = time.time()
                    else:
                        if not traffic_class == Transport.TC_INGRESS_LIMITED:
                            RNS.log(f"Path request on {packet.receiving_interface} for {RNS.prettyhexrep(destination_hash)} already in-flight, batching to existing", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                            with Transport.discovery_pr_lock:
                                if destination_hash in Transport.discovery_path_requests:
                                    if not packet.receiving_interface in Transport.discovery_path_requests[destination_hash]["requesting_interfaces"]:
                                        Transport.discovery_path_requests[destination_hash]["requesting_interfaces"].append(packet.receiving_interface)

                                else:
                                    discovery_timeout = max(Transport.PATH_REQUEST_TIMEOUT, Transport.medium_path_timeout())
                                    pr_entry = { "destination_hash": destination_hash, "timeout": time.time()+discovery_timeout,
                                                 "requesting_interfaces": [packet.receiving_interface], "engaged": False }

                                    Transport.discovery_path_requests[destination_hash] = pr_entry

                        return

                    # TODO: Add early filtering here for non-transport nodes; there's no
                    # reason to process further if we know we don't have the destination
                    # locally on this system. Might need adding a local_client_dest_map,
                    # but this will need to be kept *tightly* in-sync.

        if not Transport.USE_INBOUND_QUEUE: return Transport._inbound(packet)
        else:
            if traffic_class == Transport.TC_INGRESS_LIMITED: packet.traffic_class = Transport.TC_INGRESS_LIMITED
            try: Transport.inbound_queues.put(traffic_class, packet, block=False)
            except Full: RNS.log(f"Dropping inbound packet, queue is full (tc={traffic_class})", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
            except Exception as e: RNS.log(f"Error while inserting into inbound queue: {e}", RNS.LOG_ERROR)

    @staticmethod
    def inbound_job():
        while Transport._should_run:
                try: packet = Transport.inbound_queues.get()
                except Exception as e:
                    RNS.log(f"Error while draining inbound queue: {e}", RNS.LOG_ERROR)
                    RNS.trace_exception(e)
                    continue

                try: Transport._inbound(packet)
                except Exception as e:
                    packet.receiving_interface.protocol_violation("Processing caused exception") if packet.receiving_interface else None
                    RNS.log(f"Error while processing inbound packet: {e}", RNS.LOG_ERROR)
                    RNS.trace_exception(e)

    @staticmethod
    def _inbound(packet):
        if packet.receiving_interface != None:
            if not packet.receiving_interface.online: return

            if packet.receiving_interface.reports_phy_stats:
                if packet.receiving_interface.r_stat_rssi != None:
                    packet.rssi = packet.receiving_interface.r_stat_rssi
                    Transport.local_client_rssi_cache.append([packet.packet_hash, packet.rssi])
                    while len(Transport.local_client_rssi_cache) > Transport.LOCAL_CLIENT_CACHE_MAXSIZE:
                        Transport.local_client_rssi_cache.pop(0)

                if packet.receiving_interface.r_stat_snr != None:
                    packet.snr = packet.receiving_interface.r_stat_snr
                    Transport.local_client_snr_cache.append([packet.packet_hash, packet.snr])
                    while len(Transport.local_client_snr_cache) > Transport.LOCAL_CLIENT_CACHE_MAXSIZE:
                        Transport.local_client_snr_cache.pop(0)

                if packet.receiving_interface.r_stat_q != None:
                    packet.q = packet.receiving_interface.r_stat_q
                    Transport.local_client_q_cache.append([packet.packet_hash, packet.q])
                    while len(Transport.local_client_q_cache) > Transport.LOCAL_CLIENT_CACHE_MAXSIZE:
                        Transport.local_client_q_cache.pop(0)

        if len(Transport.local_client_interfaces) > 0:
            if Transport.is_local_client_interface(packet.receiving_interface): packet.hops -= 1

        elif Transport.interface_to_shared_instance(packet.receiving_interface): packet.hops -= 1

        # By default, remember packet hashes to avoid routing
        # loops in the network, using the packet filter.
        remember_packet_hash = True

        # If this packet belongs to a link in our link table,
        # we'll have to defer adding it to the filter list.
        # In some cases, we might see a packet over a shared-
        # medium interface, belonging to a link that transports
        # or terminates with this instance, but before it would
        # normally reach us. If the packet is appended to the
        # filter list at this point, link transport will break.
        if packet.destination_hash in Transport.link_table: remember_packet_hash = False

        # If this is a link request proof, don't add it until
        # we are sure it's not actually somewhere else in the
        # routing chain.
        if packet.packet_type == RNS.Packet.PROOF and packet.context == RNS.Packet.LRPROOF: remember_packet_hash = False

        if remember_packet_hash:
            Transport.add_packet_hash(packet.packet_hash)
            # TODO: Enable when caching has been redesigned
            # Transport.cache(packet)
        
        # Check special conditions for local clients connected
        # through a shared Reticulum instance
        from_local_client         = (packet.receiving_interface in Transport.local_client_interfaces)
        for_local_client          = (packet.packet_type != RNS.Packet.ANNOUNCE) and (packet.destination_hash in Transport.path_table and Transport.path_table[packet.destination_hash][IDX_PT_HOPS] == 0)
        local_client_nh           = (packet.packet_type != RNS.Packet.ANNOUNCE) and (packet.destination_hash in Transport.link_table and Transport.link_table[packet.destination_hash][IDX_LT_NH_IF] in Transport.local_client_interfaces)
        local_client_rh           = (packet.packet_type != RNS.Packet.ANNOUNCE) and (packet.destination_hash in Transport.link_table and Transport.link_table[packet.destination_hash][IDX_LT_RCVD_IF] in Transport.local_client_interfaces)
        proof_for_local_client    = (packet.destination_hash in Transport.reverse_table) and (Transport.reverse_table[packet.destination_hash][IDX_RT_RCVD_IF] in Transport.local_client_interfaces)
        to_local_client           = for_local_client or proof_for_local_client
        instance_local_link       = local_client_nh and local_client_rh
        for_local_client_link     = local_client_nh or local_client_rh
        link_request_handled      = False

        # Plain broadcast packets from local clients are sent
        # directly on all attached interfaces, since they are
        # never injected into transport.
        if not packet.destination_hash in Transport.control_hashes:
            if packet.destination_type == RNS.Destination.PLAIN and packet.transport_type == Transport.BROADCAST:
                # Send to all interfaces except the originator
                if from_local_client:
                    for interface in Transport.interfaces:
                        if interface != packet.receiving_interface:
                            Transport.transmit(interface, packet.raw)
                # If the packet was not from a local client, send
                # it directly to all local clients
                else:
                    for interface in Transport.local_client_interfaces:
                        Transport.transmit(interface, packet.raw)


        # General transport handling. Takes care of directing
        # packets according to transport tables and recording
        # entries in reverse and link tables.
        if RNS.Reticulum.transport_enabled() or from_local_client or for_local_client or for_local_client_link:

            # If there is no transport id, but the packet is
            # for a local client, we generate the transport
            # id (it was stripped on the previous hop, since
            # we "spoof" the hop count for clients behind a
            # shared instance, so they look directly reach-
            # able), and reinsert, so the normal transport
            # implementation can handle the packet.
            if packet.transport_id == None and for_local_client:
                packet.transport_id = Transport.identity.hash

            # If this is a cache request, and we can fullfill
            # it, do so and stop processing. Otherwise resume
            # normal processing.
            if packet.context == RNS.Packet.CACHE_REQUEST:
                if Transport.cache_request_packet(packet): return

            # If the packet is in transport, check whether we
            # are the designated next hop, and process it
            # accordingly if we are.
            if packet.transport_id != None and packet.packet_type != RNS.Packet.ANNOUNCE:
                if not packet.transport_id == Transport.identity.hash: return
                else:
                    path_entry = Transport.path_table.get(packet.destination_hash)
                    if path_entry != None:
                        next_hop = path_entry[IDX_PT_NEXT_HOP]
                        remaining_hops = path_entry[IDX_PT_HOPS]
                        
                        if remaining_hops > 1:
                            # Just increase hop count and transmit
                            new_raw  = packet.raw[0:1]
                            new_raw += struct.pack("!B", packet.hops)
                            new_raw += next_hop
                            new_raw += packet.raw[(RNS.Identity.TRUNCATED_HASHLENGTH//8)+2:]
                        elif remaining_hops == 1:
                            # Strip transport headers and transmit
                            new_flags = (RNS.Packet.HEADER_1) << 6 | (Transport.BROADCAST) << 4 | (packet.flags & 0b00001111)
                            new_raw = struct.pack("!B", new_flags)
                            new_raw += struct.pack("!B", packet.hops)
                            new_raw += packet.raw[(RNS.Identity.TRUNCATED_HASHLENGTH//8)+2:]
                        elif remaining_hops == 0:
                            if to_local_client and Transport.local_hops_delta != 0:
                                if packet.header_type == RNS.Packet.HEADER_2:
                                    # Strip transport headers and transmit
                                    new_flags = (RNS.Packet.HEADER_1) << 6 | (Transport.BROADCAST) << 4 | (packet.flags & 0b00001111)
                                    new_raw = struct.pack("!B", new_flags)
                                    new_raw += struct.pack("!B", packet.hops)
                                    new_raw += packet.raw[(RNS.Identity.TRUNCATED_HASHLENGTH//8)+2:]
                                else:
                                    # Just increase hop count and transmit
                                    new_raw  = packet.raw[0:1]
                                    new_raw += struct.pack("!B", packet.hops)
                                    new_raw += packet.raw[2:]
                            else:
                                # Just increase hop count and transmit
                                new_raw  = packet.raw[0:1]
                                new_raw += struct.pack("!B", packet.hops)
                                new_raw += packet.raw[2:]

                        outbound_interface = path_entry[IDX_PT_RVCD_IF]

                        if packet.packet_type == RNS.Packet.LINKREQUEST:
                            now = time.time()
                            proof_timeout  = Transport.extra_link_proof_timeout(outbound_interface)
                            proof_timeout += now + RNS.Link.ESTABLISHMENT_TIMEOUT_PER_HOP * max(1, remaining_hops)
                            
                            path_mtu       = RNS.Link.mtu_from_lr_packet(packet)
                            mode           = RNS.Link.mode_from_lr_packet(packet)
                            ph_mtu         = packet.receiving_interface.HW_MTU if packet.receiving_interface else None
                            nh_mtu         = outbound_interface.HW_MTU
                            if path_mtu:
                                if outbound_interface.HW_MTU == None:
                                    RNS.log(f"No next-hop HW MTU, disabling link MTU upgrade", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                    path_mtu = None
                                    new_raw  = new_raw[:-RNS.Link.LINK_MTU_SIZE]
                                elif not outbound_interface.AUTOCONFIGURE_MTU and not outbound_interface.FIXED_MTU:
                                    RNS.log(f"Outbound interface doesn't support MTU autoconfiguration, disabling link MTU upgrade", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                    path_mtu = None
                                    new_raw  = new_raw[:-RNS.Link.LINK_MTU_SIZE]
                                else:
                                    if nh_mtu < path_mtu or (ph_mtu and ph_mtu < path_mtu):
                                        try:
                                            path_mtu = min(nh_mtu, ph_mtu)
                                            clamped_mtu = RNS.Link.signalling_bytes(path_mtu, mode)
                                            RNS.log(f"Clamping link MTU to {RNS.prettysize(path_mtu)}", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                            new_raw  = new_raw[:-RNS.Link.LINK_MTU_SIZE]+clamped_mtu
                                        except Exception as e:
                                            RNS.log(f"Dropping link request packet. The contained exception was: {e}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                                            if packet.receiving_interface: packet.receiving_interface.protocol_violation("Undecodable path MTU signalling bytes")
                                            return

                            # Entry format is
                            link_entry = [  now,                            # 0: Timestamp,
                                            next_hop,                       # 1: Next-hop transport ID
                                            outbound_interface,             # 2: Next-hop interface
                                            remaining_hops,                 # 3: Remaining hops
                                            packet.receiving_interface,     # 4: Received on interface
                                            packet.hops,                    # 5: Taken hops
                                            packet.destination_hash,        # 6: Original destination hash
                                            False,                          # 7: Validated
                                            proof_timeout ]                 # 8: Proof timeout timestamp

                            with Transport.link_table_lock: Transport.link_table[RNS.Link.link_id_from_lr_packet(packet)] = link_entry
                            link_request_handled = True

                        else:
                            # Entry format is
                            reverse_entry = [ packet.receiving_interface,   # 0: Received on interface
                                              outbound_interface,           # 1: Outbound interface
                                              time.time() ]                 # 2: Timestamp

                            with Transport.reverse_table_lock: Transport.reverse_table[packet.truncated_packet_hash] = reverse_entry

                        if Transport.local_hops_delta != 0 and from_local_client and not to_local_client: new_raw = Transport.mangle_hops(new_raw, Transport.local_hops_delta)
                        Transport.transmit(outbound_interface, new_raw)
                        path_entry[IDX_PT_USED] = time.time()

                    else:
                        # TODO: There should probably be some kind of REJECT
                        # mechanism here, to signal to the source that their
                        # expected path failed.
                        RNS.log("Got packet in transport, but no known path to final destination "+RNS.prettyhexrep(packet.destination_hash)+". Dropping packet.", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

            # Link transport handling. Directs packets according
            # to entries in the link tables
            if packet.packet_type != RNS.Packet.ANNOUNCE and packet.packet_type != RNS.Packet.LINKREQUEST and packet.context != RNS.Packet.LRPROOF:
                if packet.destination_hash in Transport.link_table:
                    link_entry = Transport.link_table[packet.destination_hash]
                    if not link_entry[IDX_LT_VALIDATED]:
                        RNS.log(f"Pre-validation link packet from {packet.receiving_interface}", RNS.LOG_WARNING) # TODO: Remove
                        return packet.receiving_interface.protocol_violation("Link packet received before link validation") if packet.receiving_interface else None

                    # If receiving and outbound interface is
                    # the same for this link, direction doesn't
                    # matter, and we simply repeat the packet.
                    outbound_interface = None
                    if link_entry[IDX_LT_NH_IF] == link_entry[IDX_LT_RCVD_IF]:
                        # But check that taken hops matches one
                        # of the expectede values.
                        if packet.hops == link_entry[IDX_LT_REM_HOPS] or packet.hops == link_entry[IDX_LT_HOPS]:
                            outbound_interface = link_entry[IDX_LT_NH_IF]
                    else:
                        # If interfaces differ, we transmit on
                        # the opposite interface of what the
                        # packet was received on.
                        if packet.receiving_interface == link_entry[IDX_LT_NH_IF]:
                            # Also check that expected hop count matches
                            if packet.hops == link_entry[IDX_LT_REM_HOPS]:
                                outbound_interface = link_entry[IDX_LT_RCVD_IF]
                        elif packet.receiving_interface == link_entry[IDX_LT_RCVD_IF]:
                            # Also check that expected hop count matches
                            if packet.hops == link_entry[IDX_LT_HOPS]:
                                outbound_interface = link_entry[IDX_LT_NH_IF]

                    if outbound_interface != None:
                        # Add this packet to the filter hashlist if we
                        # have determined that it's actually our turn
                        # to process it.
                        Transport.add_packet_hash(packet.packet_hash)

                        new_raw = packet.raw[0:1]
                        new_raw += struct.pack("!B", packet.hops if not from_local_client or instance_local_link or Transport.local_hops_delta == 0 else Transport.local_hops_delta)
                        new_raw += packet.raw[2:]
                        Transport.transmit(outbound_interface, new_raw)

                        active_time = time.time()
                        Transport.link_table[packet.destination_hash][IDX_LT_TIMESTAMP] = active_time
                        link_path_entry = Transport.path_table.get(Transport.link_table[packet.destination_hash][IDX_LT_DSTHASH])
                        if link_path_entry: link_path_entry[IDX_PT_USED] = active_time

                    else: RNS.log(f"No-outbound return on link packet from {packet.receiving_interface}", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None

                    return

        # Announce handling. Handles logic related to incoming
        # announces, queueing rebroadcasts of these, and removal
        # of queued announce rebroadcasts once handed to the next node.
        if packet.packet_type == RNS.Packet.ANNOUNCE:
            announce_valid = RNS.Identity.validate_announce(packet)
            if not announce_valid: return packet.receiving_interface.protocol_violation("Invalid announce") if packet.receiving_interface else None

            local_destination = Transport.destinations_map.get(packet.destination_hash)
            if local_destination == None and announce_valid:
                if packet.transport_id != None:
                    received_from = packet.transport_id
                    
                    # Check if this is a next retransmission from
                    # another node. If it is, we're removing the
                    # announce in question from our pending table
                    if RNS.Reticulum.transport_enabled() and packet.destination_hash in Transport.announce_table:
                        announce_entry = Transport.announce_table[packet.destination_hash]
                        
                        if packet.hops-1 == announce_entry[IDX_AT_HOPS]:
                            RNS.log(f"Heard a rebroadcast of announce for {RNS.prettyhexrep(packet.destination_hash)} on {packet.receiving_interface}", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                            announce_entry[IDX_AT_LCL_RBRD] += 1
                            if announce_entry[IDX_AT_RETRIES] > 0:
                                if announce_entry[IDX_AT_LCL_RBRD] >= Transport.LOCAL_REBROADCASTS_MAX:
                                    RNS.log("Completed announce processing for "+RNS.prettyhexrep(packet.destination_hash)+", local rebroadcast limit reached", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                                    with Transport.announce_table_lock:
                                        if packet.destination_hash in Transport.announce_table: Transport.announce_table.pop(packet.destination_hash)

                        if packet.hops-1 == announce_entry[IDX_AT_HOPS]+1 and announce_entry[IDX_AT_RETRIES] > 0:
                            now = time.time()
                            if now < announce_entry[IDX_AT_RTRNS_TMO]:
                                RNS.log("Rebroadcasted announce for "+RNS.prettyhexrep(packet.destination_hash)+" has been passed on to another node, no further tries needed", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                                with Transport.announce_table_lock:
                                    if packet.destination_hash in Transport.announce_table: Transport.announce_table.pop(packet.destination_hash)

                else: received_from = packet.destination_hash

                # Check if this announce should be inserted into
                # announce and destination tables
                should_add = False

                # First, check that the announce is not for a destination
                # local to this system, and that hops are less than the max
                with Transport.destinations_map_lock:
                    local_and_hops_condition = (packet.hops < Transport.PATHFINDER_M+1) and (not packet.destination_hash in Transport.destinations_map)

                if local_and_hops_condition:
                    announce_emitted = Transport.announce_emitted(packet)
                    
                    path_used    = 0
                    random_blobs = []
                    random_blob  = packet.data[RNS.Identity.KEYSIZE//8+RNS.Identity.NAME_HASH_LENGTH//8:RNS.Identity.KEYSIZE//8+RNS.Identity.NAME_HASH_LENGTH//8+10]
                    if not random_blob: return packet.receiving_interface.protocol_violation("No random blob in data") if packet.receiving_interface else None

                    with Transport.inbound_announce_lock:
                        existing_path_entry = Transport.path_table.get(packet.destination_hash)
                        announced_destination_known = existing_path_entry != None
                        if not announced_destination_known:
                            # If this destination is unknown in our table
                            # we should add it
                            should_add = True

                        else:
                            random_blobs     = existing_path_entry[IDX_PT_RANDBLOBS]
                            current_gravity  = existing_path_entry[IDX_PT_RVCD_IF].gravity
                            path_used        = existing_path_entry[IDX_PT_USED]
                            announce_gravity = packet.receiving_interface.gravity if packet.receiving_interface != None else None

                            # If we already have a path to the announced destination,
                            # but a more recently emitted announce arrives with a hop
                            # count equal to or less than the existing path, we will
                            # update our tables.
                            if packet.hops <= existing_path_entry[IDX_PT_HOPS]:
                                path_timebase = Transport.timebase_from_random_blobs(random_blobs)
                                if not random_blob in random_blobs and announce_emitted > path_timebase:
                                    Transport.mark_path_unknown_state(packet.destination_hash)
                                    should_add = True
                                else:
                                    # If the same announce is received later on an interface
                                    # with higher gravity, allow updating the path table to
                                    # use this interface instead.
                                    if   announce_emitted != path_timebase: should_add = False
                                    elif announce_gravity == None or current_gravity == None: should_add = False
                                    else:
                                        if announce_gravity <= current_gravity: should_add = False
                                        else:
                                            RNS.log(f"Replacing path table entry for {RNS.prettyhexrep(packet.destination_hash)} with new announce due to higher gravity ({current_gravity}->{announce_gravity})", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                            should_add = True
                            else:
                                # If an announce arrives with a larger hop
                                # count than we already have in the table,
                                # ignore it, unless the path is expired, or
                                # the emission timestamp is more recent.
                                now = time.time()
                                path_expires = existing_path_entry[IDX_PT_EXPIRES]
                                
                                path_announce_emitted = 0
                                for path_random_blob in random_blobs:
                                    path_announce_emitted = max(path_announce_emitted, int.from_bytes(path_random_blob[5:10], "big"))
                                    if path_announce_emitted >= announce_emitted: break

                                # If the path has expired, consider this
                                # announce for adding to the path table.
                                if (now >= path_expires):
                                    # We check that the announce is
                                    # different from ones we've already heard,
                                    # to avoid loops in the network
                                    if not random_blob in random_blobs:
                                        RNS.log("Replacing path table entry for "+str(RNS.prettyhexrep(packet.destination_hash))+" with new announce due to expired path", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                        Transport.mark_path_unknown_state(packet.destination_hash)
                                        should_add = True
                                    else: should_add = False

                                else:
                                    # If the path is not expired, but the emission
                                    # is more recent, and we haven't already heard
                                    # this announce before, update the path table.
                                    if (announce_emitted > path_announce_emitted):
                                        if not random_blob in random_blobs:
                                            RNS.log("Replacing path table entry for "+str(RNS.prettyhexrep(packet.destination_hash))+" with new announce, since it was more recently emitted", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                            Transport.mark_path_unknown_state(packet.destination_hash)
                                            should_add = True
                                        else: should_add = False
                                    
                                    # If we have already heard this announce before,
                                    # but the path has been marked as unresponsive
                                    # by a failed communications attempt or similar,
                                    # allow updating the path table to this one.
                                    elif announce_emitted == path_announce_emitted:
                                        if Transport.path_is_unresponsive(packet.destination_hash):
                                            RNS.log("Replacing path table entry for "+str(RNS.prettyhexrep(packet.destination_hash))+" with new announce, since previously tried path was unresponsive", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                            should_add = True
                                        else: should_add = False

                        if should_add:
                            now = time.time()
                            is_from_local_client = Transport.from_local_client(packet)

                            rate_blocked = False
                            if packet.context != RNS.Packet.PATH_RESPONSE and packet.receiving_interface.announce_rate_target != None:
                                with Transport.announce_rate_table_lock:
                                    rate_blocked = Transport.announce_rate_table.check_and_update(packet.destination_hash, now,
                                                                                                  packet.receiving_interface.announce_rate_target,
                                                                                                  packet.receiving_interface.announce_rate_grace,
                                                                                                  packet.receiving_interface.announce_rate_penalty)
                            retries            = 0
                            announce_hops      = packet.hops
                            local_rebroadcasts = 0
                            block_rebroadcasts = False
                            attached_interface = None
                            
                            retransmit_timeout = now + (RNS.rand() * Transport.PATHFINDER_RW)
                            expires            = now + Transport.path_timeout_from_interface(packet.receiving_interface)
                            
                            if not random_blob in random_blobs:
                                random_blobs.append(random_blob)
                                random_blobs = random_blobs[-Transport.MAX_RANDOM_BLOBS:]

                            if (RNS.Reticulum.transport_enabled() or is_from_local_client) and packet.context != RNS.Packet.PATH_RESPONSE:
                                # Insert announce into announce table for retransmission

                                if rate_blocked: RNS.log("Blocking rebroadcast of announce from "+RNS.prettyhexrep(packet.destination_hash)+" due to excessive announce rate", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                else:
                                    if is_from_local_client:
                                        # If the announce is from a local client,
                                        # it is announced immediately, but only one time.
                                        retransmit_timeout = now
                                        retries = Transport.PATHFINDER_R

                                    with Transport.announce_table_lock:
                                        Transport.announce_table[packet.destination_hash] = [
                                            now,                # 0: IDX_AT_TIMESTAMP
                                            retransmit_timeout, # 1: IDX_AT_RTRNS_TMO
                                            retries,            # 2: IDX_AT_RETRIES
                                            received_from,      # 3: IDX_AT_RCVD_IF
                                            announce_hops,      # 4: IDX_AT_HOPS
                                            packet,             # 5: IDX_AT_PACKET
                                            local_rebroadcasts, # 6: IDX_AT_LCL_RBRD
                                            block_rebroadcasts, # 7: IDX_AT_BLCK_RBRD
                                            attached_interface, # 8: IDX_AT_ATTCHD_IF
                                        ]

                            elif is_from_local_client and packet.context == RNS.Packet.PATH_RESPONSE:
                                # If this is a path response from a local client,
                                # check if any external interfaces have pending
                                # path requests.
                                with Transport.pending_local_prs_lock:
                                    if packet.destination_hash in Transport.pending_local_path_requests:
                                        desiring_interface = Transport.pending_local_path_requests.pop(packet.destination_hash)
                                        retransmit_timeout = now
                                        retries = Transport.PATHFINDER_R

                                        with Transport.announce_table_lock:
                                            Transport.announce_table[packet.destination_hash] = [
                                                now,
                                                retransmit_timeout,
                                                retries,
                                                received_from,
                                                announce_hops,
                                                packet,
                                                local_rebroadcasts,
                                                block_rebroadcasts,
                                                attached_interface
                                            ]

                            # If we have any local clients connected, we re-
                            # transmit the announce to them immediately
                            if len(Transport.local_client_interfaces):
                                announce_identity = RNS.Identity.recall(packet.destination_hash, _no_use=True)
                                if not announce_identity: RNS.log(f"Aborting local-client announce rebroadcast for {RNS.prettyhexrep(destination_hash)}, the path was cleaned while waiting for announce rebroadcast", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                else:
                                    announce_destination = RNS.Destination(announce_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "unknown", "unknown");
                                    announce_destination.hash = packet.destination_hash
                                    announce_destination.hexhash = announce_destination.hash.hex()
                                    announce_context = RNS.Packet.NONE
                                    announce_data = packet.data

                                    # TODO: Shouldn't the context be PATH_RESPONSE in the first case here?
                                    if is_from_local_client and packet.context == RNS.Packet.PATH_RESPONSE:
                                        for local_interface in Transport.local_client_interfaces:
                                            if packet.receiving_interface != local_interface:
                                                new_announce = RNS.Packet(announce_destination, announce_data, RNS.Packet.ANNOUNCE, # <-- This one?
                                                                          context = announce_context, header_type = RNS.Packet.HEADER_2,
                                                                          transport_type = Transport.TRANSPORT, transport_id = Transport.identity.hash,
                                                                          attached_interface = local_interface, context_flag = packet.context_flag)

                                                new_announce.hops = packet.hops
                                                new_announce.send()

                                    else:
                                        for local_interface in Transport.local_client_interfaces:
                                            if packet.receiving_interface != local_interface:
                                                new_announce = RNS.Packet(announce_destination, announce_data, RNS.Packet.ANNOUNCE,
                                                                          context = announce_context, header_type = RNS.Packet.HEADER_2,
                                                                          transport_type = Transport.TRANSPORT, transport_id = Transport.identity.hash,
                                                                          attached_interface = local_interface, context_flag = packet.context_flag)

                                                new_announce.hops = packet.hops
                                                new_announce.send()

                            # If we have any waiting discovery path requests
                            # for this destination, we retransmit to that
                            # interface immediately
                            with Transport.discovery_pr_lock:
                                if not packet.destination_hash in Transport.discovery_path_requests: discovery_pr_entry = None
                                else: discovery_pr_entry = Transport.discovery_path_requests.pop(packet.destination_hash)

                            if discovery_pr_entry:
                                for attached_interface in discovery_pr_entry["requesting_interfaces"]:
                                    interface_str = " on "+str(attached_interface)
                                    RNS.log("Got matching announce, answering waiting discovery path request for "+RNS.prettyhexrep(packet.destination_hash)+interface_str, RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                    announce_identity = RNS.Identity.recall(packet.destination_hash, _no_use=False)
                                    if not announce_identity: RNS.log(f"Aborting path request answer for {RNS.prettyhexrep(destination_hash)}, the path was cleaned while waiting for the response", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                                    else:
                                        announce_destination = RNS.Destination(announce_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "unknown", "unknown");
                                        announce_destination.hash = packet.destination_hash
                                        announce_destination.hexhash = announce_destination.hash.hex()
                                        announce_context = RNS.Packet.NONE
                                        announce_data = packet.data

                                        new_announce = RNS.Packet(announce_destination, announce_data, RNS.Packet.ANNOUNCE,
                                                                  context = RNS.Packet.PATH_RESPONSE, header_type = RNS.Packet.HEADER_2,
                                                                  transport_type = Transport.TRANSPORT, transport_id = Transport.identity.hash,
                                                                  attached_interface = attached_interface, context_flag = packet.context_flag)

                                        new_announce.hops = packet.hops
                                        new_announce.send()

                            if not Transport.owner.is_connected_to_shared_instance: Transport.cache(packet, force_cache=True, packet_type="announce")
                            if rate_blocked:
                                # Rate-limited announces do not update liveness
                                # metrics, only the essential routing data.
                                with Transport.path_table_lock:
                                    rate_limited_path_entry = Transport.path_table.get(packet.destination_hash)
                                    if rate_limited_path_entry != None:
                                        rate_limited_path_entry[IDX_PT_NEXT_HOP]  = received_from
                                        rate_limited_path_entry[IDX_PT_HOPS]      = announce_hops
                                        rate_limited_path_entry[IDX_PT_RANDBLOBS] = random_blobs
                                        rate_limited_path_entry[IDX_PT_RVCD_IF]   = packet.receiving_interface
                                        rate_limited_path_entry[IDX_PT_PACKET]    = packet.packet_hash
                            else:
                                path_table_entry = [now, received_from, announce_hops, expires, random_blobs, packet.receiving_interface, packet.packet_hash, path_used]
                                with Transport.path_table_lock: Transport.path_table[packet.destination_hash] = path_table_entry

                            Transport.mark_path_unknown_state(packet.destination_hash)
                            if RNS.sl(RNS.LOG_PATHING):
                                destination_value = RNS.Identity.recall_stamp_value(packet.destination_hash)
                                value_str = f" (v:{RNS.prettycost(destination_value)})" if destination_value else " (v:n)"
                                RNS.log(f"Destination {RNS.prettyhexrep(packet.destination_hash)}{value_str} is now {announce_hops} hops away via {RNS.prettyhexrep(received_from)} on {packet.receiving_interface}", RNS.LOG_PATHING)

                            if packet.destination_hash in Transport.path_requests:
                                RNS.Reticulum.get_instance()._used_destination_data(packet.destination_hash)

                            # If the receiving interface is a tunnel, we add the
                            # announce to the tunnels table
                            if not rate_blocked and hasattr(packet.receiving_interface, "tunnel_id") and packet.receiving_interface.tunnel_id != None:
                                with Transport.tunnels_lock:
                                    if not packet.receiving_interface.tunnel_id in Transport.tunnels: RNS.log(f"Tunnel ID for {packet.receiving_interface} was not found in tunnel table", RNS.LOG_WARNING)
                                    else:
                                        tunnel_entry = Transport.tunnels[packet.receiving_interface.tunnel_id]
                                        paths = tunnel_entry[IDX_TT_PATHS]
                                        paths[packet.destination_hash] = [now, received_from, announce_hops, expires, random_blobs, None, packet.packet_hash, path_used]
                                        expires = time.time() + Transport.TUNNEL_TIMEOUT
                                        tunnel_entry[IDX_TT_EXPIRES] = expires
                                        RNS.log("Path to "+RNS.prettyhexrep(packet.destination_hash)+" associated with tunnel "+RNS.prettyhexrep(packet.receiving_interface.tunnel_id), RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None

                            # Resolve potential in-flight path requests
                            with Transport.inflight_path_requests_lock:
                                if packet.destination_hash in Transport.inflight_path_requests:
                                    Transport.inflight_path_requests.pop(packet.destination_hash)

                            # Call externally registered callbacks from apps
                            # wanting to know when an announce arrives
                            with Transport.announce_handler_lock:
                                name_hash = packet.data[RNS.Identity.KEYSIZE//8:RNS.Identity.KEYSIZE//8+RNS.Identity.NAME_HASH_LENGTH//8]
                                announce_identity = None
                                announce_app_data = None

                                announce_handlers = []
                                announce_handlers.extend(Transport.announce_handlers.get(name_hash, []))
                                announce_handlers.extend(Transport.announce_handlers.get(None, []))
                                for handler in announce_handlers:
                                    if not announce_identity: announce_identity = RNS.Identity.recall(packet.destination_hash, _no_use=True)
                                    if not announce_identity: break
                                    if handler.paused: continue
                                    try:
                                        handler_args     = handler._rns_transport_cb_signature_len
                                        handler_job      = None
                                        execute_callback = True

                                        # If this is a path response, check whether the
                                        # handler wants to receive it.
                                        if packet.context == RNS.Packet.PATH_RESPONSE:
                                            if hasattr(handler, "receive_path_responses") and handler.receive_path_responses == True: pass
                                            else: execute_callback = False

                                        if execute_callback:
                                            if not announce_app_data:
                                                announce_app_data = RNS.Identity.recall_app_data(packet.destination_hash, _no_use=True)

                                            if handler_args == 3:
                                                def job(handler=handler, packet=packet, announce_identity=announce_identity):
                                                    handler.received_announce(destination_hash=packet.destination_hash, announced_identity=announce_identity,
                                                                              app_data=announce_app_data)
                                                handler_job = job

                                            elif handler_args == 4:
                                                def job(handler=handler, packet=packet, announce_identity=announce_identity):
                                                    handler.received_announce(destination_hash=packet.destination_hash, announced_identity=announce_identity,
                                                                              app_data=announce_app_data, announce_packet_hash=packet.packet_hash)
                                                handler_job = job

                                            elif handler_args == 5:
                                                def job(handler=handler, packet=packet, announce_identity=announce_identity):
                                                    handler.received_announce(destination_hash=packet.destination_hash, announced_identity=announce_identity,
                                                                              app_data=announce_app_data, announce_packet_hash=packet.packet_hash,
                                                                              is_path_response=packet.context == RNS.Packet.PATH_RESPONSE)
                                                handler_job = job

                                            else: raise TypeError("Invalid signature for announce handler callback")

                                        if handler_job: Transport.pending_callbacks.append(threading.Thread(target=job, daemon=True))

                                    except Exception as e:
                                        RNS.log(f"Error while processing external announce callback: {e}", RNS.LOG_ERROR)
                                        RNS.trace_exception(e)

        # Handling for link requests to local destinations
        elif packet.packet_type == RNS.Packet.LINKREQUEST and not link_request_handled:
            if packet.transport_id == None or packet.transport_id == Transport.identity.hash:
                destination = Transport.destinations_map.get(packet.destination_hash)
                if destination and destination.type == packet.destination_type:
                    path_mtu       = RNS.Link.mtu_from_lr_packet(packet)
                    mode           = RNS.Link.mode_from_lr_packet(packet)
                    if packet.receiving_interface.AUTOCONFIGURE_MTU or packet.receiving_interface.FIXED_MTU:
                        nh_mtu     = packet.receiving_interface.HW_MTU
                    else:
                        nh_mtu     = RNS.Reticulum.MTU

                    if path_mtu:
                        if packet.receiving_interface.HW_MTU == None:
                            path_mtu = None
                            packet.data  = packet.data[:-RNS.Link.LINK_MTU_SIZE]
                        else:
                            if nh_mtu < path_mtu:
                                try:
                                    path_mtu = nh_mtu
                                    clamped_mtu = RNS.Link.signalling_bytes(path_mtu, mode)
                                    packet.data  = packet.data[:-RNS.Link.LINK_MTU_SIZE]+clamped_mtu
                                except Exception as e:
                                    RNS.log(f"Dropping link request packet to local destination. The contained exception was: {e}", RNS.LOG_WARNING)
                                    if packet.receiving_interface: packet.receiving_interface.protocol_violation("Undecodable path MTU signalling bytes")
                                    return

                    packet.destination = destination
                    destination.receive(packet)
        
        # Handling for local data packets
        elif packet.packet_type == RNS.Packet.DATA:
            if packet.destination_type == RNS.Destination.LINK:
                link = Transport.active_links_map.get(packet.destination_hash)
                if link != None:
                    if link.attached_interface == packet.receiving_interface:
                        packet.link = link
                        if packet.context == RNS.Packet.CACHE_REQUEST:
                            cached_packet = Transport.get_cached_packet(packet.data)
                            if cached_packet != None:
                                if not cached_packet.unpack(): return
                                RNS.Packet(destination=link, data=cached_packet.data,
                                           packet_type=cached_packet.packet_type, context=cached_packet.context).send()

                        else: link.receive(packet)

                    else:
                        # In the strange and rare case that an interface
                        # is partly malfunctioning, and a link-associated
                        # packet is being received on an interface that
                        # has failed sending, and transport has failed over
                        # to another path, we remove this packet hash from
                        # the filter hashlist so the link can receive the
                        # packet when it finally arrives over another path.
                        Transport.packet_hashlist.discard(packet.packet_hash)
            else:
                destination = Transport.destinations_map.get(packet.destination_hash)
                if destination and destination.type == packet.destination_type:
                    packet.destination = destination
                    if destination.receive(packet):
                        if destination.proof_strategy == RNS.Destination.PROVE_ALL: packet.prove()
                        elif destination.proof_strategy == RNS.Destination.PROVE_APP:
                            if destination.callbacks.proof_requested:
                                try:
                                    if destination.callbacks.proof_requested(packet): packet.prove()
                                except Exception as e: RNS.log("Error while executing proof request callback. The contained exception was: "+str(e), RNS.LOG_ERROR)

        # Handling for proofs and link-request proofs
        elif packet.packet_type == RNS.Packet.PROOF:
            if packet.context == RNS.Packet.LRPROOF:
                # This is a link request proof, check if it needs to be transported
                REBALANCE_LOGLEVEL = RNS.LOG_PATHING
                if (RNS.Reticulum.transport_enabled() or for_local_client_link or from_local_client) and packet.destination_hash in Transport.link_table:
                    link_entry = Transport.link_table[packet.destination_hash]
                    if packet.hops != link_entry[IDX_LT_REM_HOPS] and Transport.ALLOW_LINK_PATH_REBALANCE:
                        if packet.receiving_interface == link_entry[IDX_LT_NH_IF]:
                            try:
                                if len(packet.data) == RNS.Identity.SIGLENGTH//8+RNS.Link.ECPUBSIZE//2 or len(packet.data) == RNS.Identity.SIGLENGTH//8+RNS.Link.ECPUBSIZE//2+RNS.Link.LINK_MTU_SIZE:
                                    signalling_bytes = b""
                                    if len(packet.data) == RNS.Identity.SIGLENGTH//8+RNS.Link.ECPUBSIZE//2+RNS.Link.LINK_MTU_SIZE:
                                        signalling_bytes = RNS.Link.signalling_bytes(RNS.Link.mtu_from_lp_packet(packet), RNS.Link.mode_from_lp_packet(packet))

                                    peer_pub_bytes = packet.data[RNS.Identity.SIGLENGTH//8:RNS.Identity.SIGLENGTH//8+RNS.Link.ECPUBSIZE//2]
                                    peer_identity = RNS.Identity.recall(link_entry[IDX_LT_DSTHASH], _no_use=True)
                                    peer_sig_pub_bytes = peer_identity.get_public_key()[RNS.Link.ECPUBSIZE//2:RNS.Link.ECPUBSIZE]

                                    signed_data = packet.destination_hash+peer_pub_bytes+peer_sig_pub_bytes+signalling_bytes
                                    signature = packet.data[:RNS.Identity.SIGLENGTH//8]
                                    link_destination = link_entry[IDX_LT_DSTHASH]

                                    if peer_identity.validate(signature, signed_data) and not link_entry[IDX_LT_VALIDATED]:
                                        RNS.log(f"Re-balancing path to {RNS.prettyhexrep(link_destination)} from link-request proof ({link_entry[IDX_LT_REM_HOPS]}->{packet.hops})", REBALANCE_LOGLEVEL) if RNS.sl(REBALANCE_LOGLEVEL) else None
                                        link_entry[IDX_LT_REM_HOPS] = packet.hops
                                        path_entry = Transport.path_table.get(link_destination)
                                        if path_entry: path_entry[IDX_PT_HOPS] = packet.hops
                                        Transport.mark_path_responsive(link_destination)

                                    elif not link_entry[IDX_LT_VALIDATED]: RNS.log(f"Aborting link request proof path re-balancing for {RNS.prettyhexrep(link_destination)} on link {RNS.prettyhexrep(packet.destination_hash)} due to invalid signature", REBALANCE_LOGLEVEL) if RNS.sl(REBALANCE_LOGLEVEL) else None
                                    else: pass

                            except Exception as e: RNS.log(f"Error while re-balancing path from link request proof. The contained exception was: {e}", RNS.LOG_ERROR) if RNS.sl(RNS.LOG_ERROR) else None # TODO: Drop to DEBUG at some point

                    if packet.hops == link_entry[IDX_LT_REM_HOPS]:
                        if packet.receiving_interface == link_entry[IDX_LT_NH_IF]:
                            try:
                                if len(packet.data) == RNS.Identity.SIGLENGTH//8+RNS.Link.ECPUBSIZE//2 or len(packet.data) == RNS.Identity.SIGLENGTH//8+RNS.Link.ECPUBSIZE//2+RNS.Link.LINK_MTU_SIZE:
                                    signalling_bytes = b""
                                    if len(packet.data) == RNS.Identity.SIGLENGTH//8+RNS.Link.ECPUBSIZE//2+RNS.Link.LINK_MTU_SIZE:
                                        signalling_bytes = RNS.Link.signalling_bytes(RNS.Link.mtu_from_lp_packet(packet), RNS.Link.mode_from_lp_packet(packet))

                                    peer_pub_bytes = packet.data[RNS.Identity.SIGLENGTH//8:RNS.Identity.SIGLENGTH//8+RNS.Link.ECPUBSIZE//2]
                                    peer_identity = RNS.Identity.recall(link_entry[IDX_LT_DSTHASH], _no_use=True)
                                    peer_sig_pub_bytes = peer_identity.get_public_key()[RNS.Link.ECPUBSIZE//2:RNS.Link.ECPUBSIZE]

                                    signed_data = packet.destination_hash+peer_pub_bytes+peer_sig_pub_bytes+signalling_bytes
                                    signature = packet.data[:RNS.Identity.SIGLENGTH//8]

                                    if peer_identity.validate(signature, signed_data):
                                        RNS.log("Link request proof validated for transport via "+str(link_entry[IDX_LT_RCVD_IF]), RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                                        new_raw = packet.raw[0:1]
                                        new_raw += struct.pack("!B", packet.hops if not from_local_client or instance_local_link or Transport.local_hops_delta == 0 else Transport.local_hops_delta)
                                        new_raw += packet.raw[2:]
                                        Transport.link_table[packet.destination_hash][IDX_LT_VALIDATED] = True
                                        Transport.transmit(link_entry[IDX_LT_RCVD_IF], new_raw)
                                        if not Transport.owner.is_connected_to_shared_instance:
                                            RNS.Identity._used_destination_data(link_entry[IDX_LT_DSTHASH])
                                            Transport.mark_path_responsive(link_entry[IDX_LT_DSTHASH])

                                    else:
                                        RNS.log("Invalid link request proof in transport for link "+RNS.prettyhexrep(packet.destination_hash)+", dropping proof.", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                                        return packet.receiving_interface.protocol_violation("Invalid link request proof in transport") if packet.receiving_interface else None

                            except Exception as e: RNS.log("Could not transport link request proof. The contained exception was: "+str(e), RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                        else: RNS.log("Link request proof received on wrong interface, not transporting it.", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                    else: RNS.log(f"Received link request proof with hop mismatch ({packet.hops}/{link_entry[IDX_LT_REM_HOPS]}:{link_entry[IDX_LT_NH_IF]}->{link_entry[IDX_LT_RCVD_IF]}), not transporting it", REBALANCE_LOGLEVEL) if RNS.sl(REBALANCE_LOGLEVEL) else None
                
                else:
                    # Check if we can deliver it to a local pending link
                    pending_link = None
                    with Transport.pending_links_lock:
                        link = Transport.pending_links_map.get(packet.destination_hash)
                        if link != None:
                            if packet.hops != link.expected_hops and link.status == RNS.Link.PENDING and Transport.ALLOW_LINK_PATH_REBALANCE:
                                RNS.log(f"Unbalanced link path ({packet.hops}/{link.expected_hops}) detected on link {link}, validating signature for re-balancing...", REBALANCE_LOGLEVEL) if RNS.sl(REBALANCE_LOGLEVEL) else None
                                try:
                                    if len(packet.data) == RNS.Identity.SIGLENGTH//8+RNS.Link.ECPUBSIZE//2 or len(packet.data) == RNS.Identity.SIGLENGTH//8+RNS.Link.ECPUBSIZE//2+RNS.Link.LINK_MTU_SIZE:
                                        packet_data = packet.data
                                        signalling_bytes = b""
                                        confirmed_mtu = None
                                        mode = RNS.Link.mode_from_lp_packet(packet)
                                        if mode != link.mode: raise TypeError(f"Invalid link mode {mode} in link request proof")
                                        if len(packet_data) == RNS.Identity.SIGLENGTH//8+RNS.Link.ECPUBSIZE//2+RNS.Link.LINK_MTU_SIZE:
                                            confirmed_mtu = RNS.Link.mtu_from_lp_packet(packet)
                                            signalling_bytes = RNS.Link.signalling_bytes(confirmed_mtu, mode)
                                            packet_data = packet_data[:RNS.Identity.SIGLENGTH//8+RNS.Link.ECPUBSIZE//2]

                                        peer_pub_bytes = packet_data[RNS.Identity.SIGLENGTH//8:RNS.Identity.SIGLENGTH//8+RNS.Link.ECPUBSIZE//2]
                                        peer_sig_pub_bytes = link.destination.identity.get_public_key()[RNS.Link.ECPUBSIZE//2:RNS.Link.ECPUBSIZE]

                                        signed_data = link.link_id+peer_pub_bytes+peer_sig_pub_bytes+signalling_bytes
                                        signature = packet_data[:RNS.Identity.SIGLENGTH//8]

                                        if link.destination.identity.validate(signature, signed_data):
                                            if not link.rebalanced:
                                                RNS.log(f"Re-balancing path to {RNS.prettyhexrep(link.destination.hash)} at link terminus ({link.expected_hops}->{packet.hops})", REBALANCE_LOGLEVEL) if RNS.sl(REBALANCE_LOGLEVEL) else None
                                                link.rebalanced = time.time()
                                                link.expected_hops = packet.hops
                                                path_entry = Transport.path_table.get(link.destination.hash)
                                                if path_entry:
                                                    path_entry[IDX_PT_HOPS] = packet.hops
                                                    RNS.log(f"Path table re-balanced for {RNS.prettyhexrep(link.destination.hash)}", REBALANCE_LOGLEVEL) if RNS.sl(REBALANCE_LOGLEVEL) else None
                                                Transport.mark_path_responsive(link.destination.hash)

                                        else: RNS.log(f"Aborting path re-balancing at link terminus for {RNS.prettyhexrep(link.destination.hash)} on link {link} due to invalid signature", REBALANCE_LOGLEVEL) if RNS.sl(REBALANCE_LOGLEVEL) else None
                                except Exception as e: RNS.log("Error while validating link request proof for path re-balancing at link terminus. The contained exception was: "+str(e), REBALANCE_LOGLEVEL) if RNS.sl(REBALANCE_LOGLEVEL) else None

                            if packet.hops == link.expected_hops:
                                # Add this packet to the filter hashlist if we
                                # have determined that it's actually destined
                                # for this system, and then validate the proof
                                Transport.add_packet_hash(packet.packet_hash)
                                pending_link = link

                    if pending_link: pending_link.validate_proof(packet)

            elif packet.context == RNS.Packet.RESOURCE_PRF:
                link = Transport.active_links_map.get(packet.destination_hash)
                if link != None: link.receive(packet)
            else:
                if packet.destination_type == RNS.Destination.LINK:
                    link = Transport.active_links_map.get(packet.destination_hash)
                    if link != None: packet.link = link
                            
                if len(packet.data) == RNS.PacketReceipt.EXPL_LENGTH: proof_hash = packet.data[:RNS.Identity.HASHLENGTH//8]
                else:                                                 proof_hash = None

                # Check if this proof needs to be transported
                if (RNS.Reticulum.transport_enabled() or from_local_client or proof_for_local_client) and packet.destination_hash in Transport.reverse_table:
                    with Transport.reverse_table_lock: reverse_entry = Transport.reverse_table.pop(packet.destination_hash)
                    if packet.receiving_interface == reverse_entry[IDX_RT_OUTB_IF]:
                        RNS.log("Proof received on correct interface, transporting it via "+str(reverse_entry[IDX_RT_RCVD_IF]), RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        new_raw = packet.raw[0:1]
                        new_raw += struct.pack("!B", packet.hops if not from_local_client or proof_for_local_client or Transport.local_hops_delta == 0 else Transport.local_hops_delta)
                        new_raw += packet.raw[2:]
                        Transport.transmit(reverse_entry[IDX_RT_RCVD_IF], new_raw)
                    else:
                        RNS.log("Proof received on wrong interface, not transporting it.", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

                # TODO: Lock contention could be improved here
                # by a copy(), instead of running the list
                # comprehension under lock.
                with Transport.receipts_lock:
                    if proof_hash != None:
                        # Only test validation if hash matches
                        candidate_receipts = [r for r in Transport.receipts if r.hash == proof_hash]
                    else:
                        # In case of an implicit proof, we have
                        # to check every single outstanding receipt
                        candidate_receipts = Transport.receipts.copy()

                for receipt in candidate_receipts:
                    if receipt.status != RNS.PacketReceipt.SENT: continue
                    if receipt.validate_proof_packet(packet):
                        with Transport.receipts_lock:
                            if receipt in Transport.receipts: Transport.receipts.remove(receipt)

    #####################
    # Tunnel Management #
    #####################

    @staticmethod
    def synthesize_tunnel(interface):
        try:
            interface_hash = interface.get_hash()
            public_key     = RNS.Transport.identity.get_public_key()
            random_hash    = RNS.Identity.get_random_hash()
            
            tunnel_id_data = public_key+interface_hash
            tunnel_id      = RNS.Identity.full_hash(tunnel_id_data)

            signed_data    = tunnel_id_data+random_hash
            signature      = Transport.identity.sign(signed_data)
            
            data           = signed_data+signature

            tnl_snth_dst   = RNS.Destination(None, RNS.Destination.OUT, RNS.Destination.PLAIN, Transport.APP_NAME, "tunnel", "synthesize")

            packet = RNS.Packet(tnl_snth_dst, data, packet_type = RNS.Packet.DATA, transport_type = RNS.Transport.BROADCAST, header_type = RNS.Packet.HEADER_1, attached_interface = interface)
            packet.send()

            interface.wants_tunnel = False

        except Exception as e: RNS.log(f"Could not synthesize tunnel for {interface}: {e}", RNS.LOG_ERROR)

    @staticmethod
    def tunnel_synthesize_handler(data, packet):
        try:
            expected_length = RNS.Identity.KEYSIZE//8+RNS.Identity.HASHLENGTH//8+RNS.Reticulum.TRUNCATED_HASHLENGTH//8+RNS.Identity.SIGLENGTH//8
            if len(data) == expected_length:
                public_key     = data[:RNS.Identity.KEYSIZE//8]
                interface_hash = data[RNS.Identity.KEYSIZE//8:RNS.Identity.KEYSIZE//8+RNS.Identity.HASHLENGTH//8]
                tunnel_id_data = public_key+interface_hash
                tunnel_id      = RNS.Identity.full_hash(tunnel_id_data)
                random_hash    = data[RNS.Identity.KEYSIZE//8+RNS.Identity.HASHLENGTH//8:RNS.Identity.KEYSIZE//8+RNS.Identity.HASHLENGTH//8+RNS.Reticulum.TRUNCATED_HASHLENGTH//8]
                
                signature      = data[RNS.Identity.KEYSIZE//8+RNS.Identity.HASHLENGTH//8+RNS.Reticulum.TRUNCATED_HASHLENGTH//8:expected_length]
                signed_data    = tunnel_id_data+random_hash

                remote_transport_identity = RNS.Identity(create_keys=False)
                remote_transport_identity.load_public_key(public_key)

                if remote_transport_identity.validate(signature, signed_data):
                    Transport.handle_tunnel(tunnel_id, packet.receiving_interface)

        except Exception as e:
            RNS.log("An error occurred while validating tunnel establishment packet.", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
            RNS.log("The contained exception was: "+str(e), RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
            if packet.receiving_interface: packet.receiving_interface.protocol_violation("Invalid tunnel synthesis packet")

    @staticmethod
    def void_tunnel_interface(tunnel_id):
        with Transport.tunnels_lock:
            if tunnel_id in Transport.tunnels:
                RNS.log(f"Voiding tunnel interface {Transport.tunnels[tunnel_id][IDX_TT_IF]}", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                Transport.tunnels[tunnel_id][IDX_TT_IF] = None

    @staticmethod
    def handle_tunnel(tunnel_id, interface):
        expires = time.time() + Transport.TUNNEL_TIMEOUT
        if not tunnel_id in Transport.tunnels:
            RNS.log("Tunnel endpoint "+RNS.prettyhexrep(tunnel_id)+" established.", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
            paths = {}
            with Transport.tunnels_lock:
                tunnel_entry = [tunnel_id, interface, paths, expires]
                interface.tunnel_id = tunnel_id
                Transport.tunnels[tunnel_id] = tunnel_entry
        else:
            RNS.log("Tunnel endpoint "+RNS.prettyhexrep(tunnel_id)+" reappeared. Restoring paths...", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
            tunnel_entry = Transport.tunnels[tunnel_id]
            tunnel_entry[IDX_TT_IF] = interface
            tunnel_entry[IDX_TT_EXPIRES] = expires
            interface.tunnel_id = tunnel_id
            paths = tunnel_entry[IDX_TT_PATHS]

            deprecated_paths = []
            with Transport.tunnels_lock:
                for destination_hash, path_entry in paths.items():
                    path_timestamp = path_entry[0]
                    received_from = path_entry[1]
                    announce_hops = path_entry[2]
                    expires = path_entry[3]
                    random_blobs = list(set(path_entry[4]))
                    receiving_interface = interface
                    packet_hash = path_entry[6]
                    used = path_entry[7]
                    new_entry = [path_timestamp, received_from, announce_hops, expires, random_blobs, receiving_interface, packet_hash, used]

                    should_add = False
                    with Transport.path_table_lock:
                        if destination_hash in Transport.path_table:
                            old_entry = Transport.path_table[destination_hash]
                            old_hops = old_entry[IDX_PT_HOPS]
                            old_expires = old_entry[IDX_PT_EXPIRES]
                            if announce_hops <= old_hops or time.time() > old_expires:
                                current_random_blobs     = Transport.path_table[destination_hash][IDX_PT_RANDBLOBS]
                                current_path_timebase    = Transport.timebase_from_random_blobs(current_random_blobs)
                                tunnel_announce_timebase = Transport.timebase_from_random_blobs(random_blobs)
                                if tunnel_announce_timebase >= current_path_timebase: should_add = True
                                else: RNS.log("Did not restore path to "+RNS.prettyhexrep(destination_hash)+" because existing path is more recent", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                            else: RNS.log("Did not restore path to "+RNS.prettyhexrep(destination_hash)+" because a newer path with fewer hops exist", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                        
                        else:
                            if time.time() < expires: should_add = True
                            else: RNS.log("Did not restore path to "+RNS.prettyhexrep(destination_hash)+" because it has expired", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None

                    if should_add:
                        with Transport.path_table_lock: Transport.path_table[destination_hash] = new_entry
                        RNS.log("Restored path to "+RNS.prettyhexrep(destination_hash)+" is now "+str(announce_hops)+" hops away via "+RNS.prettyhexrep(received_from)+" on "+str(receiving_interface), RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                    
                    else: deprecated_paths.append(destination_hash)

            for deprecated_path in deprecated_paths:
                RNS.log("Removing path to "+RNS.prettyhexrep(deprecated_path)+" from tunnel "+RNS.prettyhexrep(tunnel_id), RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                with Transport.tunnels_lock: paths.pop(deprecated_path)

    ########################
    # Destination Handling #
    ########################

    @staticmethod
    def clean_destinations_map():
        with Transport.destinations_lock:
            for destination in Transport.destinations:
                with Transport.destinations_map_lock:
                    if not destination.hash in Transport.destinations_map:
                        Transport.destinations_map[destination.hash] = destination

        with Transport.destinations_map_lock:
            stale_destination_hashes = []
            for destination_hash in Transport.destinations_map:
                with Transport.destinations_lock:
                    found = False
                    for destination in Transport.destinations:
                        if destination.hash == destination_hash: found = True

                    if not found: stale_destination_hashes.append(destination_hash)

            for destination_hash in stale_destination_hashes:
                Transport.destinations_map.pop(destination_hash)

    @staticmethod
    def register_destination(destination):
        destination.MTU = RNS.Reticulum.MTU
        if destination.direction == RNS.Destination.IN:
            with Transport.destinations_lock:
                for registered_destination in Transport.destinations:
                    if destination.hash == registered_destination.hash:
                        raise KeyError("Attempt to register an already registered destination.")
                
                Transport.destinations.append(destination)

            with Transport.destinations_map_lock:
                Transport.destinations_map[destination.hash] = destination

            if Transport.owner.is_connected_to_shared_instance:
                if destination.type == RNS.Destination.SINGLE:
                    def job():
                        time.sleep(0.25)
                        destination.announce(path_response=True)
                    threading.Thread(target=job, daemon=True).start()

    @staticmethod
    def deregister_destination(destination):
        with Transport.destinations_lock:
            if destination in Transport.destinations: Transport.destinations.remove(destination)

        with Transport.destinations_map_lock:
            if destination.hash in Transport.destinations_map:
                Transport.destinations_map.pop(destination.hash)

    @staticmethod
    def register_announce_handler(handler):
        """
        Registers an announce handler.

        :param handler: Must be an object with an *aspect_filter* attribute and a *received_announce(destination_hash, announced_identity, app_data)*
                        or *received_announce(destination_hash, announced_identity, app_data, announce_packet_hash)* or
                        *received_announce(destination_hash, announced_identity, app_data, announce_packet_hash, is_path_response)* callable. Can
                        optionally have a *receive_path_responses* attribute set to ``True``, to also receive all path responses, in addition to live
                        announces. See the :ref:`Announce Example<example-announce>` for more info.
        """
        with Transport.announce_handler_lock:
            if hasattr(handler, "received_announce") and callable(handler.received_announce):
                if hasattr(handler, "aspect_filter"):
                    try:
                        name_hash = RNS.Destination.name_hash(handler.aspect_filter) if handler.aspect_filter else None
                        handler._rns_transport_cb_signature_len = len(inspect.signature(handler.received_announce).parameters)
                        if not hasattr(handler, "paused"): handler.paused = False
                        handlers = Transport.announce_handlers.get(name_hash, [])
                        if not handler in handlers: handlers.append(handler)
                        Transport.announce_handlers[name_hash] = handlers
                    except Exception as e:
                        RNS.log(f"Could not register announce handler for {handler.aspect_filter}: {e}", RNS.LOG_WARNING)
                        RNS.trace_exception(e)

    @staticmethod
    def deregister_announce_handler(handler):
        """
        Deregisters an announce handler.

        :param handler: The announce handler to be deregistered.
        """
        with Transport.announce_handler_lock:
            if hasattr(handler, "aspect_filter"):
                try:
                    name_hash = RNS.Destination.name_hash(handler.aspect_filter) if handler.aspect_filter else None
                    handlers = Transport.announce_handlers.get(name_hash, None)
                    if handlers:
                        while handler in handlers: handlers.remove(handler)
                        if handlers: Transport.announce_handlers[name_hash] = handlers
                        else: Transport.announce_handlers.pop(name_hash)
                except Exception as e:
                    RNS.log(f"Could not deregister announce handler for {handler.aspect_filter}: {e}", RNS.LOG_WARNING)
                    RNS.trace_exception(e)

        Transport.should_collect = True

    #################
    # Link Handling #
    #################

    @staticmethod
    def register_link(link):
        RNS.log("Registering link "+str(link), RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
        if link.initiator:
            with Transport.pending_links_lock:
                Transport.pending_links.append(link)
                Transport.pending_links_map[link.link_id] = link
        else:
            with Transport.active_links_lock:
                Transport.active_links.append(link)
                Transport.active_links_map[link.link_id] = link

    @staticmethod
    def activate_link(link):
        RNS.log("Activating link "+str(link), RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
        with Transport.pending_links_lock:
            if link in Transport.pending_links:
                if link.status != RNS.Link.ACTIVE: raise IOError("Invalid link state for link activation: "+str(link.status))
                Transport.pending_links.remove(link)
                Transport.pending_links_map.pop(link.link_id, None)
                with Transport.active_links_lock:
                    Transport.active_links.append(link)
                    Transport.active_links_map[link.link_id] = link

                link.status = RNS.Link.ACTIVE

            else: RNS.log("Attempted to activate a link that was not in the pending table", RNS.LOG_ERROR)

    ##################
    # Cache Handling #
    ##################

    @staticmethod
    def init_announce_cache():
        try:
            Transport.announce_cache = AnnounceCache(os.path.join(RNS.Reticulum.cachepath, "announces.db"))

            legacy_dir = os.path.join(RNS.Reticulum.cachepath, "announces")
            if os.path.isdir(legacy_dir) and len(os.listdir(legacy_dir)) > 0:
                st = time.time()
                imported = Transport.announce_cache.import_legacy(legacy_dir)
                RNS.log(f"Imported {imported} cached announces from legacy file storage in {RNS.prettyshorttime(time.time()-st)}", RNS.LOG_VERBOSE)

        except Exception as e:
            RNS.log("Could not initialise announce cache database, falling back to file-based caching. The contained exception was: "+str(e), RNS.LOG_ERROR)
            Transport.announce_cache = None

    @staticmethod
    def should_cache(packet):
        # TODO: Rework the caching system. It's currently
        # not very useful to even cache Resource proofs,
        # disabling it for now, until redesigned.
        # if packet.context == RNS.Packet.RESOURCE_PRF:
        #     return True

        return False

    @staticmethod
    def clean_cache():
        if not Transport.owner.is_connected_to_shared_instance:
            if Transport.cache_clean_lock.locked():
                RNS.log(f"Cache clean job still running, postponing until next scheduler interval", RNS.LOG_VERBOSE) if RNS.sl(RNS.LOG_VERBOSE) else None
            
            else:
                try:
                    acquired_lock = Transport.cache_clean_lock.acquire(blocking=False)
                    if acquired_lock:
                        Transport.clean_announce_cache()
                        Transport.cache_last_cleaned = time.time()

                except Exception as e:
                    RNS.log(f"An error occurred while launching the cache clean job. The contained exception was: {e}", RNS.LOG_ERROR)
                    RNS.trace_exception(e)

                finally:
                    if acquired_lock: Transport.cache_clean_lock.release()

    @staticmethod
    def clean_announce_cache():
        st = time.time()
        with Transport.path_table_lock: active_path_hashes = set([Transport.path_table[dst_hash][IDX_PT_PACKET] for dst_hash in Transport.path_table])
        with Transport.tunnels_lock:    tunnel_path_hashes = set([path_dict[dst_hash][IDX_PT_PACKET] for path_dict in [Transport.tunnels[tunnel_id][IDX_TT_PATHS] for tunnel_id in Transport.tunnels] for dst_hash in path_dict])
        active_path_hashes |= tunnel_path_hashes

        if Transport.announce_cache != None:
            removed = Transport.announce_cache.clean(active_path_hashes)
            if removed > 0: RNS.log(f"Removed {removed} cached announces in {RNS.prettytime(time.time()-st)}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
            return

        target_path = os.path.join(RNS.Reticulum.cachepath, "announces")
        cached_announce_hashes = os.listdir(target_path)
        removed = 0; total = 0
        for packet_hash in cached_announce_hashes:
            remove = False
            full_path = os.path.join(target_path, packet_hash)
            if os.path.isfile(full_path):
                try: target_hash = bytes.fromhex(packet_hash)
                except: remove = True
                if (not target_hash in active_path_hashes) and (not target_hash in tunnel_path_hashes): remove = True
                if remove: os.unlink(full_path); removed += 1
                total += 1

            # Low priority, yield thread
            time.sleep(0.001)

        if removed > 0: RNS.log(f"Removed {removed} cached announces in {RNS.prettytime(time.time()-st)}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

    # When caching packets to storage, they are written
    # exactly as they arrived over their interface. This
    # means that they have not had their hop count
    # increased yet! Take note of this when reading from
    # the packet cache.
    @staticmethod
    def cache(packet, force_cache=False, packet_type=None):
        if force_cache or Transport.should_cache(packet):
            try:
                interface_reference = None
                if packet.receiving_interface != None: interface_reference = str(packet.receiving_interface)

                if packet_type == "announce":
                    if Transport.announce_cache != None:
                        Transport.announce_cache.store(packet.get_hash(), packet.raw, interface_reference)
                        return

                    cachepath = os.path.join(RNS.Reticulum.cachepath, "announces", RNS.hexrep(packet.get_hash(), delimit=False))
                else:
                    cachepath = os.path.join(RNS.Reticulum.cachepath, RNS.hexrep(packet.get_hash(), delimit=False))

                file = open(cachepath, "wb")
                file.write(umsgpack.packb([packet.raw, interface_reference]))
                file.close()

            except Exception as e: RNS.log("Error writing packet to cache. The contained exception was: "+str(e), RNS.LOG_ERROR)

    @staticmethod
    def get_cached_packet(packet_hash, packet_type=None):
        try:
            if packet_type == "announce" and Transport.announce_cache != None:
                cached = Transport.announce_cache.fetch(packet_hash)
                if cached == None: return None

                packet = RNS.Packet(None, cached[0])
                interface_reference = cached[1]

                for interface in Transport.interfaces:
                    if str(interface) == interface_reference:
                        packet.receiving_interface = interface

                return packet

            packet_hash = RNS.hexrep(packet_hash, delimit=False)
            if packet_type == "announce": path = os.path.join(RNS.Reticulum.cachepath, "announces", packet_hash)
            else:                         path = os.path.join(RNS.Reticulum.cachepath, packet_hash)

            if os.path.isfile(path):
                file = open(path, "rb")
                cached_data = umsgpack.unpackb(file.read())
                file.close()

                packet = RNS.Packet(None, cached_data[0])
                interface_reference = cached_data[1]

                for interface in Transport.interfaces:
                    if str(interface) == interface_reference:
                        packet.receiving_interface = interface

                return packet

            else: return None
        
        except Exception as e:
            RNS.log("Exception occurred while getting cached packet.", RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
            return None

    @staticmethod
    def cache_request_packet(packet):
        if len(packet.data) == RNS.Identity.HASHLENGTH/8:
            packet = Transport.get_cached_packet(packet.data)

            if packet != None:
                # If the packet was retrieved from the local
                # cache, replay it to the Transport instance,
                # so that it can be directed towards it original
                # destination.
                Transport.inbound(packet.raw, packet.receiving_interface, ifac_handled=True)
                return True

            else: return False
        else: return False

    @staticmethod
    def cache_request(packet_hash, destination):
        cached_packet = Transport.get_cached_packet(packet_hash)
        if cached_packet:
            # The packet was found in the local cache,
            # replay it to the Transport instance.
            Transport.inbound(cached_packet.raw, cached_packet.receiving_interface, ifac_handled=True)
        else:
            # The packet is not in the local cache,
            # query the network.
            RNS.Packet(destination, packet_hash, context = RNS.Packet.CACHE_REQUEST).send()

    ###################
    # Various Helpers #
    ###################

    @staticmethod
    def has_path(destination_hash):
        """
        :param destination_hash: A destination hash as *bytes*.
        :returns: *True* if a path to the destination is known, otherwise *False*.
        """
        if destination_hash in Transport.path_table: return True
        else: return False

    @staticmethod
    def hops_to(destination_hash):
        """
        :param destination_hash: A destination hash as *bytes*.
        :returns: The number of hops to the specified destination, or ``RNS.Transport.PATHFINDER_M`` if the number of hops is unknown.
        """
        with Transport.path_table_lock:
            if destination_hash in Transport.path_table: return Transport.path_table[destination_hash][IDX_PT_HOPS]
            else: return Transport.PATHFINDER_M

    @staticmethod
    def next_hop(destination_hash):
        """
        :param destination_hash: A destination hash as *bytes*.
        :returns: The destination hash as *bytes* for the next hop to the specified destination, or *None* if the next hop is unknown.
        """
        with Transport.path_table_lock:
            if   destination_hash in Transport.path_table: return Transport.path_table[destination_hash][IDX_PT_NEXT_HOP]
            elif destination_hash in Transport.destinations_map: return Transport.identity.hash
            else: return None

    @staticmethod
    def next_hop_interface(destination_hash):
        """
        :param destination_hash: A destination hash as *bytes*.
        :returns: The interface for the next hop to the specified destination, or *None* if the interface is unknown.
        """
        with Transport.path_table_lock:
            if   destination_hash in Transport.path_table: return Transport.path_table[destination_hash][IDX_PT_RVCD_IF]
            elif destination_hash in Transport.destinations_map: return RNS.Reticulum.get_instance().shared_instance_interface
            else: return None

    @staticmethod
    def next_hop_interface_bitrate(destination_hash):
        next_hop_interface = Transport.next_hop_interface(destination_hash)
        if next_hop_interface != None: return next_hop_interface.bitrate
        else: return None

    @staticmethod
    def next_hop_interface_hw_mtu(destination_hash):
        next_hop_interface = Transport.next_hop_interface(destination_hash)
        if next_hop_interface != None:
            if next_hop_interface.AUTOCONFIGURE_MTU or next_hop_interface.FIXED_MTU: return next_hop_interface.HW_MTU
            else: return None
        
        else: return None

    @staticmethod
    def next_hop_per_bit_latency(destination_hash):
        next_hop_interface_bitrate = Transport.next_hop_interface_bitrate(destination_hash)
        if next_hop_interface_bitrate != None: return (1/next_hop_interface_bitrate)
        else: return None

    @staticmethod
    def next_hop_per_byte_latency(destination_hash):
        per_bit_latency = Transport.next_hop_per_bit_latency(destination_hash)
        if per_bit_latency != None: return per_bit_latency*8
        else: return None

    @staticmethod
    def first_hop_timeout(destination_hash):
        latency = Transport.next_hop_per_byte_latency(destination_hash)
        if latency != None: return RNS.Reticulum.MTU * latency + RNS.Reticulum.DEFAULT_PER_HOP_TIMEOUT
        else: return RNS.Reticulum.DEFAULT_PER_HOP_TIMEOUT

    @staticmethod
    def extra_link_proof_timeout(interface):
        if interface != None and interface.bitrate: return ((1/interface.bitrate)*8)*RNS.Reticulum.MTU
        else: return 0

    @staticmethod
    def medium_path_timeout():
        # A full round trip for an MTU on the slowest online interface
        if not Transport.lowest_interface_bitrate: return 0
        return 2*(RNS.Reticulum.MTU*8/max(Transport.lowest_interface_bitrate, RNS.Reticulum.MINIMUM_BITRATE)) + RNS.Reticulum.DEFAULT_PER_HOP_TIMEOUT

    @staticmethod
    def path_count():
        return len(Transport.path_table)

    @staticmethod
    def unused_path_count():
        with Transport.path_table_lock:
            return sum(1 for e in Transport.path_table.values() if not e[IDX_PT_USED])

    @staticmethod
    def path_pool_counts():
        with Transport.path_table_lock:
            total = len(Transport.path_table)
            unused = sum(1 for e in Transport.path_table.values() if not e[IDX_PT_USED])
        return total, unused

    @staticmethod
    def link_count():
        return len(Transport.link_table)

    @staticmethod
    def active_link_count():
        return sum(1 for e in (True for entry in Transport.link_table if entry[IDX_LT_VALIDATED]))

    @staticmethod
    def link_distribution():
        link_destinations = {}

        # TODO: Finish implementation
        return link_destinations

        # try:
        #     for link_id in Transport.link_table:
        #         link_entry = Transport.link_table.get(link_id)
        #         if link_entry:
        #             link_destination = link_entry[IDX_LT_DSTHASH]
        #             active           = link_entry[IDX_LT_VALIDATED]

        #             if not link_destination in link_destinations:
        #                 link_destinations[link_destination] = {}

        #             else:
        #                 pass

        # except Exception as e: RNS.log(f"Error while getting link distribution stats: {e}", RNS.LOG_DEBUG)

    #################
    # Path Handling #
    #################

    @staticmethod
    def expire_path(destination_hash):
        with Transport.path_table_lock:
            if destination_hash in Transport.path_table:
                Transport.path_table[destination_hash][IDX_PT_TIMESTAMP] = 0
                Transport.path_table[destination_hash][IDX_PT_EXPIRES] = 0
                Transport.tables_last_culled = 0
                return True
            
            else: return False

    @staticmethod
    def path_timeout_from_interface(interface):
        if interface != None and hasattr(interface, "mode"):
            if interface.mode == RNS.Interfaces.Interface.Interface.MODE_ACCESS_POINT: return Transport.AP_PATH_TIME
            elif interface.mode == RNS.Interfaces.Interface.Interface.MODE_ROAMING:    return Transport.ROAMING_PATH_TIME
        return Transport.PATH_TIMEOUT

    @staticmethod
    def mark_path_unresponsive(destination_hash):
        if destination_hash in Transport.path_table:
            with Transport.path_states_lock: Transport.path_states[destination_hash] = Transport.STATE_UNRESPONSIVE
            return True
        
        else: return False

    @staticmethod
    def mark_path_responsive(destination_hash):
        # Marking a path live must only occur on events that
        # cryptographically prove recent destination liveness.
        now = time.time()
        with Transport.path_table_lock:
            path_entry = Transport.path_table.get(destination_hash)
            if path_entry != None:
                path_entry[IDX_PT_TIMESTAMP] = now
                path_entry[IDX_PT_EXPIRES]   = now + Transport.path_timeout_from_interface(path_entry[IDX_PT_RVCD_IF])
                path_entry[IDX_PT_USED]      = now

                with Transport.path_states_lock:
                    Transport.path_states[destination_hash] = Transport.STATE_RESPONSIVE

                return True

            else: return False

    @staticmethod
    def mark_path_unknown_state(destination_hash):
        if destination_hash in Transport.path_table:
            with Transport.path_states_lock: Transport.path_states[destination_hash] = Transport.STATE_UNKNOWN
            return True
        
        else: return False

    @staticmethod
    def path_is_unresponsive(destination_hash):
        with Transport.path_states_lock:
            if destination_hash in Transport.path_states:
                if Transport.path_states[destination_hash] == Transport.STATE_UNRESPONSIVE:
                    return True

            return False

    @staticmethod
    def await_path(destination_hash, timeout=None, on_interface=None):
        """
        Requests a path to the destination from the network and
        blocks until the path is available, or the timeout is reached.

        :param destination_hash: A destination hash as *bytes*.
        :param timeout: An optional timeout in seconds.
        :param on_interface: If specified, the path request will only be sent on this interface. In normal use, Reticulum handles this automatically, and this parameter should not be used.
        :returns: *True* if a path to the destination is found, otherwise *False*.
        """
        timeout = time.time()+(timeout if timeout else Transport.PATH_REQUEST_TIMEOUT)
        if Transport.has_path(destination_hash): return True
        else: Transport.request_path(destination_hash, on_interface=on_interface)
        while not Transport.has_path(destination_hash) and time.time() < timeout: time.sleep(0.05)
        return Transport.has_path(destination_hash)

    @staticmethod
    def request_path(destination_hash, on_interface=None, tag=None, recursive=False, ext_payload=None):
        """
        Requests a path to the destination from the network. If
        another reachable peer on the network knows a path, it
        will announce it.

        :param destination_hash: A destination hash as *bytes*.
        :param on_interface: If specified, the path request will only be sent on this interface. In normal use, Reticulum handles this automatically, and this parameter should not be used.
        :param ext_payload: Internal use by :ref:`RNS.Transport<api-transport>`. Ignore.
        """
        if on_interface and recursive and on_interface.should_egress_limit_pr():
            RNS.log(f"Blocking recursive path request on {on_interface} due to active egress limiting", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
            return

        # From version 1.6.0, path requests always carry transport ID
        if tag == None: request_tag = RNS.Identity.get_random_hash()
        else:           request_tag = tag[:RNS.Identity.TRUNCATED_HASHLENGTH//8]
        path_request_data = destination_hash+Transport.identity.hash+request_tag

        # If a stamped extension is ready, include it
        if ext_payload != None: path_request_data += ext_payload

        # Otherwise, check if we need to include a PR stamp
        elif Transport.STAMP_PRS:
            material = Transport.pr_stamp_material(destination_hash, request_tag)
            with Transport.pr_stamp_cache_lock: stamp = Transport.pr_stamp_cache.get(material, None)

            # No cached stamp available, start generating
            if not stamp:
                with Transport.path_requests_lock: Transport.path_requests[destination_hash] = time.time()
                Transport.enqueue_stamped_pr(destination_hash, on_interface=on_interface, tag=request_tag, recursive=recursive)
                return

            # Cached stamp available, append for immediate dispatch
            else: path_request_data += bytes([RNS.Identity.EXTPAYLOADMARKER, 0x00])+stamp

        path_request_dst = RNS.Destination(None, RNS.Destination.OUT, RNS.Destination.PLAIN, Transport.APP_NAME, "path", "request")
        packet = RNS.Packet(path_request_dst, path_request_data, packet_type = RNS.Packet.DATA, transport_type = RNS.Transport.BROADCAST, header_type = RNS.Packet.HEADER_1, attached_interface = on_interface)

        if on_interface != None and recursive:
            if not hasattr(on_interface, "announce_cap"):        on_interface.announce_cap = RNS.Reticulum.ANNOUNCE_CAP/100.0
            if not hasattr(on_interface, "announce_allowed_at"): on_interface.announce_allowed_at = 0
            if not hasattr(on_interface, "announce_queue"):      on_interface.announce_queue = []

            queued_announces = True if len(on_interface.announce_queue) > 0 else False
            if queued_announces:
                RNS.log("Blocking recursive path request on "+str(on_interface)+" due to queued announces", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                return
            else:
                now = time.time()
                if now < on_interface.announce_allowed_at:
                    RNS.log("Blocking recursive path request on "+str(on_interface)+" due to active announce cap", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                    return
                else:
                    tx_time   = ((len(path_request_data)+RNS.Reticulum.HEADER_MINSIZE)*8) / on_interface.bitrate
                    wait_time = (tx_time / on_interface.announce_cap)
                    on_interface.announce_allowed_at = now + wait_time

        packet.is_outbound_pr = True
        with Transport.path_requests_lock: Transport.path_requests[destination_hash] = time.time()
        packet.send()

    @staticmethod
    def path_request_handler(data, packet):
        try:
            pr = Transport.parse_path_request(data)
            if pr == None:
                if len(data) >= RNS.Identity.TRUNCATED_HASHLENGTH//8:
                    destination_hash = data[:RNS.Identity.TRUNCATED_HASHLENGTH//8]
                    RNS.log("Ignoring tagless path request for "+RNS.prettyhexrep(destination_hash), RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                return

            destination_hash = pr[0]
            requesting_tid   = pr[1]
            tag_bytes        = pr[2]
            ext_payload      = pr[3]
            ingress_limited  = packet.traffic_class == Transport.TC_INGRESS_LIMITED

            Transport.path_request(destination_hash, Transport.from_local_client(packet), packet.receiving_interface,
                                   requestor_transport_id=requesting_tid, tag=tag_bytes, ingress_limited=ingress_limited,
                                   ext_payload=ext_payload)

        except Exception as e: RNS.log(f"Error while handling path request. The contained exception was: {e}", RNS.LOG_ERROR)

    @staticmethod
    def path_request(destination_hash, is_from_local_client, attached_interface, requestor_transport_id=None, tag=None, ingress_limited=False, ext_payload=None):
        should_search_for_unknown = False
        should_ingress_limit      = False
        search_mode_filter        = None
        answered                  = False

        if attached_interface != None:
            should_ingress_limit = ingress_limited or attached_interface.should_ingress_limit_pr()
            if RNS.Reticulum.transport_enabled():
                if attached_interface.recursive_prs: should_search_for_unknown = True
                elif attached_interface.mode in RNS.Interfaces.Interface.Interface.DISCOVER_PATHS_FOR: should_search_for_unknown = True
                elif attached_interface.mode == RNS.Interfaces.Interface.Interface.MODE_BOUNDARY:
                    should_search_for_unknown = True
                    search_mode_filter        = RNS.Interfaces.Interface.Interface.BOUNDARY_SEARCH_MODES

        if RNS.sl(RNS.LOG_PATHING):
            interface_str = f" on {attached_interface}"
            RNS.log(f"Path request for {RNS.prettyhexrep(destination_hash)}{interface_str}", RNS.LOG_PATHING)

        destination_exists_on_local_client = False
        if len(Transport.local_client_interfaces) > 0:
            if destination_hash in Transport.path_table:
                destination_interface = Transport.path_table[destination_hash][IDX_PT_RVCD_IF]
                
                if Transport.is_local_client_interface(destination_interface):
                    destination_exists_on_local_client = True
                    with Transport.pending_local_prs_lock:
                        Transport.pending_local_path_requests[destination_hash] = attached_interface
                        RNS.Reticulum.get_instance()._used_destination_data(destination_hash)

        local_destination = None
        with Transport.destinations_map_lock:
            if destination_hash in Transport.destinations_map: local_destination = Transport.destinations_map[destination_hash]

        if local_destination != None:
            answered = True
            local_destination.announce(path_response=True, tag=tag, attached_interface=attached_interface)
            RNS.log("Answering path request for "+RNS.prettyhexrep(destination_hash)+interface_str+", destination is local to this system", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None

        elif (RNS.Reticulum.transport_enabled() or is_from_local_client) and (destination_hash in Transport.path_table):
            packet = Transport.get_cached_packet(Transport.path_table[destination_hash][IDX_PT_PACKET], packet_type="announce")
            next_hop = Transport.path_table[destination_hash][IDX_PT_NEXT_HOP]
            received_from = Transport.path_table[destination_hash][IDX_PT_RVCD_IF]
            answered = True

            if packet == None:
                RNS.log(f"Could not retrieve announce packet from cache while answering path request for {RNS.prettyhexrep(destination_hash)}, ignoring path request", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

            elif attached_interface.mode == RNS.Interfaces.Interface.Interface.MODE_ROAMING and attached_interface == received_from:
                RNS.log("Not answering path request on roaming-mode interface, since next hop is on same roaming-mode interface", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None

            else:
                if not packet.unpack(): return
                packet.hops = Transport.path_table[destination_hash][IDX_PT_HOPS]

                if requestor_transport_id != None and next_hop == requestor_transport_id:
                    # TODO: Find a bandwidth efficient way to invalidate our
                    # known path on this signal. The obvious way of signing
                    # path requests with transport instance keys is quite
                    # inefficient. There is probably a better way. Doing
                    # path invalidation here would decrease the network
                    # convergence time. Maybe just drop it?
                    RNS.log("Not answering path request for "+RNS.prettyhexrep(destination_hash)+interface_str+", since next hop is the requestor", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                else:
                    RNS.log("Answering path request for "+RNS.prettyhexrep(destination_hash)+interface_str+", path is known", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None

                    now = time.time()
                    retries = Transport.PATHFINDER_R
                    local_rebroadcasts = 0
                    block_rebroadcasts = True
                    announce_hops      = packet.hops

                    if is_from_local_client:
                        retransmit_timeout = now
                    else:
                        if Transport.is_local_client_interface(Transport.next_hop_interface(destination_hash)):
                            RNS.log("Path request destination "+RNS.prettyhexrep(destination_hash)+" is on a local client interface, rebroadcasting immediately", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                            retransmit_timeout = now

                        else:
                            retransmit_timeout = now + Transport.PATH_REQUEST_GRACE

                            # If we are answering on a roaming-mode interface, wait a
                            # little longer, to allow potential more well-connected
                            # peers to answer first.
                            if attached_interface.mode == RNS.Interfaces.Interface.Interface.MODE_ROAMING:
                                retransmit_timeout += Transport.PATH_REQUEST_RG

                    # This handles an edge case where a peer sends a past
                    # request for a destination just after an announce for
                    # said destination has arrived, but before it has been
                    # rebroadcast locally. In such a case the actual announce
                    # is temporarily held, and then reinserted when the path
                    # request has been served to the peer.
                    if packet.destination_hash in Transport.announce_table:
                        held_entry = Transport.announce_table[packet.destination_hash]
                        Transport.held_announces[packet.destination_hash] = held_entry
                    
                    with Transport.announce_table_lock:
                        Transport.announce_table[packet.destination_hash] = [now, retransmit_timeout, retries, received_from, announce_hops, packet, local_rebroadcasts, block_rebroadcasts, attached_interface]

                    if not Transport.owner.is_connected_to_shared_instance: RNS.Identity._used_destination_data(packet.destination_hash)

        elif is_from_local_client:
            # Forward path request on all interfaces
            # except the local client
            RNS.log(f"Forwarding path request from local client for {RNS.prettyhexrep(destination_hash)+interface_str} to all other interfaces", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
            for interface in Transport.interfaces:
                if not interface == attached_interface:
                    Transport.request_path(destination_hash, interface, tag=tag, ext_payload=ext_payload)

        elif should_search_for_unknown:
            with Transport.discovery_pr_lock:
                if destination_hash in Transport.discovery_path_requests:
                    discovery_path_request_exists  = True
                    path_request_engaged           = Transport.discovery_path_requests[destination_hash]["engaged"]
                else:
                    discovery_path_request_exists  = False
                    path_request_engaged           = False

            if discovery_path_request_exists and path_request_engaged: RNS.log("There is already a waiting path request for "+RNS.prettyhexrep(destination_hash)+" on behalf of path request"+interface_str, RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
            else:
                # Sentinel check for potential enforcement logic leaks.
                # This branch should never fire, but better have it made
                # visible and explicit if for some unexpected reason it does.
                if ext_payload == None and Transport.STAMPS_ENFORCED:
                    # TODO: Remove *after* enforcement transition and verification.
                    RNS.log(f"Reached rebroadcast decision for unstamped path request for {RNS.prettyhexrep(destination_hash)} under stamp enforcement. This should not happen.", RNS.LOG_CRITICAL)
                    return

                # Abort recursive path request if receiving
                # interface has PR burst active, or should
                # otherwise ingress limit path requests.
                if should_ingress_limit:
                    if RNS.sl(RNS.LOG_PATHING):
                        interface_str = f" for {attached_interface}" if attached_interface else ""
                        RNS.log(f"Not sending recursive path request{interface_str} due to active ingress limiting", RNS.LOG_PATHING)
                    return

                # Forward path request on all interfaces
                # except the requestor interface. The discovery
                # timeout must also cover a full round trip for
                # an MTU on the slowest online interface.
                discovery_timeout = max(Transport.PATH_REQUEST_TIMEOUT, Transport.medium_path_timeout())

                RNS.log("Attempting to discover unknown path to "+RNS.prettyhexrep(destination_hash)+" on behalf of path request"+interface_str, RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
                pr_entry = { "destination_hash": destination_hash, "timeout": time.time()+discovery_timeout,
                             "requesting_interfaces": None, "engaged": True }

                with Transport.discovery_pr_lock:
                    existing_requesting_interfaces = []
                    if destination_hash in Transport.discovery_path_requests:
                        existing_requesting_interfaces = Transport.discovery_path_requests[destination_hash]["requesting_interfaces"]

                    if not attached_interface in existing_requesting_interfaces:
                        existing_requesting_interfaces.append(attached_interface)
                    pr_entry["requesting_interfaces"] = existing_requesting_interfaces

                    Transport.discovery_path_requests[destination_hash] = pr_entry

                # TODO: Remove
                # Don't generate stamps for non-stamped recursive
                # path requests received from non-stamping nodes
                # during the transition period where this node may
                # be stamping, but still accepting unstamped PRs.
                if ext_payload == None and Transport.STAMP_PRS:
                    ext_payload = bytes([RNS.Identity.EXTPAYLOADMARKER, 0xFF])+bytes(RNS.Identity.STAMPLENGTH)

                for interface in Transport.interfaces:
                    if search_mode_filter and not interface.mode in search_mode_filter: continue
                    if not interface.online: continue
                    if not interface == attached_interface:
                        if interface.should_egress_limit_pr():
                            RNS.log(f"Not sending recursive path request on {interface} due to active egress limiting", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        else:
                            # Use the previously extracted tag from this path request
                            # on the new path requests as well, to avoid potential loops
                            Transport.request_path(destination_hash, on_interface=interface, tag=tag, recursive=True, ext_payload=ext_payload)

        elif not is_from_local_client and len(Transport.local_client_interfaces) > 0:
            # TODO: Remove
            # Don't generate stamps for non-stamped external
            # path requests received from non-stamping nodes
            # during the transition period where this node may
            # be stamping, but still accepting unstamped PRs.
            if ext_payload == None and Transport.STAMP_PRS:
                ext_payload = bytes([RNS.Identity.EXTPAYLOADMARKER, 0xFF])+bytes(RNS.Identity.STAMPLENGTH)

            # Forward the path request on all local client interfaces
            RNS.log(f"Forwarding path request for {RNS.prettyhexrep(destination_hash)}{interface_str} to local clients", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
            for interface in Transport.local_client_interfaces:
                Transport.request_path(destination_hash, on_interface=interface, tag=tag, ext_payload=ext_payload)
        else:
            RNS.log(f"Ignoring path request for {RNS.prettyhexrep(destination_hash)}{interface_str}, no path known", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None

        if answered:
            # Resolve potential in-flight path requests
            with Transport.inflight_path_requests_lock:
                if destination_hash in Transport.inflight_path_requests:
                    Transport.inflight_path_requests.pop(destination_hash)

    ########################
    # Path Request Helpers #
    ########################

    PR_EXT_HEADERLENGTH  = 2
    PR_EXT_STAMPLENGTH   = RNS.Identity.STAMPLENGTH
    PR_EXT_PAYLOADLENGTH = PR_EXT_HEADERLENGTH+PR_EXT_STAMPLENGTH
    PR_LENGTH            = 3*RNS.Identity.TRUNCATED_HASHLENGTH//8
    PR_STAMPED_LENGTH    = PR_LENGTH+PR_EXT_PAYLOADLENGTH
    PR_LEGACY_LENGTH     = 2*RNS.Identity.TRUNCATED_HASHLENGTH//8 # TODO: Remove after transition
    @staticmethod
    def parse_path_request(data):
        DL = RNS.Identity.TRUNCATED_HASHLENGTH//8
        if len(data) < DL: return None
        destination_hash = data[:DL]

        # Stamped 1.6.0+ format (dst_hash|tid|tag|ext)
        if len(data) == Transport.PR_STAMPED_LENGTH:
            return (destination_hash, data[DL:DL*2], data[DL*2:DL*3], data[DL*3:])

        # TODO: Remove after transition
        # Unstamped, pre 1.6.0 format (dst_hash|tid|tag),
        # potentially variable tag size, although RNS will
        # always emit 16-byte tags. Truncates oversized tags.
        elif len(data) > DL*2:
            tag = data[DL*2:]
            if len(tag) > DL: tag = tag[:DL]
            return (destination_hash, data[DL:DL*2], tag, None)

        # TODO: Remove after transition
        # Legacy format without transport ID, but with tag
        elif len(data) > DL: return (destination_hash, None, data[DL:], None)

        # Ancient tagless path request, invalid
        else: return None

    @staticmethod
    def pr_stamp_material(destination_hash, tag):
        return destination_hash+tag

    @staticmethod
    def validate_pr_stamp(stamp, destination_hash, tag, required_value=None):
        if required_value == None: required_value = Transport.PR_COST
        if not stamp or len(stamp) != RNS.Identity.STAMPLENGTH: return False
        workblock = stamp_workblock(Transport.pr_stamp_material(destination_hash, tag), expand_rounds=0)
        return stamp_valid(stamp, required_value, workblock)

    @staticmethod
    def stamp_path_request(destination_hash, on_interface=None, tag=None, recursive=False, return_payload=False):
        if tag == None: request_tag = RNS.Identity.get_random_hash()
        else:           request_tag = tag

        material = Transport.pr_stamp_material(destination_hash, request_tag)
        with Transport.pr_stamp_cache_lock: stamp = Transport.pr_stamp_cache.get(material, None)

        if not stamp:
            stamp_status = None
            stamp_job_id = material
            def stamp_watchdog():
                deadline = time.time() + RNS.Transport.PR_STAMP_TIMEOUT
                while stamp_status == None and time.time() <= deadline: time.sleep(1)
                if time.time() > deadline and stamp_job_id and not stamp_status: cancel_work(stamp_job_id)

            threading.Thread(target=stamp_watchdog, daemon=True).start()
            stamp, value = generate_stamp(material, stamp_cost=Transport.PR_VALUE, expand_rounds=0, size=RNS.Identity.STAMPLENGTH)
            stamp_job_id = None

        if stamp: stamp_status = True
        else:
            stamp_status = False
            RNS.log(f"Could not generate path request stamp for {RNS.prettyhexrep(destination_hash)}, path request emission cancelled", RNS.LOG_WARNING)
            return

        with Transport.pr_stamp_cache_lock:
            Transport.pr_stamp_cache[material] = stamp
            while len(Transport.pr_stamp_cache) > Transport.pr_stamp_cache_max:
                Transport.pr_stamp_cache.pop(next(iter(Transport.pr_stamp_cache)))

        ext_payload = bytes([RNS.Identity.EXTPAYLOADMARKER, 0x00])+stamp
        if return_payload: return request_tag, ext_payload
        else: Transport.request_path(destination_hash, on_interface=on_interface, tag=request_tag, recursive=recursive, ext_payload=ext_payload)

    discovery_pr_tx_throttle = 0.5
    discovery_pr_tx_lock     = Lock()
    discovery_pr_handle_lock = Lock()
    pending_discovery_prs    = deque(maxlen=max_queued_discovery_prs)
    @staticmethod
    def handle_disovery_path_requests():
        if Transport.discovery_pr_handle_lock.locked(): return
        with Transport.discovery_pr_handle_lock:
            while len(Transport.pending_discovery_prs):
                time.sleep(Transport.discovery_pr_tx_throttle)
                destination_hash = None
                blocked_if = None
                with Transport.discovery_pr_tx_lock:
                    entry = Transport.pending_discovery_prs.popleft()
                    destination_hash = entry[0]
                    blocked_if = entry[1]

                if destination_hash:
                    if blocked_if == None: Transport.request_path(destination_hash)
                    else:
                        request_tag = RNS.Identity.get_random_hash()
                        ext_payload = None
                        if Transport.STAMP_PRS:
                            RNS.log(f"Stamping discovery path request for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                            request_tag, ext_payload = Transport.stamp_path_request(destination_hash, tag=request_tag, return_payload=True)

                        for interface in Transport.interfaces:
                            if interface != blocked_if: Transport.request_path(destination_hash, on_interface=interface, tag=request_tag, ext_payload=ext_payload)
                            else: pass

    #################################
    # Interface helpers & utilities #
    #################################

    @staticmethod
    def from_local_client(packet):
        if hasattr(packet.receiving_interface, "parent_interface"):
            return Transport.is_local_client_interface(packet.receiving_interface)
        else: return False

    @staticmethod
    def is_local_client_interface(interface):
        if hasattr(interface, "parent_interface"):
            if hasattr(interface.parent_interface, "is_local_shared_instance"): return True
            else:                                                               return False
        else:                                                                   return False

    @staticmethod
    def is_shared_instance(interface):
        if hasattr(interface, "is_local_shared_instance"): return True
        else:                                              return False

    @staticmethod
    def interface_to_shared_instance(interface):
        if hasattr(interface, "is_connected_to_shared_instance"): return True
        else:                                                     return False

    @staticmethod
    def interface_hashes():
        return {interface.get_hash() for interface in Transport.interfaces}

    @staticmethod
    def find_interface_from_hash(interface_hash):
        for interface in Transport.interfaces:
            if interface.get_hash() == interface_hash:
                return interface

        return None

    @staticmethod
    def detach_interfaces():
        closed_links = 0
        for link in Transport.active_links.copy():
            try: link.teardown(); closed_links += 1
            except Exception as e: RNS.log(f"Could not tear down active link before interface detach: {e}", RNS.LOG_WARNING)

        for link in Transport.pending_links.copy():
            try: link.teardown(); closed_links += 1
            except Exception as e: RNS.log(f"Could not tear down pending link before interface detach: {e}", RNS.LOG_WARNING)

        # Provide a 150ms window to allow link teardown
        # packets to leave local transport
        if closed_links: time.sleep(0.15)

        detachable_interfaces = []

        for interface in Transport.interfaces:
            # Currently no rules are being applied
            # here, and all interfaces will be sent
            # the detach call on RNS teardown.
            if not interface.detached: detachable_interfaces.append(interface)
            else: pass
        
        for interface in Transport.local_client_interfaces:
            # Currently no rules are being applied
            # here, and all interfaces will be sent
            # the detach call on RNS teardown.
            if not interface.detached: detachable_interfaces.append(interface)
            else: pass

        shared_instance_master = None
        local_interfaces = []
        detach_threads = []
        RNS.log("Detaching interfaces", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
        for interface in detachable_interfaces:
            try:
                if type(interface) == RNS.Interfaces.LocalInterface.LocalServerInterface:
                    shared_instance_master = interface
                elif type(interface) == RNS.Interfaces.LocalInterface.LocalClientInterface:
                    local_interfaces.append(interface)
                else:
                    def detach_job(interface=interface):
                        RNS.log(f"Detaching {interface}", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        interface.detach()
                    dt = threading.Thread(target=detach_job, daemon=False)
                    dt.start()
                    detach_threads.append(dt)

            except Exception as e:
                RNS.log("An error occurred while detaching "+str(interface)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

        for dt in detach_threads:
            dt.join()

        RNS.log("Detaching local clients", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
        for li in local_interfaces:
            li.detach()

        RNS.log("Detaching shared instance", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
        if shared_instance_master != None: shared_instance_master.detach()
        BackboneInterface.deregister_listeners()

        RNS.log("All interfaces detached", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

    @staticmethod
    def shared_connection_disappeared():
        with Transport.active_links_lock:
            for link in Transport.active_links: link.teardown()

        with Transport.pending_links_lock:
            for link in Transport.pending_links: link.teardown()

        Transport.announce_table    = {}
        Transport.path_table        = {}
        Transport.reverse_table     = {}
        Transport.link_table        = {}
        Transport.held_announces    = {}
        Transport.tunnels           = {}

    @staticmethod
    def shared_connection_reappeared():
        if Transport.owner.is_connected_to_shared_instance:
            for registered_destination in Transport.destinations.copy():
                if registered_destination.type == RNS.Destination.SINGLE:
                    registered_destination.announce(path_response=True)

    ####################
    # Announce Helpers #
    ####################

    @staticmethod
    def drop_announce_queues():
        for interface in Transport.interfaces:
            if hasattr(interface, "announce_queue") and interface.announce_queue != None:
                na = len(interface.announce_queue)
                if na > 0:
                    if na == 1: na_str = "1 announce"
                    else: na_str = str(na)+" announces"
                    interface.announce_queue = []
                    RNS.log("Dropped "+na_str+" on "+str(interface), RNS.LOG_VERBOSE) if RNS.sl(RNS.LOG_VERBOSE) else None

        Transport.should_collect = True

    @staticmethod
    def timebase_from_random_blob(random_blob):
        return int.from_bytes(random_blob[5:10], "big")

    @staticmethod
    def timebase_from_random_blobs(random_blobs):
        timebase = 0
        for random_blob in random_blobs:
            emitted = Transport.timebase_from_random_blob(random_blob)
            if emitted > timebase: timebase = emitted

        return timebase

    @staticmethod
    def announce_emitted(packet):
        random_blob = packet.data[RNS.Identity.KEYSIZE//8+RNS.Identity.NAME_HASH_LENGTH//8:RNS.Identity.KEYSIZE//8+RNS.Identity.NAME_HASH_LENGTH//8+10]
        announce_emitted = Transport.timebase_from_random_blob(random_blob)

        return announce_emitted

    #####################
    # State Persistence #
    #####################

    @staticmethod
    def save_packet_hashlist(background=False):
        if not Transport.owner.is_connected_to_shared_instance:
            if not RNS.Reticulum.transport_enabled(): return
            if hasattr(Transport, "saving_packet_hashlist"):
                wait_interval = 0.2
                wait_timeout = 5
                wait_start = time.time()
                while Transport.saving_packet_hashlist:
                    time.sleep(wait_interval)
                    if time.time() > wait_start+wait_timeout:
                        RNS.log("Could not save packet hashlist to storage, waiting for previous save operation timed out.", RNS.LOG_ERROR)
                        return False

            try:
                Transport.saving_packet_hashlist = True
                save_start = time.time()

                if RNS.Reticulum.transport_enabled(): RNS.log("Saving packet hashlist to storage...", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                else: return

                round_started_at = save_start
                yield_threshold  = 0.010

                packet_hashlist_path = RNS.Reticulum.storagepath+"/packet_hashlist.raw"
                with open(packet_hashlist_path, "wb") as file:
                    for bucket in Transport.packet_hashlist.buckets():
                        if background:
                            if time.time() - round_started_at > yield_threshold:
                                # Low priority, yield thread
                                round_started_at = time.time()
                                time.sleep(0.001)

                        file.write(bucket)

                RNS.log(f"Saved packet hashlist in {RNS.prettyshorttime(time.time()-save_start)}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

            except Exception as e: RNS.log("Could not save packet hashlist to storage, the contained exception was: "+str(e), RNS.LOG_ERROR)
            finally: Transport.saving_packet_hashlist = False

    @staticmethod
    def save_path_table(background=False):
        if not Transport.owner.is_connected_to_shared_instance:
            if hasattr(Transport, "saving_path_table"):
                wait_interval = 0.2
                wait_timeout = 5
                wait_start = time.time()
                while Transport.saving_path_table:
                    time.sleep(wait_interval)
                    if time.time() > wait_start+wait_timeout:
                        RNS.log("Could not save path table to storage, waiting for previous save operation timed out.", RNS.LOG_ERROR)
                        return False

            try:
                Transport.saving_path_table = True
                save_start = time.time()
                RNS.log("Saving path table to storage...", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

                serialised_destinations     = []
                path_table                  = Transport.path_table.copy()
                interface_hashes_updated_at = 0
                round_started_at            = save_start
                yield_threshold             = 0.010

                for destination_hash in path_table:
                    if background:
                        if time.time() - round_started_at > yield_threshold:
                            # Low priority, yield thread
                            round_started_at = time.time()
                            time.sleep(0.001)
                    try:
                        # Throttle interface hash lookup to 2 seconds
                        if time.time() > interface_hashes_updated_at + 2:
                            interface_hashes = Transport.interface_hashes()
                            interface_hashes_updated_at = time.time()

                        # Get the destination entry from the destination table
                        de        = path_table[destination_hash]
                        interface = de[IDX_PT_RVCD_IF]

                        # Only store destination table entry if the associated
                        # interface is still active
                        if not interface.get_hash() in interface_hashes: RNS.log(f"Skipping persist for path table entry {RNS.prettyhexrep(destination_hash)}, interface {interface} no longer active", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                        else:
                            # Get the destination entry from the destination table
                            if not destination_hash in path_table:
                                RNS.log(f"Skipping persist for path table entry {RNS.prettyhexrep(destination_hash)}, no longer in table", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None

                            de             = path_table[destination_hash]
                            timestamp      = de[IDX_PT_TIMESTAMP]
                            received_from  = de[IDX_PT_NEXT_HOP]
                            hops           = de[IDX_PT_HOPS]
                            expires        = de[IDX_PT_EXPIRES]
                            random_blobs   = de[IDX_PT_RANDBLOBS]
                            packet_hash    = de[IDX_PT_PACKET]
                            used           = de[IDX_PT_USED]
                            interface_hash = interface.get_hash()

                            serialised_entry = [ destination_hash,
                                                 timestamp,
                                                 received_from,
                                                 hops,
                                                 expires,
                                                 random_blobs,
                                                 interface_hash,
                                                 packet_hash,
                                                 used ]

                            serialised_destinations.append(serialised_entry)

                            # TODO: Reevaluate whether there is any cases where this is needed
                            # Transport.cache(de[IDX_PT_PACKET], force_cache=True)

                    except Exception as e: RNS.log(f"Skipping persist for path table entry due to error: {e}", RNS.LOG_ERROR)

                path_table_path = RNS.Reticulum.storagepath+"/destination_table"
                file = open(path_table_path, "wb")
                file.write(umsgpack.packb(serialised_destinations))
                file.close()

                save_time = time.time() - save_start
                if save_time < 1: time_str = str(round(save_time*1000,2))+"ms"
                else: time_str = str(round(save_time,2))+"s"
                RNS.log("Saved "+str(len(serialised_destinations))+" path table entries in "+time_str, RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

            except Exception as e:
                RNS.log("Could not save path table to storage, the contained exception was: "+str(e), RNS.LOG_ERROR)
                RNS.trace_exception(e)

            Transport.saving_path_table = False

    @staticmethod
    def save_tunnel_table(background=False):
        if not Transport.owner.is_connected_to_shared_instance:
            if hasattr(Transport, "saving_tunnel_table"):
                wait_interval = 0.2
                wait_timeout = 5
                wait_start = time.time()
                while Transport.saving_tunnel_table:
                    time.sleep(wait_interval)
                    if time.time() > wait_start+wait_timeout:
                        RNS.log("Could not save tunnel table to storage, waiting for previous save operation timed out.", RNS.LOG_ERROR)
                        return False

            try:
                Transport.saving_tunnel_table = True
                save_start = time.time()
                RNS.log("Saving tunnel table to storage...", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

                serialised_tunnels = []
                round_started_at   = save_start
                yield_threshold    = 0.010

                for tunnel_id in Transport.tunnels.copy():
                    if background:
                        if time.time() - round_started_at > yield_threshold:
                            # Low priority, yield thread
                            round_started_at = time.time()
                            time.sleep(0.001)

                    te = Transport.tunnels[tunnel_id]
                    interface = te[1]
                    tunnel_paths = te[2].copy()
                    expires = te[3]

                    if interface != None: interface_hash = interface.get_hash()
                    else: interface_hash = None

                    serialised_paths = []
                    for destination_hash in tunnel_paths:
                        de = tunnel_paths[destination_hash]

                        timestamp = de[0]
                        received_from = de[1]
                        hops = de[2]
                        path_expires = de[3]
                        random_blobs = de[4][-Transport.PERSIST_RANDOM_BLOBS:]
                        packet_hash = de[6]
                        used = de[7]

                        serialised_entry = [
                            destination_hash,
                            timestamp,
                            received_from,
                            hops,
                            path_expires,
                            random_blobs,
                            interface_hash,
                            packet_hash,
                            used,
                        ]

                        serialised_paths.append(serialised_entry)

                        # TODO: Reevaluate whether there are any cases where this is needed
                        # Transport.cache(de[6], force_cache=True)

                    serialised_tunnel = [tunnel_id, interface_hash, serialised_paths, expires]
                    serialised_tunnels.append(serialised_tunnel)

                tunnels_path = RNS.Reticulum.storagepath+"/tunnels"
                file = open(tunnels_path, "wb")
                file.write(umsgpack.packb(serialised_tunnels))
                file.close()

                save_time = time.time() - save_start
                if save_time < 1: time_str = str(round(save_time*1000,2))+"ms"
                else: time_str = str(round(save_time,2))+"s"
                RNS.log("Saved "+str(len(serialised_tunnels))+" tunnel table entries in "+time_str, RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
            
            except Exception as e:
                RNS.log("Could not save tunnel table to storage, the contained exception was: "+str(e), RNS.LOG_ERROR)

            Transport.saving_tunnel_table = False

    @staticmethod
    def persist_data(background=False):
        if Transport.persist_lock.locked(): return
        with Transport.persist_lock:
            Transport.save_packet_hashlist(background=background)
            Transport.save_path_table(background=background)
            Transport.save_tunnel_table(background=background)

    ########################
    # Blackhole Management #
    ########################

    @staticmethod
    def blackhole_identity(identity_hash, until=None, reason=None):
        """
        Blackholes an identity.

        :param identity_hash: The identity hash to blackhole as *bytes*.
        :param until: Optional unix timestamp of when the blackhole expires as *float* or *int*.
        :param reason: Optional reason for the blackhole as *str*.
        :returns: *True* if successful, otherwise *False*.
        """
        try:
            if not identity_hash in Transport.blackholed_identities:
                entry = {"source": Transport.identity.hash, "until": until, "reason": reason}
                Transport.blackholed_identities[identity_hash] = entry
                Transport.persist_blackhole()
                Transport.remove_blackholed_paths()
                RNS.Identity._reset_validation_caches()
                RNS.log(f"Blackholed identity {RNS.prettyhexrep(identity_hash)}", RNS.LOG_INFO)
                return True

            else: return None
        
        except Exception as e:
            RNS.log(f"Error while blackholing identity: {e}", RNS.LOG_ERROR)
            return False

    @staticmethod
    def unblackhole_identity(identity_hash):
        """
        Lifts blackhole for an identity.

        :param identity_hash: The identity hash to blackhole as *bytes*.
        :returns: *True* if successful, otherwise *False*.
        """
        try:
            if identity_hash in Transport.blackholed_identities:
                Transport.blackholed_identities.pop(identity_hash)
                Transport.persist_blackhole()
                RNS.Identity._reset_validation_caches()
                RNS.log(f"Lifted blackhole for identity {RNS.prettyhexrep(identity_hash)}", RNS.LOG_INFO)
                return True

            else: return None

        except Exception as e:
            RNS.log(f"Error while unblackholing identity: {e}", RNS.LOG_ERROR)
            return False

    @staticmethod
    def reload_blackhole():
        now = time.time()
        source_count = 0
        dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH//8)*2
        for filename in os.listdir(RNS.Reticulum.blackholepath):
            try:
                if filename == "local": source_identity_hash = Transport.identity.hash
                else:
                    if len(filename) != dest_len: raise ValueError(f"Identity hash length for blackhole source {filename} is invalid")
                    source_identity_hash = bytes.fromhex(filename)
                    if not source_identity_hash in RNS.Reticulum.blackhole_sources():
                        RNS.log(f"Skipping disabled blackhole source {RNS.prettyhexrep(source_identity_hash)}", RNS.LOG_VERBOSE) if RNS.sl(RNS.LOG_VERBOSE) else None
                        continue

                sourcepath = os.path.join(RNS.Reticulum.blackholepath, filename)
                with open(sourcepath, "rb") as f:
                    packed = f.read()
                    source_list = umsgpack.unpackb(packed)
                    for identity_hash in source_list:
                        if len(identity_hash) == RNS.Reticulum.TRUNCATED_HASHLENGTH//8:
                            if identity_hash in Transport.blackholed_identities:
                                if Transport.blackholed_identities[identity_hash]["source"] == Transport.identity.hash:
                                    continue
                            
                            se        = source_list[identity_hash]
                            until     = se["until"] if "until" in se else None
                            reason    = se["reason"] if "reason" in se else None
                            entry     = {"source": source_identity_hash, "until": until, "reason": reason}
                            
                            if until == None or now < until: Transport.blackholed_identities[identity_hash] = entry

                source_count += 1

            except Exception as e:
                RNS.log(f"Could not load blackholed identities from source file {filename}: {e}", RNS.LOG_ERROR)
                RNS.trace_exception(e)

        RNS.Identity._reset_validation_caches()
        Transport.remove_blackholed_paths()

    @staticmethod
    def remove_blackholed_paths():
        drop_destinations = []
        for destination_hash in Transport.path_table.copy():
            try:
                associated_identity = RNS.Identity.recall(destination_hash, _no_use=True)
                if associated_identity and associated_identity.hash in Transport.blackholed_identities:
                    if not destination_hash in drop_destinations: drop_destinations.append(destination_hash)
            except Exception as e:
                RNS.log(f"Error while enumerating blackhole-associated destinations: {e}", RNS.LOG_ERROR)

        for destination_hash in drop_destinations:
            try:
                with Transport.path_table_lock:
                    if destination_hash in Transport.path_table: Transport.path_table.pop(destination_hash)
            except Exception as e:
                RNS.log(f"Error while dropping blackhole-associated destination from path table: {e}", RNS.LOG_ERROR)

        if len(drop_destinations) > 0:
            ms = "" if len(drop_destinations) == 1 else "s"
            RNS.log(f"Removed {len(drop_destinations)} destination{ms} associated with blackholed identities from path table", RNS.LOG_INFO)

    @staticmethod
    def blackhole_list_handler(path, data, request_id, link_id, remote_identity, requested_at):
        try: return Transport.blackholed_identities
        except Exception as e:
            RNS.log("An error occurred while processing blackhole list request from "+str(remote_identity), RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)

        return None

    @staticmethod
    def persist_blackhole():
        try:
            local_blackhole = {}
            for identity_hash in Transport.blackholed_identities:
                if Transport.blackholed_identities[identity_hash]["source"] == Transport.identity.hash:
                    local_blackhole[identity_hash] = Transport.blackholed_identities[identity_hash]

            packed = umsgpack.packb(local_blackhole)
            localpath = os.path.join(RNS.Reticulum.blackholepath, "local")
            tmppath = f"{localpath}.tmp"
            with open(tmppath, "wb") as f: f.write(packed)
            if os.path.isfile(localpath): os.unlink(localpath)
            os.rename(tmppath, localpath)

        except Exception as e:
            RNS.log(f"Error while persisting blackhole list: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

    ##############################
    # Destination Type Filtering #
    ##############################

    destination_filters_lock = threading.Lock()

    @staticmethod
    def block_destination_type(full_name):
        try:
            name_hash = RNS.Destination.name_hash(full_name)
            with Transport.destination_filters_lock:
                Transport.blocked_destination_types[name_hash] = [True]
                Transport.client_destination_types.pop(name_hash, None)
                Transport.destination_type_map[name_hash] = full_name
            RNS.log(f"Blocked {full_name} {RNS.prettyhexrep(name_hash)} destinations", RNS.LOG_DEBUG)
            return True
        except Exception as e: RNS.log(f"Could not add {full_name} destination type to blocked list: {e}", RNS.LOG_ERROR)
        return False

    @staticmethod
    def allow_destination_type(full_name):
        try:
            name_hash = RNS.Destination.name_hash(full_name)
            with Transport.destination_filters_lock:
                Transport.allowed_destination_types[name_hash] = [True]
                Transport.destination_type_map[name_hash] = full_name
            if Transport.required_destinations_only: RNS.log(f"Allowing {Transport.destination_type_name(name_hash)} {RNS.prettyhexrep(name_hash)} destinations", RNS.LOG_DEBUG)
            return True
        except Exception as e: RNS.log(f"Could not add {Transport.destination_type_name(name_hash)} destination type to allowed list: {e}", RNS.LOG_ERROR)
        return False

    @staticmethod
    def _wants_destination_type(full_name, requester, signature):
        try:
            name_hash = RNS.Destination.name_hash(full_name)
            if not name_hash in Transport.blocked_destination_types:
                with Transport.destination_filters_lock:
                    # TODO: Add requester signature validation
                    entry = Transport.client_destination_types.get(name_hash, [True, {}])
                    entry[1][requester] = [True]
                    Transport.client_destination_types[name_hash] = entry
                    Transport.destination_type_map[name_hash] = full_name
                RNS.log(f"Registered {Transport.destination_type_name(name_hash)} {RNS.prettyhexrep(name_hash)} destinations requirement for {RNS.prettyhexrep(requester)}", RNS.LOG_DEBUG)
                return True

        except Exception as e: RNS.log(f"Could not add {Transport.destination_type_name(name_hash)} destination type to clients required list: {e}", RNS.LOG_ERROR)
        return False

    @staticmethod
    def _unwants_destination_type(full_name, requester, signature, name_hash=None):
        try:
            if not name_hash: name_hash = RNS.Destination.name_hash(full_name)
            with Transport.destination_filters_lock:
                # TODO: Add requester signature validation
                entry = Transport.client_destination_types.get(name_hash, None)
                if entry:
                    was_registered = entry[1].pop(requester, None)
                    if was_registered: RNS.log(f"Deregistered {Transport.destination_type_name(name_hash)} {RNS.prettyhexrep(name_hash)} destinations requirement for {RNS.prettyhexrep(requester)}", RNS.LOG_DEBUG)
                    if len(entry[1]) == 0:
                        Transport.client_destination_types.pop(name_hash, None)
                        RNS.log(f"No remaining requesters for {Transport.destination_type_name(name_hash)} {RNS.prettyhexrep(name_hash)} destinations, type deregistered", RNS.LOG_DEBUG)
                    if was_registered: return True

        except Exception as e: RNS.log(f"Could not remove {Transport.destination_type_name(name_hash)} destination type for {RNS.prettyhexrep(requester)} from clients required list: {e}", RNS.LOG_ERROR)
        return False

    @staticmethod
    def _unwants_all_destination_types(requester, signature):
        try:
            for name_hash in Transport.client_destination_types.copy():
                Transport._unwants_destination_type(None, requester, signature, name_hash=name_hash)
            RNS.log(f"Deregistered all destination requirements for {RNS.prettyhexrep(requester)}", RNS.LOG_DEBUG)
            return True

        except Exception as e: RNS.log(f"Could not deregister all destination types for {RNS.prettyhexrep(requester)} from clients required list: {e}", RNS.LOG_ERROR); RNS.trace_exception(e)
        return False

    @staticmethod
    def destination_type_name(name_hash):
        return f"<{Transport.destination_type_map.get(name_hash, 'unknown')}>"

    ###################
    # Various Helpers #
    ###################

    @staticmethod
    def void_queues():
        Transport.held_announces = {}
        Transport.receipts = []
        Transport.reverse_table = {}

    @staticmethod
    def exit_handler():
        Transport._should_run = False
        Transport.void_queues()
        if not Transport.owner.is_connected_to_shared_instance:
            Transport.persist_data()
            if Transport.announce_cache != None: Transport.announce_cache.flush()

    #####################
    # Remote Management #
    #####################

    @staticmethod
    def remote_status_handler(path, data, request_id, link_id, remote_identity, requested_at):
        if remote_identity != None:
            response = None
            try:
                if isinstance(data, list) and len(data) > 0:
                    response = []
                    response.append(Transport.owner.get_interface_stats())
                    if data[0] == True: response.append(Transport.owner.get_link_count())

                    if len(data) >= 2:
                        if data[1] == True: response.append(Transport.owner.get_profiling_results())

                    return response

            except Exception as e:
                RNS.log("An error occurred while processing remote status request from "+str(remote_identity), RNS.LOG_ERROR)
                RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)

            return None

    @staticmethod
    def remote_path_handler(path, data, request_id, link_id, remote_identity, requested_at):
        if remote_identity != None:
            response = None
            try:
                if isinstance(data, list) and len(data) > 0:
                    command = data[0]
                    destination_hash = None
                    max_hops = None
                    if len(data) > 1: destination_hash = data[1]
                    if len(data) > 2: max_hops = data[2]

                    if command == "table":
                        table = Transport.owner.get_path_table(max_hops=max_hops)
                        response = []
                        for path in table:
                            if destination_hash == None or destination_hash == path["hash"]:
                                response.append(path)

                    elif command == "rates":
                        table = Transport.owner.get_rate_table()
                        response = []
                        for path in table:
                            if destination_hash == None or destination_hash == path["hash"]:
                                response.append(path)

                    return response

            except Exception as e:
                RNS.log("An error occurred while processing remote status request from "+str(remote_identity), RNS.LOG_ERROR)
                RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)

            return None

#####################
# Memory Management #
#####################

MEM_TRIM_FLOOR = 60
_trim_impl     = None
_trim_resolved = False

def garbage_collect():
    Transport.should_collect = False
    gc.collect(); Transport.mem_dirty = True
    Transport.last_collect = time.time()

def trim_heap():
    global _trim_impl, _trim_resolved
    if not _trim_resolved:
        _trim_resolved = True
        _trim_impl     = _resolve_trim()

    if _trim_impl is not None:
        try:
            _trim_impl(Transport.mem_trim_pad)
            Transport.last_trim_rss_kb = _proc_status_kb("VmRSS")["VmRSS"]
            if Transport.last_trim_rss_kb >= 0:
                RNS.log(f"Heap trimmed, RSS {RNS.prettysize(Transport.last_trim_rss_kb*1024)}", RNS.LOG_DEBUG)
        except Exception as e: RNS.log(f"Memory trim error: {e}", RNS.LOG_DEBUG)

def _proc_status_kb(*fields):
    # Map missing fields to -1
    values = {field: -1 for field in fields}
    try:
        with open("/proc/self/status") as status_file:
            for line in status_file:
                for field in fields:
                    if line.startswith(field):
                        values[field] = int(line.split()[1])
    except (OSError, ValueError): pass
    return values

def _trim_due(now):
    if not Transport.mem_dirty: return None
    elapsed = now - Transport.last_mem_trim

    # If no gate configured, rely solely on throttle
    if Transport.mem_trim_gate_mb <= 0:
        if now > Transport.last_mem_trim+Transport.mem_trim_throttle: return -1
        return None

    # Hard limit trim cadence
    if elapsed < MEM_TRIM_FLOOR: return None

    # First gated trim, no baseline yet
    if Transport.last_trim_rss_kb < 0: return -1

    rss = _proc_status_kb("VmRSS")["VmRSS"]
    if rss < 0: # No RSS introspection available, fall back to the timer
        if now > Transport.last_mem_trim+Transport.mem_trim_throttle: return -1
        return None

    surplus = rss - Transport.last_trim_rss_kb
    if surplus >= Transport.mem_trim_gate_mb*1024: return surplus
    return None

def _resolve_trim():
    try:
        if RNS.vendor.platformutils.is_linux():
            f = getattr(ctypes.CDLL(None), "malloc_trim", None) # Not available on musl
            if f is None: return None
            return lambda pad: f(pad)
        elif RNS.vendor.platformutils.is_darwin():
            libc = ctypes.CDLL(ctypes.util.find_library("c"))
            f = getattr(libc, "malloc_zone_pressure_relief", None)
            if f is None: return None
            def trim(pad): f(None, 0); f(None, 0) # Yes, it's strange, see Apple's malloc.h
            return trim
        elif RNS.vendor.platformutils.is_android():
            libc = ctypes.CDLL("libc.so")
            return lambda pad: libc.mallopt(-101, 0) # M_PURGE, API 28+
        elif RNS.vendor.platformutils.is_windows():
            k32 = ctypes.WinDLL("kernel32")
            heap = k32.GetProcessHeap()
            f = k32.HeapTrim # Will raise AttributeError on Windows < 8
            return lambda pad: f(heap, 0)
    except Exception as e: RNS.log(f"Heap trim unavailable: {e}", RNS.LOG_DEBUG)
    RNS.log(f"No working memory trim mechanism on this platform, memory management will be sub-optimal", RNS.LOG_WARNING)
    return None

#######################
# Table entry indices #
#######################

# Transport.path_table entry indices
IDX_PT_TIMESTAMP = 0
IDX_PT_NEXT_HOP  = 1
IDX_PT_HOPS      = 2
IDX_PT_EXPIRES   = 3
IDX_PT_RANDBLOBS = 4
IDX_PT_RVCD_IF   = 5
IDX_PT_PACKET    = 6
IDX_PT_USED      = 7

# Transport.reverse_table entry indices
IDX_RT_RCVD_IF   = 0
IDX_RT_OUTB_IF   = 1
IDX_RT_TIMESTAMP = 2

# Transport.announce_table entry indices
IDX_AT_TIMESTAMP = 0
IDX_AT_RTRNS_TMO = 1
IDX_AT_RETRIES   = 2
IDX_AT_RCVD_IF   = 3
IDX_AT_HOPS      = 4
IDX_AT_PACKET    = 5
IDX_AT_LCL_RBRD  = 6
IDX_AT_BLCK_RBRD = 7
IDX_AT_ATTCHD_IF = 8

# Transport.link_table entry indices
IDX_LT_TIMESTAMP = 0
IDX_LT_NH_TRID   = 1
IDX_LT_NH_IF     = 2
IDX_LT_REM_HOPS  = 3
IDX_LT_RCVD_IF   = 4
IDX_LT_HOPS      = 5
IDX_LT_DSTHASH   = 6
IDX_LT_VALIDATED = 7
IDX_LT_PROOF_TMO = 8

# Transport.tunnels entry indices
IDX_TT_TUNNEL_ID = 0
IDX_TT_IF        = 1
IDX_TT_PATHS     = 2
IDX_TT_EXPIRES   = 3