
.. _interfaces-main:

**********************
Configuring Interfaces
**********************

Reticulum supports using many kinds of devices as networking interfaces, and
allows you to mix and match them in any way you choose. The number of distinct
network topologies you can create with Reticulum is more or less endless, but
common to them all is that you will need to define one or more *interfaces*
for Reticulum to use.

The following sections describe the interfaces currently available in Reticulum,
and gives example configurations for the respective interface types.

For a high-level overview of how networks can be formed over different interface
types, have a look at the :ref:`Building Networks<networks-main>` chapter of this
manual.


.. _interfaces-auto:

Auto Interface
==============

The Auto Interface enables communication with other discoverable Reticulum
nodes over autoconfigured IPv6 and UDP. It does not need any functional IP
infrastructure like routers or DHCP servers, but will require at least some
sort of switching medium between peers (a wired switch, a hub, a WiFi access
point or similar), and that link-local IPv6 is enabled in your operating
system, which should be enabled by default in almost all OSes.

.. code::

  # This example demonstrates a bare-minimum setup
  # of an Auto Interface. It will allow communica-
  # tion with all other reachable devices on all
  # usable physical ethernet-based devices that
  # are available on the system.

  [[Default Interface]]
    type = AutoInterface
    interface_enabled = True

  # This example demonstrates an more specifically
  # configured Auto Interface, that only uses spe-
  # cific physical interfaces, and has a number of
  # other configuration options set.
  
  [[Default Interface]]
    type = AutoInterface
    interface_enabled = True

    # You can create multiple isolated Reticulum
    # networks on the same physical LAN by
    # specifying different Group IDs.

    group_id = reticulum

    # You can also choose the multicast address type:
    # temporary (default, Temporary Multicast Address)
    # or permanent (Permanent Multicast Address)

    multicast_address_type = permanent

    # You can also select specifically which
    # kernel networking devices to use.

    devices = wlan0,eth1

    # Or let AutoInterface use all suitable
    # devices except for a list of ignored ones.

    ignored_devices = tun0,eth0


If you are connected to the Internet with IPv6, and your provider will route
IPv6 multicast, you can potentially configure the Auto Interface to globally
autodiscover other Reticulum nodes within your selected Group ID. You can specify
the discovery scope by setting it to one of ``link``, ``admin``, ``site``,
``organisation`` or ``global``.

.. code::
  
  [[Default Interface]]
    type = AutoInterface
    interface_enabled = True

    # Configure global discovery

    group_id = custom_network_name
    discovery_scope = global

    # Other configuration options

    discovery_port = 48555
    data_port = 49555


.. _interfaces-i2p:

I2P Interface
=============

The I2P interface lets you connect Reticulum instances over the
`Invisible Internet Protocol <https://i2pd.website>`_. This can be
especially useful in cases where you want to host a globally reachable
Reticulum instance, but do not have access to any public IP addresses,
have a frequently changing IP address, or have firewalls blocking
inbound traffic.

Using the I2P interface, you will get a globally reachable, portable
and persistent I2P address that your Reticulum instance can be reached
at.

To use the I2P interface, you must have an I2P router running
on your system. The easiest way to achieve this is to download and
install the `latest release <https://github.com/PurpleI2P/i2pd/releases/latest>`_
of the ``i2pd`` package. For more details about I2P, see the
`geti2p.net website <https://geti2p.net/en/about/intro>`_.

When an I2P router is running on your system, you can simply add
an I2P interface to Reticulum:

.. code::

  [[I2P]]
    type = I2PInterface
    interface_enabled = yes
    connectable = yes

On the first start, Reticulum will generate a new I2P address for the
interface and start listening for inbound traffic on it. This can take
a while the first time, especially if your I2P router was also just
started, and is not yet well-connected to the I2P network. When ready,
you should see I2P base32 address printed to your log file. You can
also inspect the status of the interface using the ``rnstatus`` utility.

To connect to other Reticulum instances over I2P, just add a comma-separated
list of I2P base32 addresses to the ``peers`` option of the interface:

.. code::

  [[I2P]]
    type = I2PInterface
    interface_enabled = yes
    connectable = yes
    peers = 5urvjicpzi7q3ybztsef4i5ow2aq4soktfj7zedz53s47r54jnqq.b32.i2p

It can take anywhere from a few seconds to a few minutes to establish
I2P connections to the desired peers, so Reticulum handles the process
in the background, and will output relevant events to the log.

**Please Note!** While the I2P interface is the simplest way to use
Reticulum over I2P, it is also possible to tunnel the TCP server and
client interfaces over I2P manually. This can be useful in situations
where more control is needed, but requires manual tunnel setup through
the I2P daemon configuration.

It is important to note that the two methods are *interchangably compatible*.
You can use the I2PInterface to connect to a TCPServerInterface that
was manually tunneled over I2P, for example. This offers a high degree
of flexibility in network setup, while retaining ease of use in simpler
use-cases.


.. _interfaces-tcps:

TCP Server Interface
====================

The TCP Server interface is suitable for allowing other peers to connect over
the Internet or private IP networks. When a TCP server interface has been
configured, other Reticulum peers can connect to it with a TCP Client interface.

.. code::

  # This example demonstrates a TCP server interface.
  # It will listen for incoming connections on the
  # specified IP address and port number.
  
  [[TCP Server Interface]]
    type = TCPServerInterface
    interface_enabled = True

    # This configuration will listen on all IP
    # interfaces on port 4242
    
    listen_ip = 0.0.0.0
    listen_port = 4242

    # Alternatively you can bind to a specific IP
    
    # listen_ip = 10.0.0.88
    # listen_port = 4242

    # Or a specific network device
    
    # device = eth0
    # port = 4242

**Please Note!** The TCP interfaces support tunneling over I2P, but to do so reliably,
you must use the i2p_tunneled option:

.. code::

  [[TCP Server on I2P]]
      type = TCPServerInterface
      interface_enabled = yes
      listen_ip = 127.0.0.1
      listen_port = 5001
      i2p_tunneled = yes

In almost all cases, it is easier to use the dedicated ``I2PInterface``, but for complete
control, and using I2P routers running on external systems, this option also exists.

.. _interfaces-tcpc:

TCP Client Interface
====================

To connect to a TCP server interface, you would naturally use the TCP client
interface. Many TCP Client interfaces from different peers can connect to the
same TCP Server interface at the same time.

The TCP interface types can also tolerate intermittency in the IP link layer.
This means that Reticulum will gracefully handle IP links that go up and down,
and restore connectivity after a failure, once the other end of a TCP interface reappears.

.. code::

  # Here's an example of a TCP Client interface. The
  # target_host can either be an IP address or a hostname.

  [[TCP Client Interface]]
    type = TCPClientInterface
    interface_enabled = True
    target_host = 127.0.0.1
    target_port = 4242

It is also possible to use this interface type to connect via other programs
or hardware devices that expose a KISS interface on a TCP port, for example
software-based soundmodems. To do this, use the ``kiss_framing`` option:

.. code::

  # Here's an example of a TCP Client interface that connects
  # to a software TNC soundmodem on a KISS over TCP port.

  [[TCP KISS Interface]]
    type = TCPClientInterface
    interface_enabled = True
    kiss_framing = True
    target_host = 127.0.0.1
    target_port = 8001

**Caution!** Only use the KISS framing option when connecting to external devices
and programs like soundmodems and similar over TCP. When using the
``TCPClientInterface`` in conjunction with the ``TCPServerInterface`` you should
never enable ``kiss_framing``, since this will disable internal reliability and
recovery mechanisms that greatly improves performance over unreliable and
intermittent TCP links.

**Please Note!** The TCP interfaces support tunneling over I2P, but to do so reliably,
you must use the i2p_tunneled option:

.. code::

  [[TCP Client over I2P]]
      type = TCPClientInterface
      interface_enabled = yes
      target_host = 127.0.0.1
      target_port = 5001
      i2p_tunneled = yes


.. _interfaces-udp:

UDP Interface
=============

A UDP interface can be useful for communicating over IP networks, both
private and the internet. It can also allow broadcast communication
over IP networks, so it can provide an easy way to enable connectivity
with all other peers on a local area network.

*Please Note!* Using broadcast UDP traffic has performance implications,
especially on WiFi. If your goal is simply to enable easy communication
with all peers in your local Ethernet broadcast domain, the
:ref:`Auto Interface<interfaces-auto>` performs better, and is even
easier to use.

.. code::

  # This example enables communication with other
  # local Reticulum peers over UDP.
  
  [[UDP Interface]]
    type = UDPInterface
    interface_enabled = True

    listen_ip = 0.0.0.0
    listen_port = 4242
    forward_ip = 255.255.255.255
    forward_port = 4242

    # The above configuration will allow communication
    # within the local broadcast domains of all local
    # IP interfaces.

    # Instead of specifying listen_ip, listen_port,
    # forward_ip and forward_port, you can also bind
    # to a specific network device like below.

    # device = eth0
    # port = 4242

    # Assuming the eth0 device has the address
    # 10.55.0.72/24, the above configuration would
    # be equivalent to the following manual setup.
    # Note that we are both listening and forwarding to
    # the broadcast address of the network segments.

    # listen_ip = 10.55.0.255
    # listen_port = 4242
    # forward_ip = 10.55.0.255
    # forward_port = 4242

    # You can of course also communicate only with
    # a single IP address

    # listen_ip = 10.55.0.15
    # listen_port = 4242
    # forward_ip = 10.55.0.16
    # forward_port = 4242


.. _interfaces-rnode:

RNode LoRa Interface
====================

To use Reticulum over LoRa, the `RNode <https://unsigned.io/rnode/>`_ interface
can be used, and offers full control over LoRa parameters.

.. code::

  # Here's an example of how to add a LoRa interface
  # using the RNode LoRa transceiver.

  [[RNode LoRa Interface]]
    type = RNodeInterface

    # Enable interface if you want use it!
    interface_enabled = True

    # Serial port for the device
    port = /dev/ttyUSB0

    # It is also possible to use BLE devices
    # instead of wired serial ports. The
    # target RNode must be paired with the
    # host device before connecting. BLE
    # devices can be connected by name,
    # BLE MAC address or by any available.
    
    # Connect to specific device by name
    # port = ble://RNode 3B87

    # Or by BLE MAC address
    # port = ble://F4:12:73:29:4E:89

    # Or connect to the first available,
    # paired device
    # port = ble://

    # Set frequency to 867.2 MHz
    frequency = 867200000

    # Set LoRa bandwidth to 125 KHz
    bandwidth = 125000

    # Set TX power to 7 dBm (5 mW)
    txpower = 7

    # Select spreading factor 8. Valid 
    # range is 7 through 12, with 7
    # being the fastest and 12 having
    # the longest range.
    spreadingfactor = 8

    # Select coding rate 5. Valid range
    # is 5 throough 8, with 5 being the
    # fastest, and 8 the longest range.
    codingrate = 5

    # You can configure the RNode to send
    # out identification on the channel with
    # a set interval by configuring the
    # following two parameters.
    
    # id_callsign = MYCALL-0
    # id_interval = 600

    # For certain homebrew RNode interfaces
    # with low amounts of RAM, using packet
    # flow control can be useful. By default
    # it is disabled.
    
    # flow_control = False

    # It is possible to limit the airtime
    # utilisation of an RNode by using the
    # following two configuration options.
    # The short-term limit is applied in a
    # window of approximately 15 seconds,
    # and the long-term limit is enforced
    # over a rolling 60 minute window. Both
    # options are specified in percent.
    
    # airtime_limit_long = 1.5
    # airtime_limit_short = 33


.. _interfaces-rnode-multi:

RNode Multi Interface
=====================

For RNodes that support multiple LoRa transceivers, the RNode
Multi interface can be used to configure sub-interfaces individually.

.. code::

  # Here's an example of how to add an RNode Multi interface
  # using the RNode LoRa transceiver.

  [[RNode Multi Interface]]
  type = RNodeMultiInterface

  # Enable interface if you want to use it!
  interface_enabled = True

  # Serial port for the device
  port = /dev/ttyACM0

  # You can configure the RNode to send
  # out identification on the channel with
  # a set interval by configuring the
  # following two parameters.

  # id_callsign = MYCALL-0
  # id_interval = 600

    # A subinterface
    [[[HIGHDATARATE]]]
    # Subinterfaces can be enabled and disabled in of themselves
    interface_enabled = True

    # Set frequency to 2.4GHz
    frequency = 2400000000

    # Set LoRa bandwidth to 1625 KHz
    bandwidth = 1625000

    # Set TX power to 0 dBm (0.12 mW)
    txpower = 0

    # The virtual port, only the manufacturer
    # or the person who wrote the board config
    # can tell you what it will be for which
    # physical hardware interface
    vport = 1

    # Select spreading factor 5. Valid
    # range is 5 through 12, with 5 
    # being the fastest and 12 having
    # the longest range.
    spreadingfactor = 5

    # Select coding rate 5. Valid range
    # is 5 throough 8, with 5 being the
    # fastest, and 8 the longest range.
    codingrate = 5

    # It is possible to limit the airtime
    # utilisation of an RNode by using the
    # following two configuration options.
    # The short-term limit is applied in a
    # window of approximately 15 seconds,
    # and the long-term limit is enforced
    # over a rolling 60 minute window. Both
    # options are specified in percent.

    # airtime_limit_long = 100
    # airtime_limit_short = 100

    [[[LOWDATARATE]]]
    # Subinterfaces can be enabled and disabled in of themselves
    interface_enabled = True

    # Set frequency to 865.6 MHz
    frequency = 865600000

    # The virtual port, only the manufacturer
    # or the person who wrote the board config
    # can tell you what it will be for which
    # physical hardware interface
    vport = 0

    # Set LoRa bandwidth to 125 KHz
    bandwidth = 125000

    # Set TX power to 0 dBm (0.12 mW)
    txpower = 0

    # Select spreading factor 7. Valid
    # range is 5 through 12, with 5 
    # being the fastest and 12 having
    # the longest range.
    spreadingfactor = 7

    # Select coding rate 5. Valid range
    # is 5 throough 8, with 5 being the
    # fastest, and 8 the longest range.
    codingrate = 5

    # It is possible to limit the airtime
    # utilisation of an RNode by using the
    # following two configuration options.
    # The short-term limit is applied in a
    # window of approximately 15 seconds,
    # and the long-term limit is enforced
    # over a rolling 60 minute window. Both
    # options are specified in percent.

    # airtime_limit_long = 100
    # airtime_limit_short = 100

.. _interfaces-serial:

Serial Interface
================

Reticulum can be used over serial ports directly, or over any device with a
serial port, that will transparently pass data. Useful for communicating
directly over a wire-pair, or for using devices such as data radios and lasers.

.. code::

  [[Serial Interface]]
    type = SerialInterface
    interface_enabled = True

    # Serial port for the device
    port = /dev/ttyUSB0

    # Set the serial baud-rate and other
    # configuration parameters.
    speed = 115200
    databits = 8
    parity = none
    stopbits = 1

.. _interfaces-pipe:

Pipe Interface
==============

Using this interface, Reticulum can use any program as an interface via `stdin` and
`stdout`. This can be used to easily create virtual interfaces, or to interface with
custom hardware or other systems.

.. code::

  [[Pipe Interface]]
    type = PipeInterface
    interface_enabled = True

    # External command to execute
    command = netcat -l 5757

    # Optional respawn delay, in seconds
    respawn_delay = 5

Reticulum will write all packets to `stdin` of the ``command`` option, and will
continuously read and scan its `stdout` for Reticulum packets. If ``EOF`` is reached,
Reticulum will try to respawn the program after waiting for ``respawn_interval`` seconds.

.. _interfaces-kiss:

KISS Interface
==============

With the KISS interface, you can use Reticulum over a variety of packet
radio modems and TNCs, including `OpenModem <https://unsigned.io/openmodem/>`_.
KISS interfaces can also be configured to periodically send out beacons
for station identification purposes.

.. code::

  [[Packet Radio KISS Interface]]
    type = KISSInterface
    interface_enabled = True

    # Serial port for the device
    port = /dev/ttyUSB1

    # Set the serial baud-rate and other
    # configuration parameters.
    speed = 115200    
    databits = 8
    parity = none
    stopbits = 1

    # Set the modem preamble.
    preamble = 150

    # Set the modem TX tail.
    txtail = 10

    # Configure CDMA parameters. These
    # settings are reasonable defaults.
    persistence = 200
    slottime = 20

    # You can configure the interface to send
    # out identification on the channel with
    # a set interval by configuring the
    # following two parameters. The KISS
    # interface will only ID if the set
    # interval has elapsed since it's last
    # actual transmission. The interval is
    # configured in seconds.
    # This option is commented out and not
    # used by default.
    # id_callsign = MYCALL-0
    # id_interval = 600

    # Whether to use KISS flow-control.
    # This is useful for modems that have
    # a small internal packet buffer, but
    # support packet flow control instead.
    flow_control = false

.. _interfaces-ax25:

AX.25 KISS Interface
====================

If you're using Reticulum on amateur radio spectrum, you might want to
use the AX.25 KISS interface. This way, Reticulum will automatically
encapsulate it's traffic in AX.25 and also identify your stations
transmissions with your callsign and SSID. 

Only do this if you really need to! Reticulum doesn't need the AX.25
layer for anything, and it incurs extra overhead on every packet to
encapsulate in AX.25.

A more efficient way is to use the plain KISS interface with the
beaconing functionality described above.

.. code::

  [[Packet Radio AX.25 KISS Interface]]
    type = AX25KISSInterface

    # Set the station callsign and SSID
    callsign = NO1CLL
    ssid = 0

    # Enable interface if you want use it!
    interface_enabled = True

    # Serial port for the device
    port = /dev/ttyUSB2

    # Set the serial baud-rate and other
    # configuration parameters.
    speed = 115200    
    databits = 8
    parity = none
    stopbits = 1

    # Set the modem preamble. A 150ms
    # preamble should be a reasonable
    # default, but may need to be
    # increased for radios with slow-
    # opening squelch and long TX/RX
    # turnaround
    preamble = 150

    # Set the modem TX tail. In most
    # cases this should be kept as low
    # as possible to not waste airtime.
    txtail = 10

    # Configure CDMA parameters. These
    # settings are reasonable defaults.
    persistence = 200
    slottime = 20

    # Whether to use KISS flow-control.
    # This is useful for modems with a
    # small internal packet buffer.
    flow_control = false

.. _interfaces-options:

Common Interface Options
========================

A number of general configuration options are available on most interfaces.
These can be used to control various aspects of interface behaviour.


 * | The ``enabled`` option tells Reticulum whether or not
     to bring up the interface. Defaults to ``False``. For any
     interface to be brought up, the ``enabled`` option
     must be set to ``True`` or ``Yes``.

 * | The ``mode`` option allows selecting the high-level behaviour
     of the interface from a number of options.

     - The default value is ``full``. In this mode, all discovery,
       meshing and transport functionality is available.

     - In the ``access_point`` (or shorthand ``ap``) mode, the
       interface will operate as a network access point. In this
       mode, announces will not be automatically broadcasted on
       the interface, and paths to destinations on the interface
       will have a much shorter expiry time. This mode is useful
       for creating interfaces that are mostly quiet, unless when
       someone is actually using them. An example of this could
       be a radio interface serving a wide area, where users are
       expected to connect momentarily, use the network, and then
       disappear again.

 * | The ``outgoing`` option sets whether an interface is allowed
     to transmit. Defaults to ``True``. If set to ``False`` or ``No``
     the interface will only receive data, and never transmit.

 * | The ``network_name`` option sets the virtual network name for
     the interface. This allows multiple separate network segments
     to exist on the same physical channel or medium.

 * | The ``passphrase`` option sets an authentication passphrase on
     the interface. This option can be used in conjunction with the
     ``network_name`` option, or be used alone.

 * | The ``ifac_size`` option allows customising the length of the
     Interface Authentication Codes carried by each packet on named
     and/or authenticated network segments. It is set by default to
     a size suitable for the interface in question, but can be set
     to a custom size between 8 and 512 bits by using this option.
     In normal usage, this option should not be changed from the
     default.

 * | The ``announce_cap`` option lets you configure the maximum
     bandwidth to allocate, at any given time, to propagating
     announces and other network upkeep traffic. It is configured at
     2% by default, and should normally not need to be changed. Can
     be set to any value between ``1`` and ``100``.

     *If an interface exceeds its announce cap, it will queue announces
     for later transmission. Reticulum will always prioritise propagating
     announces from nearby nodes first. This ensures that the local
     topology is prioritised, and that slow networks are not overwhelmed
     by interconnected fast networks.*

     *Destinations that are rapidly re-announcing will be down-prioritised
     further. Trying to get "first-in-line" by announce spamming will have
     the exact opposite effect: Getting moved to the back of the queue every
     time a new announce from the excessively announcing destination is received.*

     *This means that it is always beneficial to select a balanced
     announce rate, and not announce more often than is actually necesarry
     for your application to function.*

 * | The ``bitrate`` option configures the interface bitrate.
     Reticulum will use interface speeds reported by hardware, or
     try to guess a suitable rate when the hardware doesn't report
     any. In most cases, the automatically found rate should be
     sufficient, but it can be configured by using the ``bitrate``
     option, to set the interface speed in *bits per second*.


.. _interfaces-modes:

Interface Modes
===============

The optional ``mode`` setting is available on all interfaces, and allows
selecting the high-level behaviour of the interface from a number of modes.
These modes affect how Reticulum selects paths in the network, how announces
are propagated, how long paths are valid and how paths are discovered.

Configuring modes on interfaces is **not** strictly necessary, but can be useful
when building or connecting to more complex networks. If your Reticulum
instance is not running a Transport Node, it is rarely useful to configure
interface modes, and in such cases interfaces should generally be left in
the default mode.

 * | The default mode is ``full``. In this mode, all discovery,
     meshing and transport functionality is activated.

 * | The ``gateway`` mode (or shorthand ``gw``) also has all
     discovery, meshing and transport functionality available,
     but will additionally try to discover unknown paths on
     behalf of other nodes residing on the ``gateway`` interface.
     If Reticulum receives a path request for an unknown
     destination, from a node on a ``gateway`` interface, it
     will try to discover this path via all other active interfaces,
     and forward the discovered path to the requestor if one is
     found.

   | If you want to allow other nodes to widely resolve paths or connect
     to a network via an interface, it might be useful to put it in this
     mode. By creating a chain of ``gateway`` interfaces, other
     nodes will be able to immediately discover paths to any
     destination along the chain.

   | *Please note!* It is the interface *facing the clients* that
     must be put into ``gateway`` mode for this to work, not
     the interface facing the wider network (for this, the ``boundary``
     mode can be useful, though).

 * | In the ``access_point`` (or shorthand ``ap``) mode, the
     interface will operate as a network access point. In this
     mode, announces will not be automatically broadcasted on
     the interface, and paths to destinations on the interface
     will have a much shorter expiry time. In addition, path
     requests from clients on the access point interface will
     be handled in the same way as the ``gateway`` interface.

   | This mode is useful for creating interfaces that remain
     quiet, until someone actually starts using them. An example
     of this could be a radio interface serving a wide area,
     where users are expected to connect momentarily, use the
     network, and then disappear again.

 * | The ``roaming`` mode should be used on interfaces that are
     roaming (physically mobile), seen from the perspective of
     other nodes in the network. As an example, if a vehicle is
     equipped with an external LoRa interface, and an internal,
     WiFi-based interface, that serves devices that are moving
     *with* the vehicle, the external LoRa interface should be
     configured as ``roaming``, and the internal interface can
     be left in the default mode. With transport enabled, such
     a setup will allow all internal devices to reach each other,
     and all other devices that are available on the LoRa side
     of the network, when they are in range. Devices on the LoRa
     side of the network will also be able to reach devices
     internal to the vehicle, when it is in range. Paths via
     ``roaming`` interfaces also expire faster.

 * | The purpose of the ``boundary`` mode is to specify interfaces
     that establish connectivity with network segments that are
     significantly different than the one this node exists on.
     As an example, if a Reticulum instance is part of a LoRa-based
     network, but also has a high-speed connection to a
     public Transport Node available on the Internet, the interface
     connecting over the Internet should be set to ``boundary`` mode.

For a table describing the impact of all modes on announce propagation,
please see the :ref:`Announce Propagation Rules<understanding-announcepropagation>` section.

.. _interfaces-announcerates:

Announce Rate Control
=====================

The built-in announce control mechanisms and the default ``announce_cap``
option described above are sufficient most of the time, but in some cases, especially on fast
interfaces, it may be useful to control the target announce rate. Using the
``announce_rate_target``, ``announce_rate_grace`` and ``announce_rate_penalty``
options, this can be done on a per-interface basis, and moderates the *rate at
which received announces are re-broadcasted to other interfaces*.

 * | The ``announce_rate_target`` option sets the minimum amount of time,
     in seconds, that should pass between received announces, for any one
     destination. As an example, setting this value to ``3600`` means that
     announces *received* on this interface will only be re-transmitted and
     propagated to other interfaces once every hour, no matter how often they
     are received.

 * | The optional ``announce_rate_grace`` defines the number of times a destination
     can violate the announce rate before the target rate is enforced.

 * | The optional ``announce_rate_penalty`` configures an extra amount of
     time that is added to the normal rate target. As an example, if a penalty
     of ``7200`` seconds is defined, once the rate target is enforced, the
     destination in question will only have its announces propagated every
     3 hours, until it lowers its actual announce rate to within the target.

These mechanisms, in conjunction with the ``annouce_cap`` mechanisms mentioned
above means that it is essential to select a balanced announce strategy for
your destinations. The more balanced you can make this decision, the easier
it will be for your destinations to make it into slower networks that many hops
away. Or you can prioritise only reaching high-capacity networks with more frequent
announces.

Current statistics and information about announce rates can be viewed using the
``rnpath -r`` command.

It is important to note that there is no one right or wrong way to set up announce
rates. Slower networks will naturally tend towards using less frequent announces to
conserve bandwidth, while very fast networks can support applications that
need very frequent announces. Reticulum implements these mechanisms to ensure
that a large span of network types can seamlessly *co-exist* and interconnect.

.. _interfaces-ingress-control:

New Destination Rate Limiting
=============================

On public interfaces, where anyone may connect and announce new destinations,
it can be useful to control the rate at which announces for *new*  destinations are
processed.

If a large influx of announces for newly created or previously unknown destinations
occur within a short amount of time, Reticulum will place these announces on hold,
so that announce traffic for known and previously established destinations can
continue to be processed without interruptions.

After the burst subsides, and an additional waiting period has passed, the held
announces will be released at a slow rate, until the hold queue is cleared. This
also means, that should a node decide to connect to a public interface, announce
a large amount of bogus destinations, and then disconnect, these destination will
never make it into path tables and waste network bandwidth on retransmitted
announces.

**It's important to note** that the ingress control works at the level of *individual
sub-interfaces*. As an example, this means that one client on a :ref:`TCP Server Interface<interfaces-tcps>`
cannot disrupt processing of incoming announces for other connected clients on the same
:ref:`TCP Server Interface<interfaces-tcps>`. All other clients on the same interface will still have new announces
processed without interruption.

By default, Reticulum will handle this automatically, and ingress announce
control will be enabled on interface where it is sensible to do so. It should
generally not be neccessary to modify the ingress control configuration,
but all the parameters are exposed for configuration if needed.

 * | The ``ingress_control`` option tells Reticulum whether or not
     to enable announce ingress control on the interface. Defaults to
     ``True``.

 * | The ``ic_new_time`` option configures how long (in seconds) an
     interface is considered newly spawned. Defaults to ``2*60*60`` seconds. This
     option is useful on publicly accessible interfaces that spawn new
     sub-interfaces when a new client connects. 

 * | The ``ic_burst_freq_new`` option sets the maximum announce ingress
     frequency for newly spawned interfaces. Defaults to ``3.5``
     announces per second.

 * | The ``ic_burst_freq`` option sets the maximum announce ingress
     frequency for other interfaces. Defaults to ``12`` announces
     per second.

     *If an interface exceeds its burst frequency, incoming announces
     for unknown destinations will be temporarily held in a queue, and
     not processed until later.*

 * | The ``ic_max_held_announces`` option sets the maximum amount of
     unique announces that will be held in the queue. Any additional
     unique announces will be dropped. Defaults to ``256`` announces.

 * | The ``ic_burst_hold`` option sets how much time (in seconds) must
     pass after the burst frequency drops below its threshold, for the
     announce burst to be considered cleared. Defaults to ``60``
     seconds.

 * | The ``ic_burst_penalty`` option sets how much time (in seconds) must
     pass after the burst is considered cleared, before held announces can
     start being released from the queue. Defaults to ``5*60``
     seconds.

 * | The ``ic_held_release_interval`` option sets how much time (in seconds)
     must pass between releasing each held announce from the queue. Defaults
     to ``30`` seconds.

