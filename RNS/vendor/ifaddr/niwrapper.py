import ipaddress
import RNS.vendor.ifaddr
import socket

from typing import List

AF_INET6 = socket.AF_INET6.value
AF_INET = socket.AF_INET.value

def interfaces() -> List[str]:
    adapters = RNS.vendor.ifaddr.get_adapters(include_unconfigured=True)
    return [a.name for a in adapters]

def interface_names_to_indexes() -> dict:
    adapters = RNS.vendor.ifaddr.get_adapters(include_unconfigured=True)
    results = {}
    for adapter in adapters:
        results[adapter.name] = adapter.index
    return results

def interface_name_to_nice_name(ifname) -> str:
    try:
        adapters = RNS.vendor.ifaddr.get_adapters(include_unconfigured=True)
        for adapter in adapters:
            if adapter.name == ifname:
                if hasattr(adapter, "nice_name"):
                    return adapter.nice_name
    except:
        return None

    return None

def ifaddresses(ifname) -> dict:
    adapters = RNS.vendor.ifaddr.get_adapters(include_unconfigured=True)
    ifa = {}
    for a in adapters:
        if a.name == ifname:
            ipv4s = []
            ipv6s = []
            for ip in a.ips:
                t = {}
                if ip.is_IPv4:
                    net = ipaddress.ip_network(str(ip.ip)+"/"+str(ip.network_prefix), strict=False)
                    t["addr"] = ip.ip
                    t["prefix"] = ip.network_prefix
                    t["broadcast"] = str(net.broadcast_address)
                    ipv4s.append(t)
                if ip.is_IPv6:
                    t["addr"] = ip.ip[0]
                    ipv6s.append(t)

            if len(ipv4s) > 0:
                ifa[AF_INET] = ipv4s
            if len(ipv6s) > 0:
                ifa[AF_INET6] = ipv6s

    return ifa