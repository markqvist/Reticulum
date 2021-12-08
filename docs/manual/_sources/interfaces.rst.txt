
.. _interfaces-main:

********************
Supported Interfaces
********************

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
nodes over UDP. It does not need any functional IP infrastructure like
routers or DHCP servers, but will require at least some sort of switching
medium between peers (a wired switch, a WiFi access point or similar), and
that link-local IPv6 is enabled in your operating system, which should be
enabled by default in almost all OSes.

.. code::

  # This example demonstrates a TCP server interface.
  # It will listen for incoming connections on the
  # specified IP address and port number.
  
  [[Default Interface]]
    type = AutoInterface
    interface_enabled = True
    outgoing = True

    # You can create multiple isolated Reticulum
    # networks on the same physical LAN by
    # specifying different Group IDs.

    group_id = reticulum

If you are connected to the Internet with IPv6, and your provider will route
IPv6 multicast, you can potentially configure the Auto Interface to globally
autodiscover other Reticulum nodes within your selected Group ID. You can specify
the discovery scope by setting it to one of ``link``, ``admin``, ``site``,
``organisation`` or ``global``.

.. code::
  
  [[Default Interface]]
    type = AutoInterface
    interface_enabled = True
    outgoing = True

    # Configure global discovery

    group_id = custom_network_name
    discovery_scope = global

    # Other configuration options

    discovery_port = 48555
    data_port = 49555

*Please Note!* If you use the Auto Interface, you will need the Python module
``netifaces`` installed on your system. You can install it with ``pip3 install netifaces``.


.. _interfaces-udp:

UDP Interface
=============

A UDP interface can be useful for communicating over IP networks, both
private and the internet. It can also allow broadcast communication
over IP networks, so it can provide an easy way to enable connectivity
with all other peers on a local area network.

*Please Note!* Using broadcast UDP traffic has performance implications,
especially on WiFi. If your goal is simply to enable easy communication
with all peers in your local ethernet broadcast domain, the
:ref:`Auto Interface<interfaces-auto>` performs better, and is just as
easy to use.

The below example is enabled by default on new Reticulum installations,
as it provides an easy way to get started and to test Reticulum on a
pre-existing LAN.

.. code::

  # This example enables communication with other
  # local Reticulum peers over UDP.
  
  [[Default UDP Interface]]
    type = UDPInterface
    interface_enabled = True
    outgoing = True
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

*Please Note!* If you use the ``device`` option, you will need the Python module
``netifaces`` installed on your system. You can install it with ``pip3 install netifaces``.

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
    outgoing = True

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

*Please Note!* If you use the ``device`` option, you will need the Python module
``netifaces`` installed on your system. You can install it with ``pip3 install netifaces``.

.. _interfaces-tcpc:

TCP Client Interface
====================

To connect to a TCP server interface, you would naturally use the TCP client
interface. Many TCP Client interfaces from different peers can connect to the
same TCP Server interface at the same time.

.. code::

  # Here's an example of a TCP Client interface. The
  # target_host can either be an IP address or a hostname.

  [[TCP Client Interface]]
    type = TCPClientInterface
    interface_enabled = True
    outgoing = True
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
    outgoing = True
    kiss_framing = True
    target_host = 127.0.0.1
    target_port = 8001

**Caution!** Only use the KISS framing option when connecting to external devices
and programs like soundmodems and similar over TCP. When using the
``TCPClientInterface`` in conjunction with the ``TCPServerInterface`` you should
never enable ``kiss_framing``, since this will disable internal reliability and
recovery mechanisms that greatly improves performance over unreliable and
intermittent TCP links.


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

    # Allow transmit on interface. Setting
    # this to false will create a listen-
    # only interface.
    outgoing = true

    # Serial port for the device
    port = /dev/ttyUSB0

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
    flow_control = False

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
    outgoing = True

    # Serial port for the device
    port = /dev/ttyUSB0

    # Set the serial baud-rate and other
    # configuration parameters.
    speed = 115200
    databits = 8
    parity = none
    stopbits = 1

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
    outgoing = true

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

    # Allow transmit on interface.
    outgoing = True

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