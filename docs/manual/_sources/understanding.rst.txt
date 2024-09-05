.. _understanding-main:

***********************
Understanding Reticulum
***********************
This chapter will briefly describe the overall purpose and operating principles of Reticulum.
It should give you an overview of how the stack works, and an understanding of how to
develop networked applications using Reticulum.

This chapter is not an exhaustive source of information on Reticulum, at least not yet. Currently,
the only complete repository, and final authority on how Reticulum actually functions, is the Python
reference implementation and API reference. That being said, this chapter is an essential resource in
understanding how Reticulum works from a high-level perspective, along with the general principles of
Reticulum, and how to apply them when creating your own networks or software.

After reading this document, you should be well-equipped to understand how a Reticulum network
operates, what it can achieve, and how you can use it yourself. If you want to help out with the
development, this is also the place to start, since it will provide a pretty clear overview of the
sentiments and the philosophy behind Reticulum, what problems it seeks to solve, and how it
approaches those solutions.

.. _understanding-motivation:

Motivation
==========

The primary motivation for designing and implementing Reticulum has been the current lack of
reliable, functional and secure minimal-infrastructure modes of digital communication. It is my
belief that it is highly desirable to create a reliable and efficient way to set up long-range digital
communication networks that can securely allow exchange of information between people and
machines, with no central point of authority, control, censorship or barrier to entry.

Almost all of the various networking systems in use today share a common limitation: They
require large amounts of coordination and centralised trust and power to function. To join such networks, you need approval
of gatekeepers in control. This need for coordination and trust inevitably leads to an environment of
central control, where it's very easy for infrastructure operators or governments to control or alter
traffic, and censor or persecute unwanted actors. It also makes it completely impossible to freely deploy
and use networks at will, like one would use other common tools that enhance individual agency and freedom.

Reticulum aims to require as little coordination and trust as possible. It aims to make secure,
anonymous and permissionless networking and information exchange a tool that anyone can just pick up and use.

Since Reticulum is completely medium agnostic, it can be used to build networks on whatever is best
suited to the situation, or whatever you have available. In some cases, this might be packet radio
links over VHF frequencies, in other cases it might be a 2.4 GHz
network using off-the-shelf radios, or it might be using common LoRa development boards.

At the time of release of this document, the fastest and easiest setup for development and testing is using
LoRa radio modules with an open source firmware (see the section :ref:`Reference Setup<understanding-referencesystem>`),
connected to any kind of computer or mobile device that Reticulum can run on.

The ultimate aim of Reticulum is to allow anyone to be their own network operator, and to make it
cheap and easy to cover vast areas with a myriad of independent, interconnectable and autonomous networks.
Reticulum **is not** *one network*, it **is a tool** to build *thousands of networks*. Networks without
kill-switches, surveillance, censorship and control. Networks that can freely interoperate, associate and disassociate
with each other, and require no central oversight. Networks for human beings. *Networks for the people*.

.. _understanding-goals:

Goals
=====

To be as widely usable and efficient to deploy as possible, the following goals have been used to
guide the design of Reticulum:


* **Fully useable as open source software stack**
    Reticulum must be implemented with, and be able to run using only open source software. This is
    critical to ensuring the availability, security and transparency of the system.
* **Hardware layer agnosticism**
    Reticulum must be fully hardware agnostic, and shall be useable over a wide range of
    physical networking layers, such as data radios, serial lines, modems, handheld transceivers,
    wired Ethernet, WiFi, or anything else that can carry a digital data stream. Hardware made for
    dedicated Reticulum use shall be as cheap as possible and use off-the-shelf components, so
    it can be easily modified and replicated by anyone interested in doing so.
* **Very low bandwidth requirements**
    Reticulum should be able to function reliably over links with a transmission capacity as low
    as *5 bits per second*.
* **Encryption by default**
    Reticulum must use strong encryption by default for all communication.
* **Initiator Anonymity**
    It must be possible to communicate over a Reticulum network without revealing any identifying
    information about oneself.
* **Unlicensed use**
    Reticulum shall be functional over physical communication mediums that do not require any
    form of license to use. Reticulum must be designed in a way, so it is usable over ISM radio
    frequency bands, and can provide functional long distance links in such conditions, for example
    by connecting a modem to a PMR or CB radio, or by using LoRa or WiFi modules.
* **Supplied software**
    In addition to the core networking stack and API, that allows a developer to build
    applications with Reticulum, a basic set of Reticulum-based communication tools must be
    implemented and released along with Reticulum itself. These shall serve both as a
    functional, basic communication suite, and as an example and learning resource to others wishing
    to build applications with Reticulum.
* **Ease of use**
    The reference implementation of Reticulum is written in Python, to make it easy to use
    and understand. A programmer with only basic experience should be able to use
    Reticulum to write networked applications.
* **Low cost**
    It shall be as cheap as possible to deploy a communication system based on Reticulum. This
    should be achieved by using cheap off-the-shelf hardware that potential users might already
    own. The cost of setting up a functioning node should be less than $100 even if all parts
    needs to be purchased.

.. _understanding-basicfunctionality:

Introduction & Basic Functionality
==================================

Reticulum is a networking stack suited for high-latency, low-bandwidth links. Reticulum is at its
core a *message oriented* system. It is suited for both local point-to-point or point-to-multipoint
scenarios where all nodes are within range of each other, as well as scenarios where packets need
to be transported over multiple hops in a complex network to reach the recipient.

Reticulum does away with the idea of addresses and ports known from IP, TCP and UDP. Instead
Reticulum uses the singular concept of *destinations*. Any application using Reticulum as its
networking stack will need to create one or more destinations to receive data, and know the
destinations it needs to send data to.

All destinations in Reticulum are _represented_ as a 16 byte hash. This hash is derived from truncating a full
SHA-256 hash of identifying characteristics of the destination. To users, the destination addresses
will be displayed as 16 hexadecimal bytes, like this example: ``<13425ec15b621c1d928589718000d814>``.

The truncation size of 16 bytes (128 bits) for destinations has been chosen as a reasonable trade-off
between address space
and packet overhead. The address space accommodated by this size can support many billions of
simultaneously active devices on the same network, while keeping packet overhead low, which is
essential on low-bandwidth networks. In the very unlikely case that this address space nears
congestion, a one-line code change can upgrade the Reticulum address space all the way up to 256
bits, ensuring the Reticulum address space could potentially support galactic-scale networks.
This is obviously complete and ridiculous over-allocation, and as such, the current 128 bits should
be sufficient, even far into the future.

By default Reticulum encrypts all data using elliptic curve cryptography and AES. Any packet sent to a
destination is encrypted with a per-packet derived key. Reticulum can also set up an encrypted
channel to a destination, called a *Link*. Both data sent over Links and single packets offer
*Initiator Anonymity*. Links additionally offer *Forward Secrecy* by default, employing an Elliptic Curve
Diffie Hellman key exchange on Curve25519 to derive per-link ephemeral keys. Asymmetric, link-less
packet communication can also provide forward secrecy, with automatic key ratcheting, by enabling
ratchets on a per-destination basis. The multi-hop transport, coordination, verification and reliability
layers are fully autonomous and also based on elliptic curve cryptography.

Reticulum also offers symmetric key encryption for group-oriented communications, as well as
unencrypted packets for local broadcast purposes.

Reticulum can connect to a variety of interfaces such as radio modems, data radios and serial ports,
and offers the possibility to easily tunnel Reticulum traffic over IP links such as the Internet or
private IP networks.

.. _understanding-destinations:

Destinations
------------

To receive and send data with the Reticulum stack, an application needs to create one or more
destinations. Reticulum uses three different basic destination types, and one special:


* **Single**
    The *single* destination type is the most common type in Reticulum, and should be used for
    most purposes. It is always identified by a unique public key. Any data sent to this
    destination will be encrypted using ephemeral keys derived from an ECDH key exchange, and will
    only be readable by the creator of the destination, who holds the corresponding private key.
* **Plain**
    A *plain* destination type is unencrypted, and suited for traffic that should be broadcast to a
    number of users, or should be readable by anyone. Traffic to a *plain* destination is not encrypted.
    Generally, *plain* destinations can be used for broadcast information intended to be public.
    Plain destinations are only reachable directly, and packets addressed to plain destinations are
    never transported over multiple hops in the network. To be transportable over multiple hops in Reticulum, information
    *must* be encrypted, since Reticulum uses the per-packet encryption to verify routing paths and
    keep them alive.
* **Group**
    The *group* special destination type, that defines a symmetrically encrypted virtual destination.
    Data sent to this destination will be encrypted with a symmetric key, and will be readable by
    anyone in possession of the key, but as with the *plain* destination type, packets to this type
    of destination are not currently transported over multiple hops, although a planned upgrade
    to Reticulum will allow globally reachable *group* destinations.
* **Link**
    A *link* is a special destination type, that serves as an abstract channel to a *single*
    destination, directly connected or over multiple hops. The *link* also offers reliability and
    more efficient encryption, forward secrecy, initiator anonymity, and as such can be useful even
    when a node is directly reachable. It also offers a more capable API and allows easily carrying
    out requests and responses, large data transfers and more.

.. _understanding-destinationnaming:

Destination Naming
^^^^^^^^^^^^^^^^^^

Destinations are created and named in an easy to understand dotted notation of *aspects*, and
represented on the network as a hash of this value. The hash is a SHA-256 truncated to 128 bits. The
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
   hash      : 4faf1b2e0a077e6a9d92fa051f256038

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
is represented. The uniquely identifying aspect is always achieved by appending the public key,
which expands the destination into a uniquely identifiable one. Reticulum does this automatically.

Any destination on a Reticulum network can be addressed and reached simply by knowing its
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
    When plain-text communication is desirable, for example when broadcasting information, or for local discovery purposes.

To communicate with a *single* destination, you need to know its public key. Any method for
obtaining the public key is valid, but Reticulum includes a simple mechanism for making other
nodes aware of your destinations public key, called the *announce*. It is also possible to request
an unknown public key from the network, as all transport instances serve as a distributed ledger
of public keys.

Note that public key information can be shared and verified in other ways than using the
built-in *announce* functionality, and that it is therefore not required to use the *announce* and *path request*
functionality to obtain public keys. It is by far the easiest though, and should definitely be used
if there is not a very good reason for doing it differently.

.. _understanding-keyannouncements:

Public Key Announcements
------------------------

An *announce* will send a special packet over any relevant interfaces, containing all needed
information about the destination hash and public key, and can also contain some additional,
application specific data. The entire packet is signed by the sender to ensure authenticity. It is not
required to use the announce functionality, but in many cases it will be the simplest way to share
public keys on the network. The announce mechanism also serves to establish end-to-end connectivity
to the announced destination, as the announce propagates through the network.

As an example, an announce in a simple messenger application might contain the following information:


* The announcers destination hash
* The announcers public key
* Application specific data, in this case the users nickname and availability status
* A random blob, making each new announce unique
* An Ed25519 signature of the above information, verifying authenticity

With this information, any Reticulum node that receives it will be able to reconstruct an outgoing
destination to securely communicate with that destination. You might have noticed that there is one
piece of information lacking to reconstruct full knowledge of the announced destination, and that is
the aspect names of the destination. These are intentionally left out to save bandwidth, since they
will be implicit in almost all cases. The receiving application will already know them. If a destination
name is not entirely implicit, information can be included in the application specific data part that
will allow the receiver to infer the naming.

It is important to note that announces will be forwarded throughout the network according to a
certain pattern. This will be detailed in the section
:ref:`The Announce Mechanism in Detail<understanding-announce>`.

In Reticulum, destinations are allowed to move around the network at will. This is very different from
protocols such as IP, where an address is always expected to stay within the network segment it was assigned in.
This limitation does not exist in Reticulum, and any destination is *completely portable* over the entire topography
of the network, and *can even be moved to other Reticulum networks* than the one it was created in, and
still become reachable. To update its reachability, a destination simply needs to send an announce on any
networks it is part of. After a short while, it will be globally reachable in the network.

Seeing how *single* destinations are always tied to a private/public key pair leads us to the next topic.

.. _understanding-identities:

Identities
----------

In Reticulum, an *identity* does not necessarily represent a personal identity, but is an abstraction that
can represent any kind of *verifiable entity*. This could very well be a person, but it could also be the
control interface of a machine, a program, robot, computer, sensor or something else entirely. In
general, any kind of agent that can act, or be acted upon, or store or manipulate information, can be
represented as an identity. An *identity* can be used to create any number of destinations.

A *single* destination will always have an *identity* tied to it, but not *plain* or *group*
destinations. Destinations and identities share a multilateral connection. You can create a
destination, and if it is not connected to an identity upon creation, it will just create a new one to use
automatically. This may be desirable in some situations, but often you will probably want to create
the identity first, and then use it to create new destinations.

As an example, we could use an identity to represent the user of a messaging application.
Destinations can then be created by this identity to allow communication to reach the user.
In all cases it is of great importance to store the private keys associated with any
Reticulum Identity securely and privately, since obtaining access to the identity keys equals
obtaining access and controlling reachability to any destinations created by that identity.

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

The methods of routing used in traditional networks are fundamentally incompatible with the physical medium
types and circumstances that Reticulum was designed to handle. These mechanisms mostly assume trust at the physical layer,
and often needs a lot more bandwidth than Reticulum can assume is available. Since Reticulum is designed to
survive running over open radio spectrum, no such trust can be assumed, and bandwidth is often very limited.

To overcome such challenges, Reticulum’s *Transport* system uses asymmetric elliptic curve cryptography to
implement the concept of *paths* that allow discovery of how to get information closer to a certain
destination. It is important to note that no single node in a Reticulum network knows the complete
path to a destination. Every Transport node participating in a Reticulum network will only
know the most direct way to get a packet one hop closer to it's destination.


.. _understanding-nodetypes:

Node Types
----------

Currently, Reticulum distinguishes between two types of network nodes. All nodes on a Reticulum network
are *Reticulum Instances*, and some are also *Transport Nodes*. If a system running Reticulum is fixed in
one place, and is intended to be kept available most of the time, it is a good contender to be a *Transport Node*.

Any Reticulum Instance can become a Transport Node by enabling it in the configuration.
This distinction is made by the user configuring the node, and is used to determine what nodes on the
network will help forward traffic, and what nodes rely on other nodes for wider connectivity.

If a node is an *Instance* it should be given the configuration directive ``enable_transport = No``, which
is the default setting.

If it is a *Transport Node*, it should be given the configuration directive ``enable_transport = Yes``.


.. _understanding-announce:

The Announce Mechanism in Detail
--------------------------------

When an *announce* for a destination is transmitted by a Reticulum instance, it will be forwarded by
any transport node receiving it, but according to some specific rules:


* | If this exact announce has already been received before, ignore it.

* | If not, record into a table which Transport Node the announce was received from, and how many times in
    total it has been retransmitted to get here.

* | If the announce has been retransmitted *m+1* times, it will not be forwarded any more. By default, *m* is
    set to 128.

* | After a randomised delay, the announce will be retransmitted on all interfaces that have bandwidth
    available for processing announces. By default, the maximum bandwidth allocation for processing
    announces is set at 2%, but can be configured on a per-interface basis.

* | If any given interface does not have enough bandwidth available for retransmitting the announce,
    the announce will be assigned a priority inversely proportional to its hop count, and be inserted
    into a queue managed by the interface.

* | When the interface has bandwidth available for processing an announce, it will prioritise announces
    for destinations that are closest in terms of hops, thus prioritising reachability and connectivity
    of local nodes, even on slow networks that connect to wider and faster networks.

* | After the announce has been re-transmitted, and if no other nodes are heard retransmitting the announce
    with a greater hop count than when it left this node, transmitting it will be retried *r* times. By default,
    *r* is set to 1.

* | If a newer announce from the same destination arrives, while an identical one is already waiting
    to be transmitted, the newest announce is discarded. If the newest announce contains different
    application specific data, it will replace the old announce.

Once an announce has reached a node in the network, any other node in direct contact with that
node will be able to reach the destination the announce originated from, simply by sending a packet
addressed to that destination. Any node with knowledge of the announce will be able to direct the
packet towards the destination by looking up the next node with the shortest amount of hops to the
destination.

According to these rules, an announce will propagate throughout the network in a predictable way,
and make the announced destination reachable in a short amount of time. Fast networks that have the
capacity to process many announces can reach full convergence very quickly, even when constantly adding
new destinations. Slower segments of such networks might take a bit longer to gain full knowledge about
the wide and fast networks they are connected to, but can still do so over time, while prioritising full
and quickly converging end-to-end connectivity for their local, slower segments.

In general, even extremely complex networks, that utilize the maximum 128 hops will converge to full
end-to-end connectivity in about one minute, given there is enough bandwidth available to process
the required amount of announces.

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
    an ECDH key exchange with the destination's public key (or ratchet key, if available), and encrypt the information.

* | It is important to note that this key exchange does not require any network traffic. The sender already
    knows the public key of the destination from an earlier received *announce*, and can thus perform the ECDH
    key exchange locally, before sending the packet.

* | The public part of the newly generated ephemeral key-pair is included with the encrypted token, and sent
    along with the encrypted payload data in the packet.

* | When the destination receives the packet, it can itself perform an ECDH key exchange and decrypt the
    packet.

* | A new ephemeral key is used for every packet sent in this way.

* | Once the packet has been received and decrypted by the addressed destination, that destination can opt
    to *prove* its receipt of the packet. It does this by calculating the SHA-256 hash of the received packet,
    and signing this hash with its Ed25519 signing key. Transport nodes in the network can then direct this
    *proof* back to the packets origin, where the signature can be verified against the destination's known
    public signing key.

* | In case the packet is addressed to a *group* destination type, the packet will be encrypted with the
    pre-shared AES-128 key associated with the destination. In case the packet is addressed to a *plain*
    destination type, the payload data will not be encrypted. Neither of these two destination types can offer
    forward secrecy. In general, it is recommended to always use the *single* destination type, unless it is
    strictly necessary to use one of the others.


For exchanges of larger amounts of data, or when longer sessions of bidirectional communication is desired, Reticulum offers the *Link* API. To establish a *link*, the following process is employed:

* | First, the node that wishes to establish a link will send out a special packet, that
    traverses the network and locates the desired destination. Along the way, the Transport Nodes that
    forward the packet will take note of this *link request*.

* | Second, if the destination accepts the *link request* , it will send back a packet that proves the
    authenticity of its identity (and the receipt of the link request) to the initiating node. All
    nodes that initially forwarded the packet will also be able to verify this proof, and thus
    accept the validity of the *link* throughout the network.

* | When the validity of the *link* has been accepted by forwarding nodes, these nodes will
    remember the *link* , and it can subsequently be used by referring to a hash representing it.

* | As a part of the *link request*, an Elliptic Curve Diffie-Hellman key exchange takes place, that sets up an
    efficiently encrypted tunnel between the two nodes. As such, this mode of communication is preferred,
    even for situations when nodes can directly communicate, when the amount of data to be exchanged numbers
    in the tens of packets, or whenever the use of the more advanced API functions is desired.

* | When a *link* has been set up, it automatically provides message receipt functionality, through
    the same *proof* mechanism discussed before, so the sending node can obtain verified confirmation
    that the information reached the intended recipient.

* | Once the *link* has been set up, the initiator can remain anonymous, or choose to authenticate towards
    the destination using a Reticulum Identity. This authentication is happening inside the encrypted
    link, and is only revealed to the verified destination, and no intermediaries.

In a moment, we will discuss the details of how this methodology is
implemented, but let’s first recap what purposes this methodology serves. We
first ensure that the node answering our request is actually the one we want to
communicate with, and not a malicious actor pretending to be so.  At the same
time we establish an efficient encrypted channel. The setup of this is
relatively cheap in terms of bandwidth, so it can be used just for a short
exchange, and then recreated as needed, which will also rotate encryption keys.
The link can also be kept alive for longer periods of time, if this is more
suitable to the application. The procedure also inserts the *link id* , a hash
calculated from the link request packet, into the memory of forwarding nodes,
which means that the communicating nodes can thereafter reach each other simply
by referring to this *link id*.

The combined bandwidth cost of setting up a link is 3 packets totalling 297 bytes (more info in the
:ref:`Binary Packet Format<understanding-packetformat>` section). The amount of bandwidth used on keeping
a link open is practically negligible, at 0.45 bits per second. Even on a slow 1200 bits per second packet
radio channel, 100 concurrent links will still leave 96% channel capacity for actual data.


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
    public key *LKr* and an Ed25519 signature of the *link id* and *LKr* made by the *original signing key* of
    the addressed destination.
   
* | By verifying this *link proof* packet, all nodes that originally transported the *link request*
    packet to the destination from the originator can now verify that the intended destination received
    the request and accepted it, and that the path they chose for forwarding the request was valid.
    In successfully carrying out this verification, the transporting nodes marks the link as active.
    An abstract bi-directional communication channel has now been established along a path in the network.
    Packets can now be exchanged bi-directionally from either end of the link simply by adressing the
    packets to the *link id* of the link.

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
the transfer, integrity verification and reassembling the data on the other end.

:ref:`Resources<api-resource>` are programmatically very simple to use, and only requires a few lines
of codes to reliably transfer any amount of data. They can be used to transfer data stored in memory,
or stream data directly from files.

.. _understanding-referencesystem:

Reference Setup
======================

This section will detail a recommended *Reference Setup* for Reticulum. It is important to
note that Reticulum is designed to be usable on more or less any computing device, and over more
or less any medium that allows you to send and receive data, which satisfies some very low
minimum requirements.

The communication channel must support at least half-duplex operation, and provide an average
throughput of 5 bits per second or greater, and supports a physical layer MTU of 500 bytes. The
Reticulum stack should be able to run on more or less any hardware that can provide a Python 3.x 
runtime environment.

That being said, this reference setup has been outlined to provide a common platform for anyone
who wants to help in the development of Reticulum, and for everyone who wants to know a
recommended setup to get started experimenting. A reference system consists of three parts:

* **An Interface Device**
    Which provides access to the physical medium whereupon the communication
    takes place, for example a radio with an integrated modem. A setup with a separate modem
    connected to a radio would also be an interface device.
* **A Host Device**
    Some sort of computing device that can run the necessary software, communicate with the
    interface device, and provide user interaction.
* **A Software Stack**
    The software implementing the Reticulum protocol and applications using it.

The reference setup can be considered a relatively stable platform to develop on, and also to start
building networks or applications on. While details of the implementation might change at the current stage of
development, it is the goal to maintain hardware compatibility for as long as entirely possible, and
the current reference setup has been determined to provide a functional platform for many years
into the future. The current Reference System Setup is as follows:


* **Interface Device**
    A data radio consisting of a LoRa radio module, and a microcontroller with open source
    firmware, that can connect to host devices via USB. It operates in either the 430, 868 or 900
    MHz frequency bands. More details can be found on the `RNode Page <https://unsigned.io/rnode>`_.
* **Host Device**
    Any computer device running Linux and Python. A Raspberry Pi with a Debian based OS is
    recommended.
* **Software Stack**
    The most recently released Python Implementation of Reticulum, running on a Debian based
    operating system.

To avoid confusion, it is very important to note, that the reference interface device **does not**
use the LoRaWAN standard, but uses a custom MAC layer on top of the plain LoRa modulation! As such, you will
need a plain LoRa radio module connected to an controller with the correct firmware. Full details on how to
get or make such a device is available on the `RNode Page <https://unsigned.io/rnode>`_.

With the current reference setup, it should be possible to get on a Reticulum network for around 100$
even if you have none of the hardware already, and need to purchase everything.

This reference setup is of course just a recommendation for getting started easily, and you should
tailor it to your own specific needs, or whatever hardware you have available.

.. _understanding-protocolspecifics:

Protocol Specifics
==================

This chapter will detail protocol specific information that is essential to the implementation of
Reticulum, but non critical in understanding how the protocol works on a general level. It should be
treated more as a reference than as essential reading.


Packet Prioritisation
---------------------

Currently, Reticulum is completely priority-agnostic regarding general traffic. All traffic is handled
on a first-come, first-serve basis. Announce re-transmission are handled according to the re-transmission
times and priorities described earlier in this chapter.


Interface Access Codes
----------------------

Reticulum can create named virtual networks, and networks that are only accessible by knowing a preshared
passphrase. The configuration of this is detailed in the :ref:`Common Interface Options<interfaces-options>`
section. To implement these feature, Reticulum uses the concept of Interface Access Codes, that are calculated
and verified per packet.

An interface with a named virtual network or passphrase authentication enabled will derive a shared Ed25519
signing identity, and for every outbound packet generate a signature of the entire packet. This signature is
then inserted into the packet as an Interface Access Code before transmission. Depending on the speed and
capabilities of the interface, the IFAC can be the full 512-bit Ed25519 signature, or a truncated version.
Configured IFAC length can be inspected for all interfaces with the ``rnstatus`` utility.

Upon receipt, the interface will check that the signature matches the expected value, and drop the packet if it
does not. This ensures that only packets sent with the correct naming and/or passphrase parameters are allowed to
pass onto the network.


.. _understanding-packetformat:

Wire Format
-----------

.. code-block:: text

    == Reticulum Wire Format ======

    A Reticulum packet is composed of the following fields:

    [HEADER 2 bytes] [ADDRESSES 16/32 bytes] [CONTEXT 1 byte] [DATA 0-465 bytes]

    * The HEADER field is 2 bytes long.
      * Byte 1: [IFAC Flag], [Header Type], [Context Flag], [Propagation Type],
                [Destination Type] and [Packet Type]
      * Byte 2: Number of hops

    * Interface Access Code field if the IFAC flag was set.
      * The length of the Interface Access Code can vary from
        1 to 64 bytes according to physical interface
        capabilities and configuration.

    * The ADDRESSES field contains either 1 or 2 addresses.
      * Each address is 16 bytes long.
      * The Header Type flag in the HEADER field determines
        whether the ADDRESSES field contains 1 or 2 addresses.
      * Addresses are SHA-256 hashes truncated to 16 bytes.

    * The CONTEXT field is 1 byte.
      * It is used by Reticulum to determine packet context.

    * The DATA field is between 0 and 465 bytes.
      * It contains the packets data payload.

    IFAC Flag
    -----------------
    open             0  Packet for publically accessible interface
    authenticated    1  Interface authentication is included in packet


    Header Types
    -----------------
    type 1           0  Two byte header, one 16 byte address field
    type 2           1  Two byte header, two 16 byte address fields


    Context Flag
    -----------------
    unset            0  The context flag is used for various types
    set              1  of signalling, depending on packet context


    Propagation Types
    -----------------
    broadcast        0
    transport        1


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

       HEADER FIELD           DESTINATION FIELDS            CONTEXT FIELD  DATA FIELD
     _______|_______   ________________|________________   ________|______   __|_
    |               | |                                 | |               | |    |
    01010000 00000100 [HASH1, 16 bytes] [HASH2, 16 bytes] [CONTEXT, 1 byte] [DATA]
    || | | |    |
    || | | |    +-- Hops             = 4
    || | | +------- Packet Type      = DATA
    || | +--------- Destination Type = SINGLE
    || +----------- Propagation Type = TRANSPORT
    |+------------- Header Type      = HEADER_2 (two byte header, two address fields)
    +-------------- Access Codes     = DISABLED


    +- Packet Example -+

       HEADER FIELD   DESTINATION FIELD   CONTEXT FIELD  DATA FIELD
     _______|_______   _______|_______   ________|______   __|_
    |               | |               | |               | |    |
    00000000 00000111 [HASH1, 16 bytes] [CONTEXT, 1 byte] [DATA]
    || | | |    |
    || | | |    +-- Hops             = 7
    || | | +------- Packet Type      = DATA
    || | +--------- Destination Type = SINGLE
    || +----------- Propagation Type = BROADCAST
    |+------------- Header Type      = HEADER_1 (two byte header, one address field)
    +-------------- Access Codes     = DISABLED


    +- Packet Example -+

       HEADER FIELD     IFAC FIELD    DESTINATION FIELD   CONTEXT FIELD  DATA FIELD
     _______|_______   ______|______   _______|_______   ________|______   __|_
    |               | |             | |               | |               | |    |
    10000000 00000111 [IFAC, N bytes] [HASH1, 16 bytes] [CONTEXT, 1 byte] [DATA]
    || | | |    |
    || | | |    +-- Hops             = 7
    || | | +------- Packet Type      = DATA
    || | +--------- Destination Type = SINGLE
    || +----------- Propagation Type = BROADCAST
    |+------------- Header Type      = HEADER_1 (two byte header, one address field)
    +-------------- Access Codes     = ENABLED


    Size examples of different packet types
    ---------------------------------------

    The following table lists example sizes of various
    packet types. The size listed are the complete on-
    wire size counting all fields including headers,
    but excluding any interface access codes.

    - Path Request    :    51  bytes
    - Announce        :    167 bytes
    - Link Request    :    83  bytes
    - Link Proof      :    115 bytes
    - Link RTT packet :    99  bytes
    - Link keepalive  :    20  bytes


.. _understanding-announcepropagation:

Announce Propagation Rules
--------------------------

The following table illustrates the rules for automatically propagating announces
from one interface type to another, for all possible combinations. For the purpose
of announce propagation, the *Full* and *Gateway* modes are identical.

.. image:: graphics/if_mode_graph_b.png

See the :ref:`Interface Modes<interfaces-modes>` section for a conceptual overview
of the different interface modes, and how they are configured.

.. 
      (.. code-block:: text)
      Full ────── ✓ ──┐              ┌── ✓ ── Full
      AP ──────── ✓ ──┼───> Full >───┼── ✕ ── AP
      Boundary ── ✓ ──┤              ├── ✓ ── Boundary
      Roaming ─── ✓ ──┘              └── ✓ ── Roaming

      Full ────── ✕ ──┐              ┌── ✓ ── Full
      AP ──────── ✕ ──┼────> AP >────┼── ✕ ── AP
      Boundary ── ✕ ──┤              ├── ✓ ── Boundary
      Roaming ─── ✕ ──┘              └── ✓ ── Roaming

      Full ────── ✓ ──┐              ┌── ✓ ── Full
      AP ──────── ✓ ──┼─> Roaming >──┼── ✕ ── AP
      Boundary ── ✕ ──┤              ├── ✕ ── Boundary
      Roaming ─── ✕ ──┘              └── ✕ ── Roaming

      Full ────── ✓ ──┐              ┌── ✓ ── Full
      AP ──────── ✓ ──┼─> Boundary >─┼── ✕ ── AP
      Boundary ── ✓ ──┤              ├── ✓ ── Boundary
      Roaming ─── ✕ ──┘              └── ✕ ── Roaming


.. _understanding-primitives:

Cryptographic Primitives
------------------------

Reticulum has been designed to use a simple suite of efficient, strong and modern
cryptographic primitives, with widely available implementations that can be used
both on general-purpose CPUs and on microcontrollers. The necessary primitives are:

* Ed25519 for signatures

* X25519 for ECDH key exchanges

* HKDF for key derivation

* Modified Fernet for encrypted tokens

  * AES-128 in CBC mode

  * HMAC for message authentication

  * No Version and Timestamp metadata included

* SHA-256

* SHA-512

In the default installation configuration, the ``X25519``, ``Ed25519`` and ``AES-128-CBC``
primitives are provided by `OpenSSL <https://www.openssl.org/>`_ (via the `PyCA/cryptography <https://github.com/pyca/cryptography>`_
package). The hashing functions ``SHA-256`` and ``SHA-512`` are provided by the standard
Python `hashlib <https://docs.python.org/3/library/hashlib.html>`_. The ``HKDF``, ``HMAC``,
``Fernet`` primitives, and the ``PKCS7`` padding function are always provided by the
following internal implementations:

- ``RNS/Cryptography/HKDF.py``
- ``RNS/Cryptography/HMAC.py``
- ``RNS/Cryptography/Fernet.py``
- ``RNS/Cryptography/PKCS7.py``


Reticulum also includes a complete implementation of all necessary primitives in pure Python.
If OpenSSL & PyCA are not available on the system when Reticulum is started, Reticulum will
instead use the internal pure-python primitives. A trivial consequence of this is performance,
with the OpenSSL backend being *much* faster. The most important consequence however, is the
potential loss of security by using primitives that has not seen the same amount of scrutiny,
testing and review as those from OpenSSL.

If you want to use the internal pure-python primitives, it is **highly advisable** that you
have a good understanding of the risks that this pose, and make an informed decision on whether
those risks are acceptable to you.
