******************
What is Reticulum?
******************

Reticulum is a cryptography-based networking stack for building both local and
wide-area networks with readily available hardware, that can continue to operate
under adverse conditions, such as extremely low bandwidth and very high latency.

Reticulum allows you to build wide-area networks with off-the-shelf tools, and
offers end-to-end encryption, forward secrecy, autoconfiguring cryptographically
backed multi-hop transport, efficient addressing, unforgeable packet
acknowledgements and more.

From a users perspective, Reticulum allows the creation of applications that
respect and empower the autonomy and sovereignty of communities and individuals.
Reticulum enables secure digital communication that cannot be subjected to
outside control, manipulation or censorship.

Reticulum enables the construction of both small and potentially planetary-scale
networks, without any need for hierarchical or beaureucratic structures to control
or manage them, while ensuring individuals and communities full sovereignty
over their own network segments.

Reticulum is a **complete networking stack**, and does not need IP or higher
layers, although it is easy to utilise IP (with TCP or UDP) as the underlying
carrier for Reticulum. It is therefore trivial to tunnel Reticulum over the
Internet or private IP networks. Reticulum is built directly on cryptographic
principles, allowing resilience and stable functionality in open and trustless
networks.

No kernel modules or drivers are required. Reticulum can run completely in
userland, and will run on practically any system that runs Python 3. Reticulum
runs well even on small single-board computers like the Pi Zero.


Current Status
==============
**Please know!** Reticulum should currently be considered beta software. All core protocol
features are implemented and functioning, but additions will probably occur as
real-world use is explored. *There will be bugs*. The API and wire-format can be
considered complete and stable at the moment, but could change if absolutely warranted.


What does Reticulum Offer?
==========================
* Coordination-less globally unique addressing and identification

* Fully self-configuring multi-hop routing

* Complete initiator anonymity, communicate without revealing your identity

* Asymmetric encryption based on X25519, and Ed25519 signatures as a basis for all communication

* Forward Secrecy by using ephemeral Elliptic Curve Diffie-Hellman keys on Curve25519

* Reticulum uses a modified version of the `Fernet <https://github.com/fernet/spec/blob/master/Spec.md>`_ specification for on-the-wire / over-the-air encryption

  * Keys are ephemeral and derived from an ECDH key exchange on Curve25519

  * AES-128 in CBC mode with PKCS7 padding

  * HMAC using SHA256 for authentication

  * IVs are generated through os.urandom()

  * No Version and Timestamp metadata included

* Unforgeable packet delivery confirmations

* A variety of supported interface types

* An intuitive and developer-friendly API

* Efficient link establishment

  * Total cost of setting up an encrypted and verified link is only 3 packets, totalling 297 bytes

  * Low cost of keeping links open at only 0.44 bits per second

* Reliable and efficient transfer of arbitrary amounts of data

  * Reticulum can handle a few bytes of data or files of many gigabytes

  * Sequencing, transfer coordination and checksumming is automatic

  * The API is very easy to use, and provides transfer progress

* Authentication and virtual network segmentation on all supported interface types

* Flexible scalability allowing extremely low-bandwidth networks to co-exist and interoperate with large, high-bandwidth networks


Where can Reticulum be Used?
============================
Over practically any medium that can support at least a half-duplex channel
with greater throughput than 5 bits per second, and an MTU of 500 bytes. Data radios,
modems, LoRa radios, serial lines, AX.25 TNCs, amateur radio digital modes,
ad-hoc WiFi, free-space optical links and similar systems are all examples
of the types of interfaces Reticulum was designed for.

An open-source LoRa-based interface called `RNode <https://unsigned.io/rnode>`_
has been designed as an example transceiver that is very suitable for
Reticulum. It is possible to build it yourself, to transform a common LoRa
development board into one, or it can be purchased as a complete transceiver
from various vendors.

Reticulum can also be encapsulated over existing IP networks, so there's
nothing stopping you from using it over wired Ethernet or your local WiFi
network, where it'll work just as well. In fact, one of the strengths of
Reticulum is how easily it allows you to connect different mediums into a
self-configuring, resilient and encrypted mesh.

As an example, it's possible to set up a Raspberry Pi connected to both a
LoRa radio, a packet radio TNC and a WiFi network. Once the interfaces are
added, Reticulum will take care of the rest, and any device on the WiFi
network can communicate with nodes on the LoRa and packet radio sides of the
network, and vice versa.

Interface Types and Devices
===========================
Reticulum implements a range of generalised interface types that covers the communications hardware that Reticulum can run over. If your hardware is not supported, it's relatively simple to implement an interface class. Currently, Reticulum can use the following devices and communication mediums:

* Any Ethernet device

  * WiFi devices

  * Wired Ethernet devices

  * Fibre-optic transceivers

  * Data radios with Ethernet ports

* LoRa using `RNode <https://unsigned.io/rnode>`_

  * Can be installed on `many popular LoRa boards <https://github.com/markqvist/rnodeconfigutil#supported-devices>`_

  * Can be purchased as a `ready to use transceiver <https://unsigned.io/rnode>`_

* Packet Radio TNCs, such as `OpenModem <https://unsigned.io/openmodem>`_

  * Any packet radio TNC in KISS mode

  * Ideal for VHF and UHF radio

* Any device with a serial port

* The I2P network

* TCP over IP networks

* UDP over IP networks

* Anything you can connect via stdio

  * Reticulum can use external programs and pipes as interfaces

  * This can be used to easily hack in virtual interfaces

  * Or to quickly create interfaces with custom hardware

For a full list and more details, see the :ref:`Supported Interfaces<interfaces-main>` chapter.


Caveat Emptor
==============
Reticulum is an experimental networking stack, and should be considered as
such. While it has been built with cryptography best-practices very foremost in
mind, it has not yet been externally security audited, and there could very well be
privacy-breaking bugs. To be considered secure, Reticulum needs a thorough
security review by independent cryptographers and security researchers. If you
want to help out with this, or can help sponsor an audit, please do get in touch.
