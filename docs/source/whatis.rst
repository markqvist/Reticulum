******************
What is Reticulum?
******************

Reticulum is a cryptography-based networking stack for wide-area networks built on readily available hardware, and can operate even with very high latency and extremely low bandwidth.

Reticulum allows you to build very wide-area networks with off-the-shelf tools, and offers end-to-end encryption, autoconfiguring cryptographically backed multi-hop transport, efficient addressing, unforgeable packet acknowledgements and more.

Reticulum is a complete networking stack, and does not need IP or higher layers, although it is easy to utilise IP (with TCP or UDP) as the underlying carrier for Reticulum. It is therefore trivial to tunnel Reticulum over the Internet or private IP networks. Reticulum is built directly on cryptographic principles, allowing resilience and stable functionality in open and trustless networks.

No kernel modules or drivers are required. Reticulum runs completely in userland, and can run on practically any system that runs Python 3. Reticulum runs well even on small single-board computers like the Pi Zero.


Current Status
==============
Reticulum should currently be considered beta software. All core protocol features are implemented and functioning, but additions will probably occur as real-world use is explored. There will be bugs. The API and wire-format can be considered relatively stable at the moment, but could change if warranted.


Caveat Emptor
==============
Reticulum is an experimental networking stack, and should be considered as such. While it has been built with cryptography best-practices very foremost in mind, it has not been externally security audited, and there could very well be privacy-breaking bugs. To be considered secure, Reticulum needs a thourough security review by independt cryptographers and security researchers. If you want to help out, or help sponsor an audit, please do get in touch.


What does Reticulum Offer?
==========================
* Coordination-less globally unique adressing and identification

* Fully self-configuring multi-hop routing

* Complete initiator anonymity, communicate without revealing your identity

* Asymmetric X25519 encryption and Ed25519 signatures as a basis for all communication

* Forward Secrecy with ephemereal Elliptic Curve Diffie-Hellman keys on Curve25519

* Reticulum uses the `Fernet <https://github.com/fernet/spec/blob/master/Spec.md>`_ specification for on-the-wire / over-the-air encryption

  * All keys are ephemeral and derived from an ECDH key exchange on Curve25519

  * AES-128 in CBC mode with PKCS7 padding

  * HMAC using SHA256 for authentication

  * IVs are generated through os.urandom()

* Unforgeable packet delivery confirmations

* A variety of supported interface types

* An intuitive and developer-friendly API

* Reliable and efficient transfer of arbritrary amounts of data

  * Reticulum can handle a few bytes of data or files of many gigabytes

  * Sequencing, transfer coordination and checksumming is automatic

  * The API is very easy to use, and provides transfer progress

* Efficient link establishment

  * Total bandwidth cost of setting up a link is only 3 packets, totalling 237 bytes

  * Low cost of keeping links open at only 0.62 bits per second


Where can Reticulum be Used?
============================
Over practically any medium that can support at least a half-duplex channel
with 500 bits per second throughput, and an MTU of 500 bytes. Data radios,
modems, LoRa radios, serial lines, AX.25 TNCs, amateur radio digital modes,
ad-hoc WiFi, free-space optical links and similar systems are all examples
of the types of interfaces Reticulum was designed for.

An open-source LoRa-based interface called `RNode <https://unsigned.io/rnode>`_
has been designed specifically for use with Reticulum. It is possible to build
yourself, or it can be purchased as a complete transceiver that just needs a
USB connection to the host.

Reticulum can also be encapsulated over existing IP networks, so there's
nothing stopping you from using it over wired ethernet or your local WiFi
network, where it'll work just as well. In fact, one of the strengths of
Reticulum is how easily it allows you to connect different mediums into a
self-configuring, resilient and encrypted mesh.

As an example, it's possible to set up a Raspberry Pi connected to both a
LoRa radio, a packet radio TNC and a WiFi network. Once the interfaces are
configured, Reticulum will take care of the rest, and any device on the WiFi
network can communicate with nodes on the LoRa and packet radio sides of the
network, and vice versa.

Interface Types and Devices
===========================
Reticulum implements a range of generalised interface types that covers most of the communications hardware that Reticulum can run over. If your hardware is not supported, it's relatively simple to implement an interface class. Currently, the following interfaces are supported:

* Any ethernet device

* LoRa using `RNode <https://unsigned.io/rnode>`_

* Packet Radio TNCs, such as `OpenModem <https://unsigned.io/openmodem>`_

* Any device with a serial port

* TCP over IP networks

* UDP over IP networks

For a full list and more details, see the :ref:`Supported Interfaces<interfaces-main>` chapter.