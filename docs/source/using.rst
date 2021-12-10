.. _using-main:

******************************
Using Reticulum on Your System
******************************

Reticulum is not installed as a driver or kernel module, as one might expect
of a networking stack. Instead, Reticulum is distributed as a Python module.
This means that no special privileges are required to install or use it.
Any program or application that uses Reticulum will automatically load and
initialise Reticulum when it starts.

In many cases, this approach is sufficient. When any program needs to use
Reticulum, it is loaded, initialised, interfaces are brought up, and the
program can now communicate over Reticulum. If another program starts up
and also wants access to the same Reticulum network, the instance is simply
shared. This works for any number of programs running concurrently, and is
very easy to use, but depending on your use case, there are other options.

Included Utility Programs
-------------------------

If you often use Reticulum from several different programs, or simply want
Reticulum to stay available all the time, for example if you are hosting
a transport node, you might want to run Reticulum as a separate service that
other programs, applications and services can utilise.

The rnsd Utility
================

To do so is very easy. Simply run the included ``rnsd`` command. When ``rnsd``
is running, it will keep all configured interfaces open, handle transport if
it is enabled, and allow any other programs to immediately utilise the
Reticulum network it is configured for.

You can even run multiple instances of rnsd with different configurations on
the same system.

.. code:: text

  # Install Reticulum
  pip3 install rns

  # Run rnsd
  rnsd

.. code:: text

  usage: rnsd [-h] [--config CONFIG] [-v] [-q] [--version]

  Reticulum Network Stack Daemon

  optional arguments:
    -h, --help       show this help message and exit
    --config CONFIG  path to alternative Reticulum config directory
    -v, --verbose
    -q, --quiet
    --version        show program's version number and exit

You can easily add ``rnsd`` as an always-on service by :ref:`configuring a service<using-systemd>`.

The rnstatus Utility
====================

Using the ``rnstatus`` utility, you can view the status of configured Reticulum
interfaces, similar to the ``ifconfig`` program.

.. code:: text

  # Run rnstatus
  rnstatus

  # Example output
  Shared Instance[37428]
         Status: Up
         Connected applications: 1
         RX: 1.13 KB
         TX: 1.07 KB

  UDPInterface[Default UDP Interface/0.0.0.0:4242]
         Status: Up
         RX: 1.01 KB
         TX: 1.01 KB

  TCPInterface[RNS Testnet Frankfurt/frankfurt.rns.unsigned.io:4965]
         Status: Up
         RX: 1.37 KB
         TX: 9.02 KB

.. code:: text

  usage: rnsd [-h] [--config CONFIG] [-v] [-q] [--version]

  Reticulum Network Stack Daemon

  optional arguments:
    -h, --help       show this help message and exit
    --config CONFIG  path to alternative Reticulum config directory
    -v, --verbose
    -q, --quiet
    --version        show program's version number and exit


The rnpath Utility
====================

With the ``rnpath`` utility, you can look up and view paths for
destinations on the Reticulum network.

.. code:: text

  # Run rnpath
  rnpath eca6f4e4dc26ae329e61

  # Example output
  Path found, destination <eca6f4e4dc26ae329e61> is 4 hops away via <56b115c30cd386cad69c> on TCPInterface[Testnet/frankfurt.rns.unsigned.io:4965]

.. code:: text

  usage: rnpath.py [-h] [--config CONFIG] [--version] [-v] [destination]

  Reticulum Path Discovery Utility

  positional arguments:
    destination      hexadecimal hash of the destination

  optional arguments:
    -h, --help       show this help message and exit
    --config CONFIG  path to alternative Reticulum config directory
    --version        show program's version number and exit
    -v, --verbose


The rnprobe Utility
====================

The ``rnprobe`` utility lets you probe a destination for connectivity, similar
to the ``ping`` program. Please note that probes will only be answered if the
specified destination is configured to send proofs for received packets. Many
destinations will not have this option enabled, and will not be probable.

.. code:: text

  # Run rnprobe
  python3 -m RNS.Utilities.rnprobe example_utilities.echo.request 9382f334de63217a4278

  # Example output
  Sent 16 byte probe to <9382f334de63217a4278>
  Valid reply received from <9382f334de63217a4278>
  Round-trip time is 38.469 milliseconds over 2 hops

.. code:: text

  usage: rnprobe.py [-h] [--config CONFIG] [--version] [-v] [full_name] [destination_hash]

  Reticulum Probe Utility

  positional arguments:
    full_name         full destination name in dotted notation
    destination_hash  hexadecimal hash of the destination

  optional arguments:
    -h, --help        show this help message and exit
    --config CONFIG   path to alternative Reticulum config directory
    --version         show program's version number and exit
    -v, --verbose


Improving System Configuration
------------------------------

If you are setting up a system for permanent use with Reticulum, there is a
few system configuration changes that can make this easier to administrate.
These changes will be detailed here.


Fixed Serial Port Names
=======================

On a Reticulum node with several serial port based interfaces, it can be
beneficial to use the fixed name device nodes for the serial ports, instead
of the dynamically allocated shorthands such as ``/dev/ttyUSB0``. Under most
Debian-based distributions, including Ubuntu and Raspberry Pi OS, these nodes
can be found under ``/dev/serial/by-id``.

You can use such a device path directly in place of the numbered shorthands.
Here is an example of a packet radio TNC configured as such:

.. code:: text

  [[Packet Radio KISS Interface]]
    type = KISSInterface
    interface_enabled = True
    outgoing = true
    port = /dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_43891CKM-if00-port0
    speed = 115200    
    databits = 8
    parity = none
    stopbits = 1
    preamble = 150
    txtail = 10
    persistence = 200
    slottime = 20

Using this methodology avoids potential naming mix-ups where physical devices
might be plugged and unplugged in different orders, or when node name
assignment varies from one boot to another.

.. _using-systemd:

Reticulum as a System Service
=============================

Instead of starting Reticulum manually, you can install ``rnsd`` as a system
service and have it start automatically at boot.

If you installed Reticulum with ``pip``, the ``rnsd`` program will most likely
be located in a user-local installation path only, which means ``systemd`` will not
be able to execute it. In this case, you can simply symlink the ``rnsd`` program
into a directory that is in systemd's path:

.. code:: text

  sudo ln -s $(which rnsd) /usr/local/bin/

You can then create the service file ``/etc/systemd/system/rnsd.service`` with the
following content:

.. code:: text

  [Unit]
  Description=Reticulum Network Stack Daemon
  After=multi-user.target

  [Service]
  # If you run Reticulum on WiFi devices,
  # or other devices that need some extra
  # time to initialise, you might want to
  # add a short delay before Reticulum is
  # started by systemd:
  # ExecStartPre=/bin/sleep 10
  Type=simple
  Restart=always
  RestartSec=3
  User=USERNAMEHERE
  ExecStart=rnsd --service

  [Install]
  WantedBy=multi-user.target

Be sure to replace ``USERNAMEHERE`` with the user you want to run ``rnsd`` as.

To manually start ``rnsd`` run:

.. code:: text

  sudo systemctl start rnsd

If you want to automatically start ``rnsd`` at boot, run:

.. code:: text

  sudo systemctl enable rnsd