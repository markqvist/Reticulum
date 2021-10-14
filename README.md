Reticulum Network Stack β
==========

Reticulum is a cryptography-based networking stack for wide-area networks built on readily available hardware, and can operate even with very high latency and extremely low bandwidth. Reticulum allows you to build very wide-area networks with off-the-shelf tools, and offers end-to-end encryption, autoconfiguring cryptographically backed multi-hop transport, efficient addressing, unforgeable packet acknowledgements and more.

Reticulum is a complete networking stack, and does not need IP or higher layers, although it is easy to use IP (with TCP or UDP) as the underlying carrier for Reticulum. It is therefore trivial to tunnel Reticulum over the Internet or private IP networks.

Having no dependencies on traditional networking stacks free up overhead that has been utilised to implement a networking stack built directly on cryptographic principles, allowing resilience and stable functionality in open and trustless networks.

No kernel modules or drivers are required. Reticulum runs completely in userland, and can run on practically any system that runs Python 3.

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
    - Total bandwidth cost of setting up a link is 3 packets totalling 237 bytes
    - Low cost of keeping links open at only 0.62 bits per second

## Examples of Reticulum Applications
If you want to quickly get an idea of what Reticulum can do, take a look at the following resources.

 - For an off-grid, encrypted and resilient mesh communications platform, see [Nomad Network](https://github.com/markqvist/NomadNet)
 - For a distributed, delay and disruption tolerant message transfer protocol built on Reticulum, see [LXMF](https://github.com/markqvist/lxmf)

## Where can Reticulum be used?
Over practically any medium that can support at least a half-duplex channel with 500 bits per second throughput, and an MTU of 500 bytes. Data radios, modems, LoRa radios, serial lines, AX.25 TNCs, amateur radio digital modes, ad-hoc WiFi, free-space optical links and similar systems are all examples of the types of interfaces Reticulum was designed for.

An open-source LoRa-based interface called [RNode](https://unsigned.io/projects/rnode/) has been designed specifically for use with Reticulum. It is possible to build yourself, or it can be purchased as a complete transceiver that just needs a USB connection to the host.

Reticulum can also be encapsulated over existing IP networks, so there's nothing stopping you from using it over wired ethernet or your local WiFi network, where it'll work just as well. In fact, one of the strengths of Reticulum is how easily it allows you to connect different mediums into a self-configuring, resilient and encrypted mesh.

As an example, it's possible to set up a Raspberry Pi connected to both a LoRa radio, a packet radio TNC and a WiFi network. Once the interfaces are configured, Reticulum will take care of the rest, and any device on the WiFi network can communicate with nodes on the LoRa and packet radio sides of the network, and vice versa.

## Current Status
Reticulum should currently be considered beta software. All core protocol features are implemented and functioning, but additions will probably occur as real-world use is explored. There will be bugs. The API and wire-format can be considered relatively stable at the moment, but could change if warranted.

## Supported interface types and devices

Reticulum implements a range of generalised interface types that covers most of the communications hardware that Reticulum can run over. If your hardware is not supported, it's relatively simple to implement an interface class. Currently, the following interfaces are supported:

 - Any ethernet device
 - LoRa using [RNode](https://unsigned.io/projects/rnode/)
 - Packet Radio TNCs (with or without AX.25)
 - Any device with a serial port
 - TCP over IP networks
 - UDP over IP networks



## Feature Roadmap
 - Stream mode for links
 - More interface types for even broader compatibility
   - ESP32 devices (ESP-Now, Bluetooth, etc.)
   - More LoRa transceivers
   - AT-compatible modems
   - CAN-bus
   - ZeroMQ
   - MQTT
   - SPI
   - i²c

## Dependencies:
 - Python 3
 - cryptography.io
 - pyserial

## How do I get started?
The best way to get started with the Reticulum Network Stack depends on what
you want to do. For full details and examples, have a look at the [Getting Started Fast](https://markqvist.github.io/Reticulum/manual/gettingstartedfast.html) section of the [Reticulum Manual](https://markqvist.github.io/Reticulum/manual/).

If you just need Reticulum as a dependency for another application, the easiest way is via pip:

```bash
pip3 install rns
```

The default config file contains examples for using Reticulum with LoRa transceivers (specifically [RNode](https://unsigned.io/projects/rnode/)), packet radio TNCs/modems and UDP. By default a UDP interface is already enabled in the default config, which will enable Reticulum communication in your local ethernet broadcast domain.

You can use the examples in the config file to expand communication over other mediums such as packet radio or LoRa, or over fast IP links using the UDP interface. I'll add in-depth tutorials and explanations on these topics later. For now, the included examples will hopefully be enough to get started.

## Support Reticulum
You can help support the continued development of open, free and private communications systems by donating via one of the following channels:

- Ethereum: 0x81F7B979fEa6134bA9FD5c701b3501A2e61E897a
- Bitcoin: 3CPmacGm34qYvR6XWLVEJmi2aNe3PZqUuq
- Ko-Fi: https://ko-fi.com/markqvist

## Caveat Emptor
Reticulum is experimental software, and should be considered as such. While it has been built with cryptography best-practices very foremost in mind, it _has not_ been externally security audited, and there could very well be privacy-breaking bugs. If you want to help out, or help sponsor an audit, please do get in touch.
