# MIT License
#
# Copyright (c) 2014 Stefan C. Mueller
# Copyright (c) 2025 Mark Qvist
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

import os
import socket
import ipaddress
import platform
import ctypes.util
import collections
from typing import List, Iterable, Optional, Tuple, Union

AF_INET6 = socket.AF_INET6.value
AF_INET = socket.AF_INET.value

def interfaces() -> List[str]:
    adapters = get_adapters(include_unconfigured=True)
    return [a.name for a in adapters]

def interface_names_to_indexes() -> dict:
    adapters = get_adapters(include_unconfigured=True)
    results = {}
    for adapter in adapters:
        results[adapter.name] = adapter.index
    return results

def interface_name_to_nice_name(ifname) -> str:
    try:
        adapters = get_adapters(include_unconfigured=True)
        for adapter in adapters:
            if adapter.name == ifname:
                if hasattr(adapter, "nice_name"):
                    return adapter.nice_name

    except: return None
    return None

def ifaddresses(ifname) -> dict:
    adapters = get_adapters(include_unconfigured=True)
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

            if len(ipv4s) > 0: ifa[AF_INET] = ipv4s
            if len(ipv6s) > 0: ifa[AF_INET6] = ipv6s

    return ifa

def get_adapters(include_unconfigured=False):
    if os.name == "posix": return _get_adapters_posix(include_unconfigured=include_unconfigured)
    elif os.name == "nt":  return _get_adapters_win(include_unconfigured=include_unconfigured)
    else: raise RuntimeError(f"Unsupported Operating System: {os.name}")

class Adapter(object):
    def __init__(self, name: str, nice_name: str, ips: List["IP"], index: Optional[int] = None) -> None:
        self.name = name
        self.nice_name = nice_name
        self.ips = ips
        self.index = index

    def __repr__(self) -> str:
        return "Adapter(name={name}, nice_name={nice_name}, ips={ips}, index={index})".format(
            name=repr(self.name), nice_name=repr(self.nice_name), ips=repr(self.ips), index=repr(self.index))

_IPv4Address = str
_IPv6Address = Tuple[str, int, int]
class IP(object):
    def __init__(self, ip: Union[_IPv4Address, _IPv6Address], network_prefix: int, nice_name: str) -> None:
        self.ip = ip
        self.network_prefix = network_prefix
        self.nice_name = nice_name

    @property
    def is_IPv4(self) -> bool: return not isinstance(self.ip, tuple)

    @property
    def is_IPv6(self) -> bool: return isinstance(self.ip, tuple)

    def __repr__(self) -> str:
        return "IP(ip={ip}, network_prefix={network_prefix}, nice_name={nice_name})".format(ip=repr(self.ip), network_prefix=repr(self.network_prefix), nice_name=repr(self.nice_name))

if platform.system() == "Darwin" or "BSD" in platform.system():
    class sockaddr(ctypes.Structure):
        _fields_ = [
            ("sa_len", ctypes.c_uint8),
            ("sa_familiy", ctypes.c_uint8),
            ("sa_data", ctypes.c_uint8 * 14)]

    class sockaddr_in(ctypes.Structure):
        _fields_ = [
            ("sa_len", ctypes.c_uint8),
            ("sa_familiy", ctypes.c_uint8),
            ("sin_port", ctypes.c_uint16),
            ("sin_addr", ctypes.c_uint8 * 4),
            ("sin_zero", ctypes.c_uint8 * 8)]

    class sockaddr_in6(ctypes.Structure):
        _fields_ = [
            ("sa_len", ctypes.c_uint8),
            ("sa_familiy", ctypes.c_uint8),
            ("sin6_port", ctypes.c_uint16),
            ("sin6_flowinfo", ctypes.c_uint32),
            ("sin6_addr", ctypes.c_uint8 * 16),
            ("sin6_scope_id", ctypes.c_uint32)]

else:
    class sockaddr(ctypes.Structure):  # type: ignore
        _fields_ = [("sa_familiy", ctypes.c_uint16), ("sa_data", ctypes.c_uint8 * 14)]

    class sockaddr_in(ctypes.Structure):  # type: ignore
        _fields_ = [
            ("sin_familiy", ctypes.c_uint16),
            ("sin_port", ctypes.c_uint16),
            ("sin_addr", ctypes.c_uint8 * 4),
            ("sin_zero", ctypes.c_uint8 * 8)]

    class sockaddr_in6(ctypes.Structure):  # type: ignore
        _fields_ = [
            ("sin6_familiy", ctypes.c_uint16),
            ("sin6_port", ctypes.c_uint16),
            ("sin6_flowinfo", ctypes.c_uint32),
            ("sin6_addr", ctypes.c_uint8 * 16),
            ("sin6_scope_id", ctypes.c_uint32)]

def sockaddr_to_ip(sockaddr_ptr: "ctypes.pointer[sockaddr]") -> Optional[Union[_IPv4Address, _IPv6Address]]:
    if sockaddr_ptr:
        if sockaddr_ptr[0].sa_familiy == socket.AF_INET:
            ipv4 = ctypes.cast(sockaddr_ptr, ctypes.POINTER(sockaddr_in))
            ippacked = bytes(bytearray(ipv4[0].sin_addr))
            ip = str(ipaddress.ip_address(ippacked))
            return ip
        elif sockaddr_ptr[0].sa_familiy == socket.AF_INET6:
            ipv6 = ctypes.cast(sockaddr_ptr, ctypes.POINTER(sockaddr_in6))
            flowinfo = ipv6[0].sin6_flowinfo
            ippacked = bytes(bytearray(ipv6[0].sin6_addr))
            ip = str(ipaddress.ip_address(ippacked))
            scope_id = ipv6[0].sin6_scope_id
            return (ip, flowinfo, scope_id)
    return None


def ipv6_prefixlength(address: ipaddress.IPv6Address) -> int:
    prefix_length = 0
    for i in range(address.max_prefixlen):
        if int(address) >> i & 1: prefix_length = prefix_length + 1
    return prefix_length

if os.name == "posix":
    class ifaddrs(ctypes.Structure): pass
    ifaddrs._fields_ = [
        ("ifa_next", ctypes.POINTER(ifaddrs)),
        ("ifa_name", ctypes.c_char_p),
        ("ifa_flags", ctypes.c_uint),
        ("ifa_addr", ctypes.POINTER(sockaddr)),
        ("ifa_netmask", ctypes.POINTER(sockaddr)),]

    libc = ctypes.CDLL(ctypes.util.find_library("socket" if os.uname()[0] == "SunOS" else "c"), use_errno=True) # type: ignore

    def _get_adapters_posix(include_unconfigured: bool = False) -> Iterable[Adapter]:
        addr0 = addr = ctypes.POINTER(ifaddrs)()
        retval = libc.getifaddrs(ctypes.byref(addr))
        if retval != 0:
            eno = ctypes.get_errno()
            raise OSError(eno, os.strerror(eno))

        ips = collections.OrderedDict()

        def add_ip(adapter_name: str, ip: Optional[IP]) -> None:
            if adapter_name not in ips:
                index = None  # type: Optional[int]
                try:
                    index = socket.if_nametoindex(adapter_name) # type: ignore
                except (OSError, AttributeError): pass
                ips[adapter_name] = Adapter(adapter_name, adapter_name, [], index=index)
            if ip is not None:
                ips[adapter_name].ips.append(ip)

        while addr:
            name = addr[0].ifa_name.decode(encoding="UTF-8")
            ip_addr = sockaddr_to_ip(addr[0].ifa_addr)
            if ip_addr:
                if addr[0].ifa_netmask and not addr[0].ifa_netmask[0].sa_familiy:
                    addr[0].ifa_netmask[0].sa_familiy = addr[0].ifa_addr[0].sa_familiy
                netmask = sockaddr_to_ip(addr[0].ifa_netmask)
                if isinstance(netmask, tuple):
                    netmaskStr = str(netmask[0])
                    prefixlen = ipv6_prefixlength(ipaddress.IPv6Address(netmaskStr))
                else:
                    assert netmask is not None, f"sockaddr_to_ip({addr[0].ifa_netmask}) returned None"
                    netmaskStr = str("0.0.0.0/" + netmask)
                    prefixlen = ipaddress.IPv4Network(netmaskStr).prefixlen
                ip = IP(ip_addr, prefixlen, name)
                add_ip(name, ip)
            else:
                if include_unconfigured:
                    add_ip(name, None)
            addr = addr[0].ifa_next

        libc.freeifaddrs(addr0)
        return ips.values()

elif os.name == "nt":
    from ctypes import wintypes
    NO_ERROR = 0
    ERROR_BUFFER_OVERFLOW = 111
    MAX_ADAPTER_NAME_LENGTH = 256
    MAX_ADAPTER_DESCRIPTION_LENGTH = 128
    MAX_ADAPTER_ADDRESS_LENGTH = 8
    AF_UNSPEC = 0

    class SOCKET_ADDRESS(ctypes.Structure): _fields_ = [("lpSockaddr", ctypes.POINTER(sockaddr)), ("iSockaddrLength", wintypes.INT)]
    class IP_ADAPTER_UNICAST_ADDRESS(ctypes.Structure): pass
    IP_ADAPTER_UNICAST_ADDRESS._fields_ = [
        ("Length", wintypes.ULONG),
        ("Flags", wintypes.DWORD),
        ("Next", ctypes.POINTER(IP_ADAPTER_UNICAST_ADDRESS)),
        ("Address", SOCKET_ADDRESS),
        ("PrefixOrigin", ctypes.c_uint),
        ("SuffixOrigin", ctypes.c_uint),
        ("DadState", ctypes.c_uint),
        ("ValidLifetime", wintypes.ULONG),
        ("PreferredLifetime", wintypes.ULONG),
        ("LeaseLifetime", wintypes.ULONG),
        ("OnLinkPrefixLength", ctypes.c_uint8)]

    class IP_ADAPTER_ADDRESSES(ctypes.Structure): pass
    IP_ADAPTER_ADDRESSES._fields_ = [
        ("Length", wintypes.ULONG),
        ("IfIndex", wintypes.DWORD),
        ("Next", ctypes.POINTER(IP_ADAPTER_ADDRESSES)),
        ("AdapterName", ctypes.c_char_p),
        ("FirstUnicastAddress", ctypes.POINTER(IP_ADAPTER_UNICAST_ADDRESS)),
        ("FirstAnycastAddress", ctypes.c_void_p),
        ("FirstMulticastAddress", ctypes.c_void_p),
        ("FirstDnsServerAddress", ctypes.c_void_p),
        ("DnsSuffix", ctypes.c_wchar_p),
        ("Description", ctypes.c_wchar_p),
        ("FriendlyName", ctypes.c_wchar_p)]

    iphlpapi = ctypes.windll.LoadLibrary("Iphlpapi") # type: ignore

    def _enumerate_interfaces_of_adapter_win(nice_name: str, address: IP_ADAPTER_UNICAST_ADDRESS) -> Iterable[IP]:
        # Iterate through linked list and fill list
        addresses = [] # type: List[IP_ADAPTER_UNICAST_ADDRESS]
        while True:
            addresses.append(address)
            if not address.Next: break
            address = address.Next[0]

        for address in addresses:
            ip = sockaddr_to_ip(address.Address.lpSockaddr)
            assert ip is not None, f"sockaddr_to_ip({address.Address.lpSockaddr}) returned None"
            network_prefix = address.OnLinkPrefixLength
            yield IP(ip, network_prefix, nice_name)

    def _get_adapters_win(include_unconfigured: bool = False) -> Iterable[Adapter]:
        addressbuffersize = wintypes.ULONG(15 * 1024)
        retval = ERROR_BUFFER_OVERFLOW
        while retval == ERROR_BUFFER_OVERFLOW:
            addressbuffer = ctypes.create_string_buffer(addressbuffersize.value)
            retval = iphlpapi.GetAdaptersAddresses(
                wintypes.ULONG(AF_UNSPEC),
                wintypes.ULONG(0),
                None,
                ctypes.byref(addressbuffer),
                ctypes.byref(addressbuffersize))

        if retval != NO_ERROR:
            raise ctypes.WinError() # type: ignore

        # Iterate through adapters and fill array
        address_infos = []  # type: List[IP_ADAPTER_ADDRESSES]
        address_info = IP_ADAPTER_ADDRESSES.from_buffer(addressbuffer)
        while True:
            address_infos.append(address_info)
            if not address_info.Next: break
            address_info = address_info.Next[0]

        # Iterate through unicast addresses
        result = [] # type: List[Adapter]
        for adapter_info in address_infos:
            name = adapter_info.AdapterName.decode()
            nice_name = adapter_info.Description
            index = adapter_info.IfIndex

            if adapter_info.FirstUnicastAddress:
                ips = _enumerate_interfaces_of_adapter_win(adapter_info.FriendlyName, adapter_info.FirstUnicastAddress[0])
                ips = list(ips)
                result.append(Adapter(name, nice_name, ips, index=index))
            
            elif include_unconfigured: result.append(Adapter(name, nice_name, [], index=index))

        return result