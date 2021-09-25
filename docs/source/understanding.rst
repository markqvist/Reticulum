.. _understanding-main:

***********************
Understanding Reticulum
***********************
This chapter will briefly describe the overall purpose and operating principles of Reticulum, a
networking stack designed for reliable and secure communication over high-latency, low-bandwidth
links. It should give you an overview of how the stack works, and an understanding of how to
develop networked applications using Reticulum.

This document is not an exhaustive source of information on Reticulum, at least not yet. Currently,
the best place to go for such information is the Python reference implementation of Reticulum, along
with the code examples and API reference. It is however an essential resource to understanding the
general principles of Reticulum, how to apply them when creating your own networks or software.

After reading this document, you should be well-equipped to understand how a Reticulum network
operates, what it can achieve, and how you can use it yourself. If you want to help out with the
development, this is also the place to start, since it will provide a pretty clear overview of the
sentiments and the philosophy behind Reticulum.

.. _understanding-motivation:

Motivation
==========

The primary motivation for designing and implementing Reticulum has been the current lack of
reliable, functional and secure minimal-infrastructure modes of digital communication. It is my
belief that it is highly desirable to create a cheap and reliable way to set up a wide-range digital
communication network that can securely allow exchange of information between people and
machines, with no central point of authority, control, censorship or barrier to entry.

Almost all of the various networking systems in use today share a common limitation, namely that they
require large amounts of coordination and trust to work, and to join the networks you need approval
of gatekeepers in control. This need for coordination and trust inevitably leads to an environment of
central control, where it's very easy for infrastructure operators or governments to control or alter
traffic, and censor or persecute unwanted actors.

Reticulum aims to require as little coordination and trust as possible. In fact, the only
“coordination” required is to know the characteristics of physical medium carrying Reticulum traffic.

Since Reticulum is completely medium agnostic, this could be whatever is best suited to the situation.
In some cases, this might be 1200 baud packet radio links over VHF frequencies, in other cases it might
be a microwave network using off-the-shelf radios. At the time of release of this document, the
recommended setup for development and testing is using LoRa radio modules with an open source firmware
(see the section :ref:`Reference System Setup<understanding-referencesystem>`), connected to a small
computer like a Raspberry Pi. As an example, the default reference setup provides a channel capacity
of 5.4 Kbps, and a usable direct node-to-node range of around 15 kilometers (indefinitely extendable
by using multiple hops).

.. _understanding-goals:

Goals
=====

To be as widely usable and easy to use as possible, the following goals have been used to
guide the design of Reticulum:


* **Fully useable as open source software stack**
    Reticulum must be implemented with, and be able to run using only open source software. This is
    critical to ensuring the availability, security and transparency of the system.
* **Hardware layer agnosticism**
    Reticulum shall be fully hardware agnostic, and shall be useable over a wide range
    physical networking layers, such as data radios, serial lines, modems, handheld transceivers,
    wired ethernet, wifi, or anything else that can carry a digital data stream. Hardware made for
    dedicated Reticulum use shall be as cheap as possible and use off-the-shelf components, so
    it can be easily replicated.
* **Very low bandwidth requirements**
    Reticulum should be able to function reliably over links with a transmission capacity as low
    as *1,000 bps*.
* **Encryption by default**
    Reticulum must use encryption by default where possible and applicable.
* **Unlicensed use**
    Reticulum shall be functional over physical communication mediums that do not require any
    form of license to use. Reticulum must be designed in a way, so it is usable over ISM radio
    frequency bands, and can provide functional long distance links in such conditions, for example
    by connecting a modem to a PMR or CB radio, or by using LoRa or WiFi modules.
* **Supplied software**
    Apart from the core networking stack and API, that allows a developer to build
    applications with Reticulum, a basic communication suite using Reticulum must be
    implemented and released at the same time as Reticulum itself. This shall serve both as a
    functional communication suite, and as an example and learning resource to others wishing
    to build applications with Reticulum.
* **Ease of use**
    The reference implementation of Reticulum is written in Python, to make it easy to use
    and understand. A programmer with only basic experience should be able to use
    Reticulum in their own applications.
* **Low cost**
    It shall be as cheap as possible to deploy a communication system based on Reticulum. This
    should be achieved by using cheap off-the-shelf hardware that potential users might already
    own. The cost of setting up a functioning node should be less than $100 even if all parts
    needs to be purchased.

.. _understanding-basicfunctionality:

Introduction & Basic Functionality
==================================

Reticulum is a networking stack suited for high-latency, low-bandwidth links. Reticulum is at it’s
core a *message oriented* system. It is suited for both local point-to-point or point-to-multipoint
scenarios where alle nodes are within range of each other, as well as scenarios where packets need
to be transported over multiple hops to reach the recipient.

Reticulum does away with the idea of addresses and ports known from IP, TCP and UDP. Instead
Reticulum uses the singular concept of *destinations*. Any application using Reticulum as it’s
networking stack will need to create one or more destinations to receive data, and know the
destinations it needs to send data to.

All destinations in Reticulum are represented internally as 10 bytes, derived from truncating a full
SHA-256 hash of identifying characteristics of the destination. To users, the destination addresses
will be displayed as 10 bytes in hexadecimal representation, as in the following example: ``<80e29bf7cccaf31431b3>``.

By default Reticulum encrypts all data using public-key cryptography. Any message sent to a
destination is encrypted with that destinations public key. Reticulum can also set up an encrypted
channel to a destination with *Perfect Forward Secrecy* and *Initiator Anonymity* using a elliptic
curve cryptography and ephemeral keys derived from a Diffie Hellman exchange on Curve25519. In
Reticulum terminology, this is called a *Link*.

Reticulum also offers symmetric key encryption for group-oriented communications, as well as
unencrypted packets for broadcast purposes, or situations where you need the communication to be in
plain text. The multi-hop transport, coordination, verification and reliability layers are fully
autonomous and based on public key cryptography.

Reticulum can connect to a variety of interfaces such as radio modems, data radios and serial ports,
and offers the possibility to easily tunnel Reticulum traffic over IP links such as the Internet or
private IP networks.

.. _understanding-destinations:

Destinations
------------

To receive and send data with the Reticulum stack, an application needs to create one or more
destinations. Reticulum uses three different basic destination types, and one special:


* **Single**
    The *single* destination type defines a public-key encrypted destination. Any data sent to this
    destination will be encrypted with the destination’s public key, and will only be readable by
    the creator of the destination.
* **Group**
    The *group* destination type defines a symmetrically encrypted destination. Data sent to this
    destination will be encrypted with a symmetric key, and will be readable by anyone in
    possession of the key. The *group* destination can be used just as well by only two peers, as it
    can by many.
* **Plain**
    A *plain* destination type is unencrypted, and suited for traffic that should be broadcast to a
    number of users, or should be readable by anyone. Traffic to a *plain* destination is not encrypted.
* **Link**
    A *link* is a special destination type, that serves as an abstract channel to a *single*
    destination, directly connected or over multiple hops. The *link* also offers reliability and
    more efficient encryption, forward secrecy, initiator anonymity, and as such can be useful even
    when a node is directly reachable.

.. _understanding-destinationnaming:

Destination Naming
^^^^^^^^^^^^^^^^^^

Destinations are created and named in an easy to understand dotted notation of *aspects*, and
represented on the network as a hash of this value. The hash is a SHA-256 truncated to 80 bits. The
top level aspect should always be a unique identifier for the application using the destination.
The next levels of aspects can be defined in any way by the creator of the application.

Aspects can be as long and as plentiful as required, and a resulting long destination name will not
impact efficiency, as names are always represented as truncated SHA-256 hashes on the network.

As an example, a destination for a environmental monitoring application could be made up of the
application name, a device type and measurement type, like this:

.. code-block:: text

   app name  : environmentlogger
   aspects   : remotesensor, temperature

   full name : environmentlogger.remotesensor.temperature
   hash      : fa7ddfab5213f916dea

For the *single* destination, Reticulum will automatically append the associated public key as a
destination aspect before hashing. This is done to ensure only the correct destination is reached,
since anyone can listen to any destination name. Appending the public key ensures that a given
packet is only directed at the destination that holds the corresponding private key to decrypt the
packet.

**Take note!** There is a very important concept to understand here:

* Anyone can use the destination name ``environmentlogger.remotesensor.temperature``

* Each destination that does so will still have a unique destination hash, and thus be uniquely
  addressable, because their public keys will differ.

In actual use of *single* destination naming, it is advisable not to use any uniquely identifying
features in aspect naming. Aspect names should be general terms describing what kind of destination
is represented. The uniquely identifying aspect is always acheived by the appending the public key,
which expands the destination into a uniquely identifyable one.

Any destination on a Reticulum network can be addressed and reached simply by knowning its
destination hash (and public key, but if the public key is not known, it can be requested from the
network simply by knowing the destination hash). The use of app names and aspects makes it easy to
structure Reticulum programs and makes it possible to filter what information and data your program
receives.

To recap, the different destination types should be used in the following situations:

* **Single**
    When private communication between two endpoints is needed. Supports multiple hops.
* **Group**
    When private communication between two or more endpoints is needed. Supports multiple hops
    indirectly, but must first be established through a *single* destination.
* **Plain**
    When plain-text communication is desirable, for example when broadcasting information.

To communicate with a *single* destination, you need to know it’s public key. Any method for
obtaining the public key is valid, but Reticulum includes a simple mechanism for making other
nodes aware of your destinations public key, called the *announce*. It is also possible to request
an unknown public key from the network, as all participating nodes serve as a distributed ledger
of public keys.

Note that public key information can be shared and verified in many other ways than using the
built-in *announce* functionality, and that it is therefore not required to use the announce/request
functionality to obtain public keys. It is by far the easiest though, and should definitely be used
if there is not a good reason for doing it differently.

.. _understanding-keyannouncements:

Public Key Announcements
------------------------

An *announce* will send a special packet over any configured interfaces, containing all needed
information about the destination hash and public key, and can also contain some additional,
application specific data. The entire packet is signed by the sender to ensure authenticity. It is not
required to use the announce functionality, but in many cases it will be the simplest way to share
public keys on the network. As an example, an announce in a simple messenger application might
contain the following information:


* The announcers destination hash
* The announcers public key
* Application specific data, in this case the users nickname and availability status
* A random blob, making each new announce unique
* An Ed25519 signature of the above information, verifying authenticity

With this information, any Reticulum node that receives it will be able to reconstruct an outgoing
destination to securely communicate with that destination. You might have noticed that there is one
piece of information lacking to reconstruct full knowledge of the announced destination, and that is
the aspect names of the destination. These are intentionally left out to save bandwidth, since they
will be implicit in almost all cases. If a destination name is not entirely implicit, information can be
included in the application specific data part that will allow the receiver to infer the naming.

It is important to note that announces will be forwarded throughout the network according to a
certain pattern. This will be detailed in the section
:ref:`The Announce Mechanism in Detail<understanding-announce>`.

Seeing how *single* destinations are always tied to a private/public key pair leads us to the next topic.

.. _understanding-identities:

Identities
----------

In Reticulum, an *identity* does not necessarily represent a personal identity, but is an abstraction that
can represent any kind of *verified entity*. This could very well be a person, but it could also be the
control interface of a machine, a program, robot, computer, sensor or something else entirely. In
general, any kind of agent that can act, or be acted upon, or store or manipulate information, can be
represented as an identity.

As we have seen, a *single* destination will always have an *identity* tied to it, but not *plain* or *group*
destinations. Destinations and identities share a multilateral connection. You can create a
destination, and if it is not connected to an identity upon creation, it will just create a new one to use
automatically. This may be desirable in some situations, but often you will probably want to create
the identity first, and then link it to created destinations.

Building upon the simple messenger example, we could use an identity to represent the user of the
application. Destinations created will then be linked to this identity to allow communication to
reach the user. In all cases it is of great importance to store the private keys associated with any
Reticulum Identity securely and privately.

.. _understanding-gettingfurther:

Getting Further
---------------

The above functions and principles form the core of Reticulum, and would suffice to create
functional networked applications in local clusters, for example over radio links where all interested
nodes can directly hear each other. But to be truly useful, we need a way to direct traffic over multiple
hops in the network.

In the following sections, two concepts that allow this will be introduced, *paths* and *links*.

.. _understanding-transport:

Reticulum Transport
===================

The term routing has been purposefully avoided until now. The current methods of routing used in IP-based
networks are fundamentally incompatible with the physical link types that Reticulum was designed to handle.
These routing methodologies assume trust at the physical layer, and often needs a lot more bandwidth than
Reticulum can assume is available.

Since Reticulum is designed to run over open radio spectrum, no such trust exists, and bandwidth is often
very limited. Existing routing protocols like BGP or OSPF carry too much overhead to be practically
useable over bandwidth-limited, high-latency links.

To overcome such challenges, Reticulum’s *Transport* system uses public-key cryptography to
implement the concept of *paths* that allow discovery of how to get information to a certain
destination. It is important to note that no single node in a Reticulum network knows the complete
path to a destination. Every Transport node participating in a Reticulum network will only
know what the most direct way to get a packet one hop closer to it's destination is.

.. _understanding-announce:

The Announce Mechanism in Detail
--------------------------------

When an *announce* is transmitted by a node, it will be forwarded by any node receiving it, but
according to some specific rules:


* | If this exact announce has already been received before, ignore it.

* | If not, record into a table which node the announce was received from, and how many times in
    total it has been retransmitted to get here.

* | If the announce has been retransmitted *m+1* times, it will not be forwarded. By default, *m* is
    set to 18.

* | The announce will be assigned a delay *d* = c\ :sup:`h` seconds, where *c* is a decay constant, and *h* is the amount of times this packet has already been forwarded.

* | The packet will be given a priority *p = 1/d*.

* | If at least *d* seconds has passed since the announce was received, and no other packets with a
    priority higher than *p* are waiting in the queue (see Packet Prioritisation), and the channel is
    not utilized by other traffic, the announce will be forwarded.

* | If no other nodes are heard retransmitting the announce with a greater hop count than when
    it left this node, transmitting it will be retried *r* times. By default, *r* is set to 1. Retries
    follow same rules as above, with the exception that it must wait for at least *d* = c\ :sup:`h+1` +
    t + rand(0, rw) seconds. This amount of time is equal to the amount of time it would take the next
    node to retransmit the packet, plus a random window. By default, *t* is set to 10 seconds, and the
    random window *rw* is set to 10 seconds.

* | If a newer announce from the same destination arrives, while an identical one is already in
    the queue, the newest announce is discarded. If the newest announce contains different
    application specific data, it will replace the old announce, but will use *d* and *p* of the old
    announce.

Once an announce has reached a node in the network, any other node in direct contact with that
node will be able to reach the destination the announce originated from, simply by sending a packet
addressed to that destination. Any node with knowledge of the announce will be able to direct the
packet towards the destination by looking up the next node with the shortest amount of hops to the
destination.

According to these rules and default constants, an announce will propagate throughout the network
in a predictable way. In an example network utilising the default constants, and with an average link
distance of *Lavg =* 15 kilometers, an announce will be able to propagate outwards to a radius of 180
kilometers in 34 minutes, and a *maximum announce radius* of 270 kilometers in approximately 3
days.

.. _understanding-paths:

Reaching the Destination
------------------------

In networks with changing topology and trustless connectivity, nodes need a way to establish
*verified connectivity* with each other. Since the network is assumed to be trustless, Reticulum
must provide a way to guarantee that the peer you are communicating with is actually who you
expect. Reticulum offers two ways to do this.

For exchanges of small amounts of information, Reticulum offers the *Packet* API, which works exactly like you would expect - on a per packet level. The following process is employed when sending a packet:

* | A packet is always created with an associated destination and some payload data. When the packet is sent
    to a *single* destination type, Reticulum will automatically create an ephemeral encryption key, perform
    an ECDH key exchange with the destinations public key, and encrypt the information.

* | It is important to note that this key exchange does not require any network traffic. The sender already
    knows the public key of the destination from an earlier received *announce*, and can thus perform the ECDH
    key exchange locally, before sending the packet.

* | The public part of the newly generated ephemeral key-pair is included with the encrypted token, and sent
    along with the encrypted payload data in the packet.

* | When the destination receives the packet, it can itself perform an ECDH key exchange and decrypt the
    packet.

* | A new ephemeral key is used for every packet sent in this way, and forward secrecy is guaranteed on a
    per packet level.

* | Once the packet has been received and decrypted by the addressed destination, that destination can opt
    to *prove* its receipt of the packet. It does this by calculating the SHA-256 hash of the received packet,
    and signing this hash with it's Ed25519 signing key. Transport nodes in the network can then direct this
    *proof* back to the packets origin, where the signature can be verified against the destinations known
    public signing key.

* | In case the packet is addressed to a *group* destination type, the packet will be encrypted with the
    pre-shared AES-128 key associated with the destination. In case the packet is addressed to a *plain*
    destination type, the payload data will not be encrypted. Neither of these two destination types offer
    forward secrecy. In general, it is recommended to always use the *single* destination type, unless it is
    strictly necessary to use one of the others.


For exchanges of larger amounts of data, or when longer sessions of bidirectional communication is desired, Reticulum offers the *Link* API. To establish a *link*, the following process is employed:

* | First, the node that wishes to establish a link will send out a special packet, that
    traverses the network and locates the desired destination. Along the way, the nodes that
    forward the packet will take note of this *link request*.

* | Second, if the destination accepts the *link request* , it will send back a packet that proves the
    authenticity of it’s identity (and the receipt of the link request) to the initiating node. All
    nodes that initially forwarded the packet will also be able to verify this proof, and thus
    accept the validity of the *link* throughout the network.

* | When the validity of the *link* has been accepted by forwarding nodes, these nodes will
    remember the *link* , and it can subsequently be used by referring to a hash representing it.

* | As a part of the *link request* , a Diffie-Hellman key exchange takes place, that sets up an
    efficiently encrypted tunnel between the two nodes, using elliptic curve cryptography. As such,
    this mode of communication is preferred, even for situations when nodes can directly communicate,
    when the amount of data to be exchanged numbers in the tens of packets.

* | When a *link* has been set up, it automatically provides message receipt functionality, through
    the same *proof* mechanism discussed before, so the sending node can obtain verified confirmation
    that the information reached the intended recipient.

In a moment, we will discuss the details of how this methodology is implemented, but let’s first
recap what purposes this methodology serves. We first ensure that the node answering our request
is actually the one we want to communicate with, and not a malicious actor pretending to be so.
At the same time we establish an efficient encrypted channel. The setup of this is relatively cheap in
terms of bandwidth, so it can be used just for a short exchange, and then recreated as needed, which will
also rotate encryption keys. The link can also be kept alive for longer periods of time, if this is
more suitable to the application. The procedure also inserts the *link id* , a hash calculated from the link request packet, into the memory of forwarding nodes, which means that the communicating nodes can thereafter reach each other simply by referring to this *link id*.

The combined bandwidth cost of setting up a link is 3 packets totalling 237 bytes (more info in the
:ref:`Binary Packet Format<understanding-packetformat>` section). The amount of bandwidth used on keeping
a link open is practically negligible, at 0.62 bits per second. Even on a slow 1200 bits per second packet
radio channel, 100 concurrent links will still leave 95% channel capacity for actual data.


Link Establishment in Detail
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

After exploring the basics of the announce mechanism, finding a path through the network, and an overview
of the link establishment procedure, this section will go into greater detail about the Reticulum link
establishment process.

The *link* in Reticulum terminology should not be viewed as a direct node-to-node link on the
physical layer, but as an abstract channel, that can be open for any amount of time, and can span
an arbitrary number of hops, where information will be exchanged between two nodes.


* | When a node in the network wants to establish verified connectivity with another node, it
    will randomly generate a new X25519 private/public key pair. It then creates a *link request*
    packet, and broadcast it.
  |  
  | *It should be noted that the X25519 public/private keypair mentioned above is two separate keypairs:
    An encryption key pair, used for derivation of a shared symmetric key, and a signing key pair, used
    for signing and verifying messages on the link. They are sent together over the wire, and can be
    considered as single public key for simplicity in this explanation.*

* | The *link request* is addressed to the destination hash of the desired destination, and
    contains the following data: The newly generated X25519 public key *LKi*.

* | The broadcasted packet will be directed through the network according to the rules laid out
    previously.

* | Any node that forwards the link request will store a *link id* in it’s *link table* , along with the
    amount of hops the packet had taken when received. The link id is a hash of the entire link
    request packet. If the link request packet is not *proven* by the addressed destination within some
    set amount of time, the entry will be dropped from the *link table* again.

* | When the destination receives the link request packet, it will decide whether to accept the request.
    If it is accepted, the destination will also generate a new X25519 private/public key pair, and
    perform a Diffie Hellman Key Exchange, deriving a new symmetric key that will be used to encrypt the
    channel, once it has been established.

* | A *link proof* packet is now constructed and transmitted over the network. This packet is
    addressed to the *link id* of the *link*. It contains the following data: The newly generated X25519
    public key *LKr* and an Ed25519 signature of the *link id* and *LKr* made by the signing key of
    the addressed destination.
   
* | By verifying this *link proof* packet, all nodes that originally transported the *link request*
    packet to the destination from the originator can now verify that the intended destination received
    the request and accepted it, and that the path they chose for forwarding the request was valid.
    In sucessfully carrying out this verification, the transporting nodes marks the link as active.
    An abstract bi-directional communication channel has now been established along a path in the network.

* | When the source receives the *proof* , it will know unequivocally that a verified path has been
    established to the destination. It can now also use the X25519 public key contained in the
    *link proof* to perform it's own Diffie Hellman Key Exchange and derive the symmetric key
    that is used to encrypt the channel. Information can now be exchanged reliably and securely.


It’s important to note that this methodology ensures that the source of the request does not need to
reveal any identifying information about itself. The link initiator remains completely anonymous.

When using *links*, Reticulum will automatically verify all data sent over the link, and can also
automate retransmissions if *Resources* are used.

.. _understanding-resources:

Resources
---------

For exchanging small amounts of data over a Reticulum network, the :ref:`Packet<api-packet>` interface
is sufficient, but for exchanging data that would require many packets, an efficient way to coordinate
the transfer is needed.

This is the purpose of the Reticulum :ref:`Resource<api-resource>`. A *Resource* can automatically
handle the reliable transfer of an arbitrary amount of data over an established :ref:`Link<api-link>`.
Resources can auto-compress data, will handle breaking the data into individual packets, sequencing
the transfer and reassembling the data on the other end.

:ref:`Resources<api-resource>` are programmatically very simple to use, and only requires a few lines
of codes to reliably transfer any amount of data. They can be used to transfer data stored in memory,
or stream data directly from files.

.. _understanding-referencesystem:

Reference System Setup
======================

This section will detail the recommended *Reference System Setup* for Reticulum. It is important to
note that Reticulum is designed to be usable over more or less any medium that allows you to send
and receive data in a digital form, and satisfies some very low minimum requirements. The
communication channel must support at least half-duplex operation, and provide an average
throughput of around 1000 bits per second, and supports a physical layer MTU of 500 bytes. The
Reticulum software should be able to run on more or less any hardware that can provide a Python 3.x 
runtime environment.

That being said, the reference setup has been outlined to provide a common platform for anyone
who wants to help in the development of Reticulum, and for everyone who wants to know a
recommended setup to get started. A reference system consists of three parts:

* **A channel access device**
    Or *CAD* , in short, provides access to the physical medium whereupon the communication
    takes place, for example a radio with an integrated modem. A setup with a separate modem
    connected to a radio would also be termed a “channel access device”.
* **A host device**
    Some sort of computing device that can run the necessary software, communicates with the
    channel access device, and provides user interaction.
* **A software stack**
    The software implementing the Reticulum protocol and applications using it.

The reference setup can be considered a relatively stable platform to develop on, and also to start
building networks on. While details of the implementation might change at the current stage of
development, it is the goal to maintain hardware compatibility for as long as entirely possible, and
the current reference setup has been determined to provide a functional platform for many years
into the future. The current Reference System Setup is as follows:


* **Channel Access Device**
    A data radio consisting of a LoRa radio module, and a microcontroller with open source
    firmware, that can connect to host devices via USB. It operates in either the 430, 868 or 900
    MHz frequency bands. More details can be found on the `RNode Page <https://unsigned.io/rnode>`_.
* **Host device**
    Any computer device running Linux and Python. A Raspberry Pi with a Debian based OS is
    recommended.
* **Software stack**
    The current Reference Implementation Release of Reticulum, running on a Debian based
    operating system.

It is very important to note, that the reference channel access device **does not** use the LoRaWAN
standard, but uses a custom MAC layer on top of the plain LoRa modulation! As such, you will
need a plain LoRa radio module connected to an MCU with the correct firmware. Full details on how to
get or make such a device is available on the `RNode Page <https://unsigned.io/rnode>`_.

With the current reference setup, it should be possible to get on a Reticulum network for around 100$
even if you have none of the hardware already, and need to purchase everything.

.. _understanding-protocolspecifics:

Protocol Specifics
==================

This chapter will detail protocol specific information that is essential to the implementation of
Reticulum, but non critical in understanding how the protocol works on a general level. It should be
treated more as a reference than as essential reading.


Node Types
----------

Currently Reticulum defines two node types, the *Station* and the *Peer*. A node is a *station* if it fixed
in one place, and if it is intended to be kept online most of the time. Otherwise the node is a *peer*.
This distinction is made by the user configuring the node, and is used to determine what nodes on the
network will help forward traffic, and what nodes rely on other nodes for connectivity.

If a node is a *Peer* it should be given the configuration directive ``enable_transport = No``.

If it is a *Station*, it should be given the configuration directive ``enable_transport = Yes``.


Packet Prioritisation
---------------------

Currently, Reticulum is completely priority-agnostic regarding general traffic. All traffic is handled
on a first-come, first-serve basis. Announce re-transmission are handled according to the re-transmission
times and priorities described earlier in this chapter.

It is possible that a prioritisation engine could be added to Reticulum in the future, but in
the light of Reticulums goal of equal access, doing so would need to be the subject of careful
investigation of the consequences first.


.. _understanding-packetformat:

Binary Packet Format
--------------------

.. code-block:: text

    == Reticulum Wire Format ======

    A Reticulum packet is composed of the following fields:

    [HEADER 2 bytes] [ADDRESSES 10/20 bytes] [CONTEXT 1 byte] [DATA 0-477 bytes]

    * The HEADER field is 2 bytes long.
      * Byte 1: [Header Type], [Propagation Type], [Destination Type] and [Packet Type]
      * Byte 2: Number of hops

    * The ADDRESSES field contains either 1 or 2 addresses.
      * Each address is 10 bytes long.
      * The Header Type flag in the HEADER field determines
        whether the ADDRESSES field contains 1 or 2 addresses.
      * Addresses are Reticulum hashes truncated to 10 bytes.

    * The CONTEXT field is 1 byte.
      * It is used by Reticulum to determine packet context.

    * The DATA field is between 0 and 477 bytes.
      * It contains the packets data payload.

    Header Types
    -----------------
    type 1          00  Two byte header, one 10 byte address field
    type 2          01  Two byte header, two 10 byte address fields
    type 3          10  Reserved
    type 4          11  Reserved


    Propagation Types
    -----------------
    broadcast       00
    transport       01
    reserved        10
    reserved        11


    Destination Types
    -----------------
    single          00
    group           01
    plain           10
    link            11


    Packet Types
    -----------------
    data            00
    announce        01
    link request    10
    proof           11


    +- Packet Example -+

       HEADER FIELD             ADDRESSES FIELD             CONTEXT FIELD  DATA FIELD
     _______|_______   ________________|________________   ________|______   __|_
    |               | |                                 | |               | |    |
    01010000 00000100 [ADDR1, 10 bytes] [ADDR2, 10 bytes] [CONTEXT, 1 byte] [DATA]
     | | | |    |
     | | | |    +-- Hops             = 4
     | | | +------- Packet Type      = DATA
     | | +--------- Destination Type = SINGLE
     | +----------- Propagation Type = TRANSPORT
     +------------- Header Type      = HEADER_2 (two byte header, two address fields)


     +- Packet Example -+

       HEADER FIELD    ADDRESSES FIELD    CONTEXT FIELD  DATA FIELD
     _______|_______   _______|_______   ________|______   __|_
    |               | |               | |               | |    |
    00000000 00000111 [ADDR1, 10 bytes] [CONTEXT, 1 byte] [DATA]
     | | | |    |
     | | | |    +-- Hops             = 7
     | | | +------- Packet Type      = DATA
     | | +--------- Destination Type = SINGLE
     | +----------- Propagation Type = BROADCAST
     +------------- Header Type      = HEADER_1 (two byte header, one address field)


     Size examples of different packet types
     ---------------------------------------

     The following table lists example sizes of various
     packet types. The size listed are the complete on-
     wire size including all fields.

     - Path Request    :    33  bytes
     - Announce        :    151 bytes
     - Link Request    :    77  bytes
     - Link Proof      :    77  bytes
     - Link RTT packet :    83  bytes
     - Link keepalive  :    14  bytes