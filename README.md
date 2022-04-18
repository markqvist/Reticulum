Reticulum Network Stack β
==========

<p align="center"><img width="200" src="https://unsigned.io/wp-content/uploads/2022/03/reticulum_logo_512.png"></p>

Reticulum is the cryptography-based networking stack for wide-area networks built on readily available hardware. It can operate even with very high latency and extremely low bandwidth. Reticulum allows you to build wide-area networks with off-the-shelf tools, and offers end-to-end encryption and connectivity, initiator anonymity, autoconfiguring cryptographically backed multi-hop transport, efficient addressing, unforgeable delivery acknowledgements and more.

Reticulum is a complete networking stack, and does not need IP or higher layers, although it is easy to use IP (with TCP or UDP) as the underlying carrier for Reticulum. It is therefore trivial to tunnel Reticulum over the Internet or private IP networks.

Having no dependencies on traditional networking stacks free up overhead that has been utilised to implement a networking stack built directly on cryptographic principles, allowing resilience and stable functionality in open and trustless networks.

No kernel modules or drivers are required. Reticulum runs completely in userland, and can run on practically any system that runs Python 3.

## Read The Manual
The full documentation for Reticulum is available at [markqvist.github.io/Reticulum/manual/](https://markqvist.github.io/Reticulum/manual/).

You can also [download the Reticulum manual as a PDF](https://github.com/markqvist/Reticulum/raw/master/docs/Reticulum%20Manual.pdf)

For more info, see [unsigned.io/projects/reticulum](https://unsigned.io/projects/reticulum/)

## Notable Features
- Coordination-less globally unique adressing and identification
- Fully self-configuring multi-hop routing
- Complete initiator anonymity, communicate without revealing your identity
- Asymmetric X25519 encryption and Ed25519 signatures as a basis for all communication
- Forward Secrecy with ephemereal Elliptic Curve Diffie-Hellman keys on Curve25519
- Reticulum uses the [Fernet](https://github.com/fernet/spec/blob/master/Spec.md) specification for on-the-wire / over-the-air encryption
  - Keys are ephemeral and derived from an ECDH key exchange on Curve25519
  - AES-128 in CBC mode with PKCS7 padding
  - HMAC using SHA256 for authentication
  - IVs are generated through os.urandom()
- Unforgeable packet delivery confirmations
- A variety of supported interface types
- An intuitive and easy-to-use API
- Reliable and efficient transfer of arbritrary amounts of data
  - Reticulum can handle a few bytes of data or files of many gigabytes
  - Sequencing, transfer coordination and checksumming is automatic
  - The API is very easy to use, and provides transfer progress
- Lightweight, flexible and expandable Request/Response mechanism
- Efficient link establishment
  - Total bandwidth cost of setting up an encrypted link is 3 packets totalling 237 bytes
  - Low cost of keeping links open at only 0.62 bits per second

## Examples of Reticulum Applications
If you want to quickly get an idea of what Reticulum can do, take a look at the following resources.

- [LXMF](https://github.com/markqvist/lxmf) is a distributed, delay and disruption tolerant message transfer protocol built on Reticulum
- For an off-grid, encrypted and resilient mesh communications platform, see [Nomad Network](https://github.com/markqvist/NomadNet)
- The Android, Linux and macOS app [Sideband](https://unsigned.io/sideband) has a graphical interface and focuses on ease of use.

## Where can Reticulum be used?
Over practically any medium that can support at least a half-duplex channel with 500 bits per second throughput, and an MTU of 500 bytes. Data radios, modems, LoRa radios, serial lines, AX.25 TNCs, amateur radio digital modes, ad-hoc WiFi, free-space optical links and similar systems are all examples of the types of interfaces Reticulum was designed for.

An open-source LoRa-based interface called [RNode](https://unsigned.io/projects/rnode/) has been designed specifically for use with Reticulum. It is possible to build yourself, or it can be purchased as a complete transceiver that just needs a USB connection to the host.

Reticulum can also be encapsulated over existing IP networks, so there's nothing stopping you from using it over wired ethernet or your local WiFi network, where it'll work just as well. In fact, one of the strengths of Reticulum is how easily it allows you to connect different mediums into a self-configuring, resilient and encrypted mesh.

As an example, it's possible to set up a Raspberry Pi connected to both a LoRa radio, a packet radio TNC and a WiFi network. Once the interfaces are configured, Reticulum will take care of the rest, and any device on the WiFi network can communicate with nodes on the LoRa and packet radio sides of the network, and vice versa.

## How do I get started?
The best way to get started with the Reticulum Network Stack depends on what
you want to do. For full details and examples, have a look at the [Getting Started Fast](https://markqvist.github.io/Reticulum/manual/gettingstartedfast.html) section of the [Reticulum Manual](https://markqvist.github.io/Reticulum/manual/).

To simply install Reticulum and related utilities on your system, the easiest way is via pip:

```bash
pip3 install rns
```

You can then start any program that uses Reticulum, or start Reticulum as a system service with [the rnsd utility](https://markqvist.github.io/Reticulum/manual/using.html#the-rnsd-utility).

When first started, Reticulum will create a default configuration file, providing basic connectivity to other Reticulum peers. The default config file contains examples for using Reticulum with LoRa transceivers (specifically [RNode](https://unsigned.io/projects/rnode/)), packet radio TNCs/modems, TCP and UDP.

You can use the examples in the config file to expand communication over many mediums such as packet radio or LoRa (with [RNode](https://unsigned.io/projects/rnode/)), serial ports, or over fast IP links and the Internet using the UDP and TCP interfaces. For more detailed examples, take a look at the [Supported Interfaces](https://markqvist.github.io/Reticulum/manual/interfaces.html) section of the [Reticulum Manual](https://markqvist.github.io/Reticulum/manual/).

## Current Status
Reticulum should currently be considered beta software. All core protocol features are implemented and functioning, but additions will probably occur as real-world use is explored. There will be bugs. The API and wire-format can be considered relatively stable at the moment, but could change if warranted.

## Supported interface types and devices

Reticulum implements a range of generalised interface types that covers most of the communications hardware that Reticulum can run over. If your hardware is not supported, it's relatively simple to implement an interface class. I will gratefully accept pull requests for custom interfaces if they are generally useful.

Currently, the following interfaces are supported:

- Any ethernet device
- LoRa using [RNode](https://unsigned.io/projects/rnode/)
- Packet Radio TNCs (with or without AX.25)
- KISS-compatible hardware and software modems
- Any device with a serial port
- TCP over IP networks
- UDP over IP networks

## Development Roadmap
- Version 0.3.5
  - Improved announce propagation and flexible scalability
  - Physical layer segmentation & authentication, see [#23](https://github.com/markqvist/Reticulum/discussions/23)
  - Improving [the manual](https://markqvist.github.io/Reticulum/manual/) with sections specifically for beginners
  - Foundational support for networks of multi-planetary scale and size
- Version 0.3.6
  - Support for radio and modem interfaces on Android
  - GUI interface configuration tool
  - Easy way to share interface configurations, see [#19](https://github.com/markqvist/Reticulum/discussions/19)
- Version 0.3.7
  - More interface types for even broader compatibility
    - Plain ESP32 devices (ESP-Now, WiFi, Bluetooth, etc.)
    - More LoRa transceivers
    - AT-compatible modems
    - IR Transceivers
    - AWDL / OWL
    - HF Modems
    - CAN-bus
    - ZeroMQ
    - MQTT
    - SPI
    - i²c
- Planned, but not yet scheduled
  - Globally routable multicast
  - A portable Reticulum implementation in C, see [#21](https://github.com/markqvist/Reticulum/discussions/21)



## Dependencies:
- Python 3.6
- cryptography.io
- netifaces
- pyserial

## Public Testnet

If you just want to get started experimenting without building any physical networks, you are welcome to join the Unsigned.io RNS Testnet. The testnet is just that, an informal network for testing and experimenting. It will be up most of the time, and anyone can join, but it also means that there's no guarantees for service availability.

The testnet runs the very latest version of Reticulum (often even a short while before it is publicly released). Sometimes experimental versions of Reticulum might be deployed to nodes on the testnet, which means strange behaviour might occur. If none of that scares you, you can join the testnet via eihter TCP or I2P. Just add one of the following interfaces to your Reticulum configuration file:

```
# For connecting over TCP/IP:

  [[RNS Testnet Frankfurt]]
    type = TCPClientInterface
    interface_enabled = yes
    outgoing = True
    target_host = frankfurt.rns.unsigned.io
    target_port = 4965


# For connecting over I2P:

  [[RNS Testnet I2P Node A]]
    type = I2PInterface
    interface_enabled = yes
    peers = ykzlw5ujbaqc2xkec4cpvgyxj257wcrmmgkuxqmqcur7cq3w3lha.b32.i2p
```

The testnet also contains a number of [Nomad Network](https://github.com/markqvist/nomadnet) nodes, and LXMF propagation nodes.

## Support Reticulum
You can help support the continued development of open, free and private communications systems by donating via one of the following channels:

- Ethereum: 0x81F7B979fEa6134bA9FD5c701b3501A2e61E897a
- Bitcoin: 3CPmacGm34qYvR6XWLVEJmi2aNe3PZqUuq
- Ko-Fi: https://ko-fi.com/markqvist

Are certain features in the development roadmap are important to you or your organisation? Make them a reality quickly by sponsoring their implementation.

## Caveat Emptor
Reticulum is relatively young software, and should be considered as such. While it has been built with cryptography best-practices very foremost in mind, it _has not_ been externally security audited, and there could very well be privacy-breaking bugs. If you want to help out, or help sponsor an audit, please do get in touch.
