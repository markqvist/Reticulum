#!/usr/bin/env python3
#
# Generated with lc/deepseek_v4_flash_q8_k_xl
# Reviewed and corrected by Mark Qvist
#
# Usage examples:
#
#   python3 tests/transport_throughput.py
#   python3 tests/transport_throughput.py --scenario transit_single_135
#   python3 tests/transport_throughput.py --mode inline --runs 5
#   python3 tests/transport_throughput.py --list-scenarios
#

import unittest

import os
import sys
import time
import gc
import struct
import platform
import tempfile
import statistics

# Ensure that the Reticulum tree this suite lives in is the one being
# benchmarked, even if a different version of Reticulum is installed in
# site-packages.
_SUITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.isdir(os.path.join(_SUITE_ROOT, "RNS")):
    sys.path.insert(0, _SUITE_ROOT)

import RNS

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BENCHMARK_CONFIG = {
    "scenarios": None,   # None = all, or a list of scenario names
    "mode": "both",      # "inline", "drainer" or "both"
    "runs": 3,           # measurement runs per scenario/mode, median is reported
}

SCENARIO_DESCRIPTIONS = {
    "transit_single_135":   "SINGLE transit relay, 135 B payload, 3-hop path",
    "transit_single_475":   "SINGLE transit relay, 475 B payload, 3-hop path",
    "transit_single_1024":  "SINGLE transit relay, 1 KiB payload, 3-hop path",
    "transit_single_16384": "SINGLE transit relay, 16 KiB payload, 3-hop path",
    "transit_single_final": "SINGLE transit relay, final hop, header strip, 135 B",
    "transit_link_135":     "LINK transit relay via link table, cross-interface, 135 B",
    "transit_link_475":     "LINK transit relay via link table, cross-interface, 475 B",
    "transit_link_1024":    "LINK transit relay via link table, cross-interface, 1024 B",
    "transit_link_16384":   "LINK transit relay via link table, cross-interface, 16384 B",
    "transit_link_32768":   "LINK transit relay via link table, cross-interface, 32768 B",
    "terminus_link":        "LINK terminus delivery, token decrypt, 135 B",
    "terminus_single":      "SINGLE local delivery, ephemeral-key decrypt, 135 B",
    "announce_ingress":     "Announce ingress, fresh destinations, validation + path insert",
    "outbound_path":        "Outbound insertion into transport, known 3-hop path, 135 B",
}

# Default packet counts per scenario and mode.
DEFAULT_PACKETS = {
    "transit_single_135":     {"inline": 20000, "drainer": 20000},
    "transit_single_475":     {"inline": 20000, "drainer": 20000},
    "transit_single_1024":    {"inline": 20000, "drainer": 20000},
    "transit_single_16384":   {"inline": 10000, "drainer": 10000},
    "transit_single_final":   {"inline": 20000, "drainer": 20000},
    "transit_link_135":       {"inline": 20000, "drainer": 20000},
    "transit_link_475":       {"inline": 20000, "drainer": 20000},
    "transit_link_1024":      {"inline": 20000, "drainer": 20000},
    "transit_link_16384":     {"inline": 10000, "drainer": 10000},
    "transit_link_32768":     {"inline": 10000, "drainer": 10000},
    "terminus_link":          {"inline": 6000,  "drainer": 6000},
    "terminus_single":        {"inline": 3000,  "drainer": 3000},
    "announce_ingress":       {"inline": 1000,  "drainer": 1000},
    "outbound_path":          {"inline": 8000,  "drainer": 0},
}

INLINE_SAMPLE_STEP  = 64  # sample a timing point every N packets for p50/p95
DRAINER_CHUNK       = 256 # packets fed per drainer backpressure step


class BenchmarkInterface(RNS.Interfaces.Interface.Interface):
    HW_MTU    = 1048576
    BITRATE   = 1_000_000_000

    def __init__(self, name="bench"):
        super().__init__()
        self.name      = name
        self.IN        = True
        self.OUT       = True
        self.online    = True
        self.bitrate   = self.BITRATE
        self.HW_MTU    = BenchmarkInterface.HW_MTU
        self.mode      = RNS.Interfaces.Interface.Interface.MODE_FULL
        self.gravity   = 0
        self.ifac_size = 0
        self.ifac_key  = None
        self.ifac_identity = None
        self.parent_interface = None
        self.ingress_control  = False
        self.announce_rate_target  = RNS.Interfaces.Interface.Interface.DEFAULT_AR_TARGET
        self.announce_rate_grace   = RNS.Interfaces.Interface.Interface.DEFAULT_AR_GRACE
        self.announce_rate_penalty = RNS.Interfaces.Interface.Interface.DEFAULT_AR_PENALTY

    def process_outgoing(self, data):
        self.txb += len(data)

    def __str__(self):
        return f"BenchmarkInterface[{self.name}]"


class Scenario:
    kind = "ingress"   # "ingress" or "outbound"

    def __init__(self, name, description, interface, frames, packets, runs,
                 inline_offset, drainer_offset, size, completion_counter=None,
                 fresh_per_run=False):
        self.name                = name
        self.description         = description
        self.interface           = interface
        self.frame_size          = size
        self.frames              = frames          # pool of unique raw frames
        self.packets_inline      = packets.get("inline", 0)
        self.packets_drainer     = packets.get("drainer", 0)
        self.runs                = runs
        self.inline_offset       = inline_offset
        self.drainer_offset      = drainer_offset
        self.completion_counter  = completion_counter
        # When true, each run uses a dedicated fresh slice of frames
        # (required where processing is not idempotent, e.g. announces).
        # When false, runs reuse the same pool with the duplicate filter
        # reset in between.
        self.fresh_per_run       = fresh_per_run

    def can_drainer(self):
        return self.packets_drainer > 0 and self.completion_counter is not None

    def n_for_mode(self, mode):
        if mode == "inline":  return self.packets_inline
        if mode == "drainer": return self.packets_drainer


class CountingDestination(RNS.Destination):
    """A destination that counts successful deliveries, for use as a
    completion counter in drainer mode."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.delivered = 0

    def receive(self, packet):
        result = super().receive(packet)
        if result:
            self.delivered += 1
        return result


def _register_link(link):
    with RNS.Transport.active_links_lock:
        RNS.Transport.active_links.append(link)
        if hasattr(RNS.Transport, "active_links_map"):
            RNS.Transport.active_links_map[link.link_id] = link


def _make_minimal_link(instance, interface):
    """Constructs a minimal, active Link object suitable for benchmark delivery."""
    import importlib
    _link_mod = importlib.import_module("RNS.Link")

    link = RNS.Link.__new__(RNS.Link)
    link.mode = RNS.Link.MODE_DEFAULT
    link.rtt = 0.1
    link.mtu = RNS.Reticulum.MTU
    link.establishment_cost = 0
    link.establishment_rate = None
    link.expected_rate = None
    link.callbacks = _link_mod.LinkCallbacks()
    link.resource_strategy = RNS.Link.ACCEPT_NONE
    link.last_resource_window = None
    link.last_resource_eifr = None
    link.outgoing_resources = []
    link.incoming_resources = []
    link.pending_requests = []
    link.last_inbound = 0
    link.last_outbound = 0
    link.last_keepalive = 0
    link.last_proof = 0
    link.last_data = 0
    link.tx = 0
    link.rx = 0
    link.txbytes = 0
    link.rxbytes = 0
    link.rssi = None
    link.snr = None
    link.q = None
    link.traffic_timeout_factor = RNS.Link.TRAFFIC_TIMEOUT_FACTOR
    link.keepalive_timeout_factor = RNS.Link.KEEPALIVE_TIMEOUT_FACTOR
    link.keepalive = RNS.Link.KEEPALIVE
    link.stale_time = RNS.Link.STALE_TIME
    link.watchdog_lock = False
    link.status = RNS.Link.ACTIVE
    link.activated_at = time.time()
    link.type = RNS.Destination.LINK
    link.owner = instance
    link.initiator = False
    link.expected_hops = 1
    link.rebalanced = None
    link.attached_interface = interface
    link._channel = None
    link._Link__remote_identity = None
    link._Link__track_phy_stats = False
    link.derived_key = os.urandom(64)
    link.token = RNS.Cryptography.Token(link.derived_key)
    link.link_id = os.urandom(RNS.Reticulum.TRUNCATED_HASHLENGTH//8)
    link.hash = link.link_id
    link.hexhash = link.link_id.hex()
    from RNS.Cryptography.Proxies import Ed25519PrivateKeyProxy
    link.sig_prv = Ed25519PrivateKeyProxy.from_private_bytes(link.derived_key[:32])

    class _DestinationShim:
        pass

    link.destination = _DestinationShim()
    link.destination.type = RNS.Destination.LINK
    link.destination.proof_strategy = RNS.Destination.PROVE_NONE
    _dest_mod = importlib.import_module("RNS.Destination")
    link.destination.callbacks = _dest_mod.Callbacks()
    link.destination.status = RNS.Link.ACTIVE
    link.destination.last_outbound = 0
    link.destination.tx = 0
    link.destination.txbytes = 0
    link.destination.attached_interface = interface
    link.destination.mtu = RNS.Reticulum.MTU
    link.destination.rssi = None
    link.destination.snr = None
    link.destination.q = None
    link.destination.rtt = RNS.Link.TRAFFIC_TIMEOUT_MIN_MS/1000
    link.destination.traffic_timeout_factor = 1.0

    return link


def _transit_single_frame(interface, dst_h, payload):
    """One HEADER_2|TRANSPORT|SINGLE|DATA frame addressed to this instance."""
    flags = (RNS.Packet.HEADER_2 << 6) | (RNS.Transport.TRANSPORT << 4) \
            | (RNS.Destination.SINGLE << 2) | RNS.Packet.DATA
    return (struct.pack("!B", flags) + struct.pack("!B", 1)
            + RNS.Transport.identity.hash + dst_h
            + bytes([RNS.Packet.NONE]) + payload)


def _transit_link_frame(interface, link_id, payload):
    """One HEADER_2|TRANSPORT|LINK|DATA frame addressed to this instance."""
    flags = (RNS.Packet.HEADER_2 << 6) | (RNS.Transport.TRANSPORT << 4) \
            | (RNS.Destination.LINK << 2) | RNS.Packet.DATA
    return (struct.pack("!B", flags) + struct.pack("!B", 1)
            + RNS.Transport.identity.hash + link_id
            + bytes([RNS.Packet.NONE]) + payload)


def _terminus_link_frame(link, payload):
    """One HEADER_1|BROADCAST|LINK|DATA frame for a local active link,
    encrypted with the link token."""
    flags = (RNS.Packet.HEADER_1 << 6) | (RNS.Transport.BROADCAST << 4) \
            | (RNS.Destination.LINK << 2) | RNS.Packet.DATA
    ciphertext = link.encrypt(payload)
    return (struct.pack("!B", flags) + struct.pack("!B", 0)
            + link.link_id + bytes([RNS.Packet.NONE]) + ciphertext)


def _payload(i, size, marker):
    """Deterministic, unique payload of `size` bytes."""
    return i.to_bytes(8, "big") + bytes([marker]) * (size - 8)


def build_scenarios(instance, interface, interface_b, requested=None):
    """Builds all benchmark scenarios and returns a dict name -> Scenario."""
    scenarios = {}
    runs = BENCHMARK_CONFIG["runs"]

    def _slices(packets, fresh=False):
        inline_n = packets.get("inline", 0)
        drainer_n = packets.get("drainer", 0)
        if fresh:
            # Fresh frames per run for both modes
            total = (inline_n + drainer_n) * runs
            return total, inline_n, drainer_n, 0, inline_n * runs
        else:
            # One re-usable pool of the largest mode's frame count
            total = max(inline_n, drainer_n)
            return total, inline_n, drainer_n, 0, 0

    # --- SINGLE transit relay, several payload sizes -----------------------
    sizes = [("135", 135), ("475", 475), ("1024", 1024), ("16384", 16384)]
    for suffix, size in sizes:
        name = f"transit_single_{suffix}"
        total, inline_n, drainer_n, off_i, off_d = _slices(DEFAULT_PACKETS[name])
        dst_h = RNS.Cryptography.hkdf(length=16,
                                      derive_from=f"T{suffix}dst".encode(),
                                      salt=b"bench", context=None)
        next_hop = RNS.Cryptography.hkdf(length=16,
                                         derive_from=f"T{suffix}nh".encode(),
                                         salt=b"bench", context=None)
        now = time.time()
        with RNS.Transport.path_table_lock:
            RNS.Transport.path_table[dst_h] = [
                now, next_hop, 3, now + 3600, [], interface, bytes(32)
            ]
        frames = [_transit_single_frame(interface, dst_h,
                                        _payload(i, size, 0x57))
                  for i in range(total)]
        scenarios[name] = Scenario(
            name,
            f"SINGLE transit relay, {size} B payload, 3-hop path",
            interface, frames, DEFAULT_PACKETS[name], runs,
            off_i, off_d, size,
            completion_counter=lambda: RNS.Transport.tx_packets,
        )

    # --- SINGLE transit relay, final hop (header strip) --------------------
    name = "transit_single_final"
    total, inline_n, drainer_n, off_i, off_d = _slices(DEFAULT_PACKETS[name])
    dst_h = RNS.Cryptography.hkdf(length=16, derive_from=b"TFdst",
                                  salt=b"bench", context=None)
    next_hop = RNS.Cryptography.hkdf(length=16, derive_from=b"TFnh",
                                     salt=b"bench", context=None)
    now = time.time()
    with RNS.Transport.path_table_lock:
        RNS.Transport.path_table[dst_h] = [
            now, next_hop, 1, now + 3600, [], interface, bytes(32)
        ]
    frames = [_transit_single_frame(interface, dst_h,
                                    _payload(i, 135, 0x46))
              for i in range(total)]
    scenarios[name] = Scenario(
        name,
        "SINGLE transit relay, final hop, transport header strip, 135 B",
        interface, frames, DEFAULT_PACKETS[name], runs,
        off_i, off_d, 135,
        completion_counter=lambda: RNS.Transport.tx_packets,
    )

    # --- LINK transit relay (cross-interface) ------------------------------
    sizes = [("135", 135), ("475", 475), ("1024", 1024), ("16384", 16384), ("32768", 32768)]
    for suffix, size in sizes:
        name = f"transit_link_{suffix}"

        total, inline_n, drainer_n, off_i, off_d = _slices(DEFAULT_PACKETS[name])
        link_id = RNS.Cryptography.hkdf(length=16, derive_from=b"Llink",
                                        salt=b"bench", context=None)
        now = time.time()
        with RNS.Transport.link_table_lock:
            # timestamp, next-hop transport id, outbound iface, remaining hops,
            # received-on iface, taken hops, original destination hash,
            # validated, proof timeout
            RNS.Transport.link_table[link_id] = [
                now, RNS.Transport.identity.hash, interface_b, 2,
                interface, 2, os.urandom(16), True, now + 60
            ]
        frames = [_transit_link_frame(interface, link_id,
                                      _payload(i, size, 0x4C))
                  for i in range(total)]
        scenarios[name] = Scenario(
            name,
            f"LINK transit relay via link table, cross-interface, {size} B",
            interface, frames, DEFAULT_PACKETS[name], runs,
            off_i, off_d, size,
            completion_counter=lambda: RNS.Transport.tx_packets,
        )

    # --- LINK terminus delivery --------------------------------------------
    name = "terminus_link"
    total, inline_n, drainer_n, off_i, off_d = _slices(DEFAULT_PACKETS[name])
    link = _make_minimal_link(instance, interface)
    _register_link(link)
    frames = [_terminus_link_frame(link, _payload(i, 135, 0x6C))
              for i in range(total)]
    scenarios[name] = Scenario(
        name,
        "LINK terminus delivery, token decrypt, no app callback, 135 B",
        interface, frames, DEFAULT_PACKETS[name], runs,
        off_i, off_d, 135,
        completion_counter=lambda: link.rx,
    )

    # --- SINGLE local delivery ---------------------------------------------
    name = "terminus_single"
    total, inline_n, drainer_n, off_i, off_d = _slices(DEFAULT_PACKETS[name])
    identity = RNS.Identity()
    # The Destination initialiser automatically registers IN destinations
    # with the transport core.
    destination = CountingDestination(identity, RNS.Destination.IN,
                                      RNS.Destination.SINGLE,
                                      "bench", "terminus")
    frames = []
    for i in range(total):
        packet = RNS.Packet(destination, _payload(i, 135, 0x53),
                            RNS.Packet.DATA, create_receipt=False)
        packet.pack()
        frames.append(packet.raw)
    scenarios[name] = Scenario(
        name,
        "SINGLE local delivery, ephemeral-key decrypt, 135 B",
        interface, frames, DEFAULT_PACKETS[name], runs,
        off_i, off_d, 135,
        completion_counter=lambda: destination.delivered,
    )

    # --- Announce ingress ----------------------------------------------------
    name = "announce_ingress"
    total, inline_n, drainer_n, off_i, off_d = _slices(DEFAULT_PACKETS[name],
                                                       fresh=True)
    name_hash = RNS.Identity.full_hash(b"rns.throughput.bench")[
        :RNS.Identity.NAME_HASH_LENGTH//8]
    frames = []; tsize = 0
    for i in range(total):
        ann_identity = RNS.Identity()
        dst_h = RNS.Identity.full_hash(name_hash + ann_identity.hash)[
            :RNS.Reticulum.TRUNCATED_HASHLENGTH//8]
        random_hash = os.urandom(5) + int(time.time() + i).to_bytes(5, "big")
        signed_data = dst_h + ann_identity.get_public_key() + name_hash \
                      + random_hash + b""
        signature = ann_identity.sign(signed_data)
        announce_data = ann_identity.get_public_key() + name_hash \
                        + random_hash + b"" + signature
        flags = (RNS.Packet.HEADER_1 << 6) \
                | (RNS.Destination.SINGLE << 2) | RNS.Packet.ANNOUNCE
        fbs = struct.pack("!B", flags) + struct.pack("!B", 0) + dst_h + bytes([RNS.Packet.NONE]) + announce_data
        frames.append(fbs)
        tsize += len(fbs)

    scenarios[name] = Scenario(
        name,
        "Announce ingress, fresh destinations, validation + path insert",
        interface, frames, DEFAULT_PACKETS[name], runs,
        off_i, off_d, int(tsize/total),
        completion_counter=lambda: len(RNS.Transport.path_table),
        fresh_per_run=True,
    )

    # --- Outbound insertion into transport ----------------------------------
    name = "outbound_path"
    packets = DEFAULT_PACKETS[name]
    inline_n = packets.get("inline", 0)
    total = inline_n  # pool is re-used across runs
    dst_h = RNS.Cryptography.hkdf(length=16, derive_from=b"Odst",
                                  salt=b"bench", context=None)
    next_hop = RNS.Cryptography.hkdf(length=16, derive_from=b"Onh",
                                     salt=b"bench", context=None)
    now = time.time()
    with RNS.Transport.path_table_lock:
        RNS.Transport.path_table[dst_h] = [
            now, next_hop, 3, now + 3600, [], interface, bytes(32)
        ]
    remote_id = RNS.Identity(create_keys=False)
    remote_id.load_public_key(os.urandom(RNS.Identity.KEYSIZE//8))
    outbound_destination = RNS.Destination(remote_id, RNS.Destination.OUT,
                                           RNS.Destination.SINGLE,
                                           "bench", "outbound")
    outbound_destination.hash = dst_h
    outbound_destination.hexhash = dst_h.hex()
    frames = []
    for i in range(total):
        packet = RNS.Packet(outbound_destination, _payload(i, 135, 0x4F),
                            RNS.Packet.DATA, create_receipt=False)
        packet.pack()
        frames.append(packet)
    outbound = Scenario(
        name,
        "Outbound insertion into transport, known 3-hop path, 135 B",
        interface, frames, packets, runs,
        0, 0, 135,
        completion_counter=None,
    )
    outbound.kind = "outbound"
    scenarios[name] = outbound

    if requested is not None:
        missing = [s for s in requested if s not in scenarios]
        if missing:
            raise KeyError(f"Unknown scenario(s): {', '.join(missing)}. "
                           f"Available: {', '.join(sorted(scenarios))}")
        scenarios = {name: scenarios[name] for name in requested}

    return scenarios


def _reset_transport_state():
    RNS.Transport.packet_hashlist = set()
    RNS.Transport.packet_hashlist_prev = set()
    RNS.Transport.reverse_table = {}


def _percentile(sorted_values, p):
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, int(len(sorted_values) * p))
    return sorted_values[index]


def _feed(frame, interface):
    RNS.Transport.preprocess_inbound(frame, interface)

def _bench_inline(interface, frames, n, runs, offset, fresh_per_run=False):
    """Synchronous benchmark: process each frame in the calling thread,
    bypassing the inbound queue. Returns (run_means_us, samples_us)."""
    run_means = []
    all_samples = []

    # Bypass the inbound queue so processing happens entirely in the
    # calling thread; restore the previous setting afterwards.
    previous_queue_state = RNS.Transport.USE_INBOUND_QUEUE
    RNS.Transport.USE_INBOUND_QUEUE = False
    try:
        for r in range(runs):
            _reset_transport_state()
            gc.collect()
            gc.disable()

            base = offset + (r * n if fresh_per_run else 0)
            t0 = time.perf_counter()
            prev = None
            samples = []
            step = INLINE_SAMPLE_STEP
            next_sample = step
            for i in range(n):
                _feed(frames[base + i], interface)
                if i == next_sample:
                    now = time.perf_counter()
                    if prev is not None:
                        samples.append((now - prev) / step)
                    prev = now
                    next_sample += step
            dt = time.perf_counter() - t0
            gc.enable()

            run_means.append(dt / n * 1e6)
            all_samples.extend(samples)
    finally:
        RNS.Transport.USE_INBOUND_QUEUE = previous_queue_state

    return run_means, [s * 1e6 for s in all_samples]


def _bench_drainer(scenario, n, runs):
    """Feed frames through the inbound queue from the calling thread
    while the drainer thread processes them. Backpressure is applied
    via the scenario completion counter, so no frames are dropped and
    the pipeline stays saturated."""
    run_means = []

    # Ensure the inbound queue and drainer are used; restore afterwards.
    previous_queue_state = RNS.Transport.USE_INBOUND_QUEUE
    RNS.Transport.USE_INBOUND_QUEUE = True
    try:
        for r in range(runs):
            _reset_transport_state()
            gc.collect()
            gc.disable()

            base = scenario.drainer_offset \
                + (r * n if scenario.fresh_per_run else 0)
            baseline = scenario.completion_counter()
            fed = 0
            t0 = time.perf_counter()
            chunk = DRAINER_CHUNK
            while fed < n:
                batch = min(chunk, n - fed)
                for i in range(fed, fed + batch):
                    _feed(scenario.frames[base + i], scenario.interface)
                fed += batch
                target = baseline + fed
                while scenario.completion_counter() < target-800: # Assumes default inbound queue of 1024
                    time.sleep(0.0002)
            dt = time.perf_counter() - t0
            gc.enable()

            run_means.append(dt / n * 1e6)
    finally:
        RNS.Transport.USE_INBOUND_QUEUE = previous_queue_state

    return run_means


def _bench_outbound(packets, n, runs, offset):
    """Synchronous benchmark of the outbound path: insert each packet
    into transport for a known path via Transport.outbound(). The packet
    pool is re-used across runs."""
    run_means = []
    for r in range(runs):
        gc.collect()
        gc.disable()
        t0 = time.perf_counter()
        for i in range(n):
            RNS.Transport.outbound(packets[offset + i])
        dt = time.perf_counter() - t0
        gc.enable()
        run_means.append(dt / n * 1e6)
    return run_means


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _fmt_us(value):
    return f"{value:>10.2f}"


def _fmt_pps(value):
    return f"{value:>12,.0f}"


def print_environment_header():
    tree_fastpath = "present" if hasattr(RNS.Transport, "USE_FP_CACHE") else "absent"
    print("=" * 40)
    print("Reticulum Transport Throughput Benchmark")
    print("=" * 40)
    print(f"  RNS version : {RNS.__version__}")
    print(f"  Mode        : {'compiled' if RNS.compiled else 'interpreted'}")
    print(f"  crypto      : {RNS.Cryptography.backend()}")
    print(f"  transport   : enabled")
    print(f"  fast path   : {tree_fastpath}")
    print(f"  python      : {platform.python_version()}")
    print(f"  platform    : {platform.platform()}")
    print(f"  machine     : {platform.machine()}, cpus: {os.cpu_count()}")
    print()


def print_scenario_table(scenario, results):
    """results: dict mode -> dict(runs, mean_us, pps, stdev, p50, p95)."""
    print(f"Scenario: {scenario.name} - {scenario.description}")
    print(f"  {'mode':<9}{'n':>8}{'runs':>6}{'mean µs':>13}{'pps':>16}"
          f"{'p50':>11}{'p95':>11}")
    print("  " + "-" * 75)
    for mode in ("inline", "drainer"):
        if mode not in results:
            continue
        r = results[mode]
        n = scenario.n_for_mode(mode)
        p50 = f"{r['p50']:>9.2f} µs" if r["p50"] is not None else "-"
        p95 = f"{r['p95']:>9.2f} µs" if r["p95"] is not None else "-"
        spread = ""
        if r.get("stdev") is not None:
            spread = f" ±{r['stdev']:.2f}"
        if mode == "inline": mode = "direct"
        print(f"  {mode:<9}{n:>8}{r['runs']:>6}{_fmt_us(r['mean_us']):>13}"
              f"{_fmt_pps(r['pps']):>16}{p50:>11}{p95:>11}  "
              f"({r['runs']} runs, median{spread})")

    print()
    for mode in ("inline", "drainer"):
        if mode not in results:
            continue

        r = results[mode]
        tp = r['pps']*scenario.frame_size*8
        if mode == "inline": mode = "direct"
        print(f"{mode:<8} : {RNS.prettyspeed(tp)}")

    print()


def print_pps_matrix(rows):
    """rows: list of (scenario_name, inline_pps, drainer_pps, fsize)"""
    if not rows:
        return
    print("-" * 72)
    print("Transport Throughput, median of runs")
    print(f"  {'scenario':<22}{'direct':>14}{'drainer':>14}")
    print("  " + "-" * 70)
    for name, inline_pps, drainer_pps, fsize in rows:
        i = f"{inline_pps:>12,.0f}" if inline_pps else "-"
        d = f"{drainer_pps:>12,.0f}" if drainer_pps else "-"
        itp = RNS.prettyspeed(inline_pps*fsize*8) if inline_pps else "-"
        dtp = RNS.prettyspeed(drainer_pps*fsize*8) if drainer_pps else "-"
        print(f"  {name:<22}{i:>14}{d:>14}{itp:>16} / {dtp}")
    print()


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

_instance = None
_interfaces = None
_scenarios = None
_config_dir = None


def _start_transport():
    global _instance, _interfaces, _scenarios, _config_dir

    _config_dir = tempfile.mkdtemp(prefix="rns-transport-bench-")
    config_dir = _config_dir
    with open(os.path.join(config_dir, "config"), "w") as fh:
        fh.write(
            "[reticulum]\n"
            "  enable_transport = yes\n"
            "  share_instance = No\n"
            "  panic_on_interface_error = No\n"
            "\n"
            "[logging]\n"
            "  loglevel = 0\n"
            "\n"
            "[interfaces]\n"
        )

    # Raise queue lengths for to avoid drops
    # at high feed rates
    RNS.Transport.INBOUND_DA_QUEUE_LENGTH = 4096
    RNS.Transport.INBOUND_AN_QUEUE_LENGTH = 1024
    RNS.Transport.INBOUND_PR_QUEUE_LENGTH = 1024
    RNS.Transport.INBOUND_IL_QUEUE_LENGTH = 1024
    _instance = RNS.Reticulum(configdir=config_dir,
                              loglevel=RNS.LOG_CRITICAL,
                              logdest=lambda *a, **k: None)

    while not RNS.Transport.ready:
        time.sleep(0.05)

    interface = BenchmarkInterface("line-a")
    interface_b = BenchmarkInterface("line-b")
    RNS.Transport.add_interface(interface)
    RNS.Transport.add_interface(interface_b)
    RNS.Transport.prioritize_interfaces()
    _interfaces = (interface, interface_b)

    requested = BENCHMARK_CONFIG["scenarios"]
    _scenarios = build_scenarios(_instance, interface, interface_b,
                                 requested=requested)


class TestTransportThroughput(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if _scenarios is None:
            _start_transport()

    @classmethod
    def tearDownClass(cls):
        if RNS.Transport._should_run:
            RNS.Transport.exit_handler()
        if _config_dir is not None:
            import shutil
            shutil.rmtree(_config_dir, ignore_errors=True)

    def _run_scenario_matrix(self, scenario_names):
        rows = []
        # Only include scenarios selected via the command line
        scenario_names = [name for name in scenario_names
                          if name in _scenarios]
        for name in scenario_names:
            scenario = _scenarios[name]
            results = {}

            mode_filter = BENCHMARK_CONFIG["mode"]
            runs = BENCHMARK_CONFIG["runs"]

            if scenario.kind == "outbound":
                # The outbound path is synchronous; it only has an
                # inline-equivalent measurement, and follows the mode
                # filter's "inline" selector.
                if mode_filter in ("inline", "both"):
                    run_means = _bench_outbound(scenario.frames,
                                                scenario.packets_inline,
                                                runs, 0)
                    mean_us = statistics.median(run_means)
                    results["inline"] = {
                        "runs": runs,
                        "mean_us": mean_us,
                        "pps": 1e6 / mean_us,
                        "stdev": statistics.stdev(run_means) if len(run_means) > 2 else None,
                        "p50": None,
                        "p95": None,
                    }
            else:
                if mode_filter in ("inline", "both") and scenario.packets_inline:
                    n = scenario.packets_inline
                    run_means, samples = _bench_inline(scenario.interface,
                                                       scenario.frames, n, runs,
                                                       scenario.inline_offset,
                                                       scenario.fresh_per_run)
                    mean_us = statistics.median(run_means)
                    stdev = statistics.stdev(run_means) if len(run_means) > 2 else None
                    sorted_samples = sorted(samples)
                    results["inline"] = {
                        "runs": runs,
                        "mean_us": mean_us,
                        "pps": 1e6 / mean_us,
                        "stdev": stdev,
                        "p50": _percentile(sorted_samples, 0.50),
                        "p95": _percentile(sorted_samples, 0.95),
                    }

                if mode_filter in ("drainer", "both") and scenario.can_drainer():
                    n = scenario.packets_drainer
                    run_means = _bench_drainer(scenario, n, runs)
                    mean_us = statistics.median(run_means)
                    stdev = statistics.stdev(run_means) if len(run_means) > 2 else None
                    results["drainer"] = {
                        "runs": runs,
                        "mean_us": mean_us,
                        "pps": 1e6 / mean_us,
                        "stdev": stdev,
                        "p50": None,
                        "p95": None,
                    }

            if results:
                print_scenario_table(scenario, results)
                rows.append((name,
                             results.get("inline", {}).get("pps"),
                             results.get("drainer", {}).get("pps"),
                             scenario.frame_size))

        print_pps_matrix(rows)

    def test_01_transit_throughput(self):
        print("")
        print_environment_header()
        self._run_scenario_matrix([
            "transit_single_135",
            "transit_single_475",
            "transit_single_1024",
            "transit_single_16384",
            "transit_single_final",
            "transit_link_135",
            "transit_link_475",
            "transit_link_1024",
            "transit_link_16384",
            "transit_link_32768",
        ])

    def test_02_delivery_throughput(self):
        print("")
        self._run_scenario_matrix([
            "terminus_link_135",
            "terminus_link_475",
            "terminus_link_1024",
            "terminus_link_16384",
            "terminus_single",
            "announce_ingress",
            "outbound_path",
        ])


def _usage():
    return (
        "\nUsage: python3 tests/transport_throughput.py [options]\n"
        "\n"
        "Options:\n"
        "  -s, --scenario NAME   Run only the named scenario\n"
        "  --mode MODE           Measurement mode: inline, drainer or both\n"
        "                        (default: both)\n"
        "  --runs N              Measurement runs per scenario/mode, median\n"
        "                        is reported (default: 3)\n"
        "  --list-scenarios      List available scenarios and exit\n"
        "  -h, --help            Show this help and exit\n"
    )


if __name__ == "__main__":
    argv = sys.argv[1:]
    rest = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-s", "--scenario"):
            BENCHMARK_CONFIG["scenarios"] = BENCHMARK_CONFIG["scenarios"] or []
            BENCHMARK_CONFIG["scenarios"].append(argv[i + 1])
            i += 2
        elif arg == "--mode":
            mode = argv[i + 1]
            if mode not in ("inline", "drainer", "both"):
                raise SystemExit(f"Invalid mode '{mode}'" + _usage())
            BENCHMARK_CONFIG["mode"] = mode
            i += 2
        elif arg == "--runs":
            BENCHMARK_CONFIG["runs"] = max(1, int(argv[i + 1]))
            i += 2
        elif arg == "--list-scenarios":
            print("\nAvailable scenarios:")
            for name in sorted(SCENARIO_DESCRIPTIONS):
                print(f"  {name:<22} {SCENARIO_DESCRIPTIONS[name]}")
            raise SystemExit(0)
        elif arg in ("-h", "--help"):
            raise SystemExit(_usage())
        else:
            rest.append(arg)
            i += 1

    unittest.main(argv=[sys.argv[0]] + rest, verbosity=2)

# Pre:
#
# Transport Throughput - PPS matrix (median of runs)
#   scenario                      direct       drainer
#   ----------------------------------------------------------------------
#   transit_single_135           208,550       184,075     225.23 Mbps / 198.80 Mbps
#   transit_single_475           195,652       130,808     743.48 Mbps / 497.07 Mbps
#   transit_single_1024          169,828       111,446       1.39 Gbps / 912.97 Mbps
#   transit_single_16384          49,618        74,101       6.50 Gbps / 9.71 Gbps
#   transit_single_final         204,604       112,925     220.97 Mbps / 121.96 Mbps
#   transit_link_135             272,813       234,430     294.64 Mbps / 253.18 Mbps
#   transit_link_475             260,003       227,895     988.01 Mbps / 866.00 Mbps
#   transit_link_1024            232,763       145,872       1.91 Gbps / 1.19 Gbps
#   transit_link_16384            84,028        73,313      11.01 Gbps / 9.61 Gbps
#
#   terminus_single               29,813        25,663      32.20 Mbps / 27.72 Mbps
#   announce_ingress               7,561         7,242      10.10 Mbps / 9.68 Mbps
#   outbound_path                696,106             -     751.79 Mbps / -
#
# No Fastpath:
#
# Transport Throughput - PPS matrix (median of runs)
#   scenario                      direct       drainer
#   ----------------------------------------------------------------------
#   transit_single_135           247,667       162,090     267.48 Mbps / 175.06 Mbps
#   transit_single_475           233,514       159,717     887.35 Mbps / 606.92 Mbps
#   transit_single_1024          211,443       175,994       1.73 Gbps / 1.44 Gbps
#   transit_single_16384          78,963        72,532      10.35 Gbps / 9.51 Gbps
#   transit_single_final         240,855       112,702     260.12 Mbps / 121.72 Mbps
#   transit_link_135             266,614       220,571     287.94 Mbps / 238.22 Mbps
#   transit_link_475             256,347       152,410     974.12 Mbps / 579.16 Mbps
#   transit_link_1024            228,080       194,444       1.87 Gbps / 1.59 Gbps
#   transit_link_16384            82,149        73,720      10.77 Gbps / 9.66 Gbps
#
#   terminus_single               29,764        28,308      32.15 Mbps / 30.57 Mbps
#   announce_ingress               7,394         7,150       9.88 Mbps / 9.55 Mbps
#   outbound_path                872,747             -     942.57 Mbps / -
#   ----------------------------------------------------------------------
#
#
# Fastpath:
#
# Transport Throughput - PPS matrix (median of runs)
#   scenario                      direct       drainer
#   ----------------------------------------------------------------------
#   transit_single_135           407,561       411,426     440.17 Mbps / 444.34 Mbps
#   transit_single_475           378,867       377,964       1.44 Gbps / 1.44 Gbps
#   transit_single_1024          320,878       325,910       2.63 Gbps / 2.67 Gbps
#   transit_single_16384          94,265        94,357      12.36 Gbps / 12.37 Gbps
#   transit_single_final         395,245       399,247     426.86 Mbps / 431.19 Mbps
#   transit_link_135             453,216       451,863     489.47 Mbps / 488.01 Mbps
#   transit_link_475             417,013       417,294       1.58 Gbps / 1.59 Gbps
#   transit_link_1024            347,548       353,783       2.85 Gbps / 2.90 Gbps
#   transit_link_16384            96,682        96,871      12.67 Gbps / 12.70 Gbps
#
#   terminus_single               29,451        25,862      31.81 Mbps / 27.93 Mbps
#   announce_ingress               7,495         6,996      10.01 Mbps / 9.35 Mbps
#   outbound_path                840,738             -     908.00 Mbps / -
