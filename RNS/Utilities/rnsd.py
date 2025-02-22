#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2016-2022 Mark Qvist / unsigned.io
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

import RNS
import argparse
import signal
import time

from RNS._version import __version__


def program_setup(configdir, verbosity = 0, quietness = 0, service = False):
    targetverbosity = verbosity-quietness

    if service:
        targetlogdest  = RNS.LOG_FILE
        targetverbosity = None
    else:
        targetlogdest  = RNS.LOG_STDOUT

    reticulum = RNS.Reticulum(configdir=configdir, verbosity=targetverbosity, logdest=targetlogdest)
    if reticulum.is_connected_to_shared_instance:
        RNS.log("Started rnsd version {version} connected to another shared local instance, this is probably NOT what you want!".format(version=__version__), RNS.LOG_WARNING)
    else:
        if RNS.Reticulum.get_instance().shared_instance_interface:
            RNS.Reticulum.get_instance().shared_instance_interface.server.daemon_threads = True
        RNS.log("Started rnsd version {version}".format(version=__version__), RNS.LOG_NOTICE)
        #signal.signal(signal.SIGINT, reticulum.sigint_handler)
        signal.signal(signal.SIGTERM, reticulum.sigterm_handler)

    try:
        while True:
            time.sleep(1)
    finally:
        reticulum.stop()


def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Network Stack Daemon")
        parser.add_argument("--config", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
        parser.add_argument('-v', '--verbose', action='count', default=0)
        parser.add_argument('-q', '--quiet', action='count', default=0)
        parser.add_argument('-s', '--service', action='store_true', default=False, help="rnsd is running as a service and should log to file")
        parser.add_argument("--exampleconfig", action='store_true', default=False, help="print verbose configuration example to stdout and exit")
        parser.add_argument("--version", action="version", version="rnsd {version}".format(version=__version__))
        
        args = parser.parse_args()

        if args.exampleconfig:
            print(__example_rns_config__)
            return

        if args.config:
            configarg = args.config
        else:
            configarg = None

        program_setup(configdir = configarg, verbosity=args.verbose, quietness=args.quiet, service=args.service)

    except KeyboardInterrupt:
        print("")
        exit()

__example_rns_config__ = '''# This is an example Reticulum config file.
# You should probably edit it to include any additional,
# interfaces and settings you might need.

[reticulum]

# If you enable Transport, your system will route traffic
# for other peers, pass announces and serve path requests.
# This should be done for systems that are suited to act
# as transport nodes, ie. if they are stationary and
# always-on. This directive is optional and can be removed
# for brevity.

enable_transport = No


# By default, the first program to launch the Reticulum
# Network Stack will create a shared instance, that other
# programs can communicate with. Only the shared instance
# opens all the configured interfaces directly, and other
# local programs communicate with the shared instance over
# a local socket. This is completely transparent to the
# user, and should generally be turned on. This directive
# is optional and can be removed for brevity.

share_instance = Yes


# If you want to run multiple *different* shared instances
# on the same system, you will need to specify different
# shared instance ports for each. The defaults are given
# below, and again, these options can be left out if you
# don't need them.

shared_instance_port = 37428
instance_control_port = 37429


# On systems where running instances may not have access
# to the same shared Reticulum configuration directory,
# it is still possible to allow full interactivity for
# running instances, by manually specifying a shared RPC
# key. In almost all cases, this option is not needed, but
# it can be useful on operating systems such as Android.
# The key must be specified as bytes in hexadecimal.

# rpc_key = e5c032d3ec4e64a6aca9927ba8ab73336780f6d71790


# It is possible to allow remote management of Reticulum
# systems using the various built-in utilities, such as
# rnstatus and rnpath. You will need to specify one or
# more Reticulum Identity hashes for authenticating the
# queries from client programs. For this purpose, you can
# use existing identity files, or generate new ones with
# the rnid utility.

# enable_remote_management = yes
# remote_management_allowed = 9fb6d773498fb3feda407ed8ef2c3229, 2d882c5586e548d79b5af27bca1776dc


# You can configure Reticulum to panic and forcibly close
# if an unrecoverable interface error occurs, such as the
# hardware device for an interface disappearing. This is
# an optional directive, and can be left out for brevity.
# This behaviour is disabled by default.

panic_on_interface_error = No


# When Transport is enabled, it is possible to allow the
# Transport Instance to respond to probe requests from
# the rnprobe utility. This can be a useful tool to test
# connectivity. When this option is enabled, the probe
# destination will be generated from the Identity of the
# Transport Instance, and printed to the log at startup.
# Optional, and disabled by default.

respond_to_probes = No


[logging]
# Valid log levels are 0 through 7:
#   0: Log only critical information
#   1: Log errors and lower log levels
#   2: Log warnings and lower log levels
#   3: Log notices and lower log levels
#   4: Log info and lower (this is the default)
#   5: Verbose logging
#   6: Debug logging
#   7: Extreme logging

loglevel = 4


# The interfaces section defines the physical and virtual
# interfaces Reticulum will use to communicate on. This
# section will contain examples for a variety of interface
# types. You can modify these or use them as a basis for
# your own config, or simply remove the unused ones.

[interfaces]

  # This interface enables communication with other
  # link-local Reticulum nodes over UDP. It does not
  # need any functional IP infrastructure like routers
  # or DHCP servers, but will require that at least link-
  # local IPv6 is enabled in your operating system, which
  # should be enabled by default in almost any OS. See
  # the Reticulum Manual for more configuration options.

  [[Default Interface]]
    type = AutoInterface
    enabled = yes


  # The following example enables communication with other
  # local Reticulum peers using UDP broadcasts.
  
  [[UDP Interface]]
    type = UDPInterface
    enabled = no
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


  # This example demonstrates a TCP server interface.
  # It will listen for incoming connections on the
  # specified IP address and port number.
  
  [[TCP Server Interface]]
    type = TCPServerInterface
    enabled = no

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


  # To connect to a TCP server interface, you would
  # naturally use the TCP client interface. Here's
  # an example. The target_host can either be an IP
  # address or a hostname

  [[TCP Client Interface]]
    type = TCPClientInterface
    enabled = no
    target_host = 127.0.0.1
    target_port = 4242


  # This example shows how to make your Reticulum
  # instance available over I2P, and connect to
  # another I2P peer. Please be aware that you
  # must have an I2P router running on your system
  # with the SAMv3 API enabled for this to work.

  [[I2P]]
    type = I2PInterface
    enabled = no
    connectable = yes
    peers = ykzlw5ujbaqc2xkec4cpvgyxj257wcrmmgkuxqmqcur7cq3w3lha.b32.i2p


  # Here's an example of how to add a LoRa interface
  # using the RNode LoRa transceiver.

  [[RNode LoRa Interface]]
    type = RNodeInterface

    # Enable interface if you want use it!
    enabled = no

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
    # following two parameters. The trans-
    # ceiver will only ID if the set
    # interval has elapsed since it's last
    # actual transmission. The interval is
    # configured in seconds.
    # This option is commented out and not
    # used by default.
    # id_callsign = MYCALL-0
    # id_interval = 600

    # For certain homebrew RNode interfaces
    # with low amounts of RAM, using packet
    # flow control can be useful. By default
    # it is disabled.
    flow_control = False
    
    
  # An example KISS modem interface. Useful for running
  # Reticulum over packet radio hardware.

  [[Packet Radio KISS Interface]]
    type = KISSInterface

    # Enable interface if you want use it!
    enabled = no

    # Serial port for the device
    port = /dev/ttyUSB1

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


  # If you're using Reticulum on amateur radio spectrum,
  # you might want to use the AX.25 KISS interface. This
  # way, Reticulum will automatically encapsulate it's
  # traffic in AX.25 and also identify your stations
  # transmissions with your callsign and SSID.
  # 
  # Only do this if you really need to! Reticulum doesn't
  # need the AX.25 layer for anything, and it incurs extra
  # overhead on every packet to encapsulate in AX.25.
  #
  # A more efficient way is to use the plain KISS interface
  # with the beaconing functionality described above.

  [[Packet Radio AX.25 KISS Interface]]
    type = AX25KISSInterface

    # Set the station callsign and SSID
    callsign = NO1CLL
    ssid = 0

    # Enable interface if you want use it!
    enabled = no

    # Serial port for the device
    port = /dev/ttyUSB2

    # Set the serial baud-rate and other
    # configuration parameters.
    speed = 115200    
    databits = 8
    parity = none
    stopbits = 1

    # Whether to use KISS flow-control.
    # This is useful for modems with a
    # small internal packet buffer.
    flow_control = false

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

'''

if __name__ == "__main__":
    main()
