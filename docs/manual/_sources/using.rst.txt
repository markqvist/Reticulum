.. _using-main:

******************************
Using Reticulum on Your System
******************************

Reticulum is not installed as a driver or kernel module, as one might expect
of a networking stack. Instead, Reticulum is distributed as a Python module.
This means that no special privileges are required to install or use it. It
is also very light-weight, and easy to transfer to and install on new systems.
Any program or application that uses Reticulum will automatically load and
initialise Reticulum when it starts.

In many cases, this approach is sufficient. When any program needs to use
Reticulum, it is loaded, initialised, interfaces are brought up, and the
program can now communicate over any Reticulum networks available. If another
program starts up and also wants access to the same Reticulum network, the
instance is simply shared. This works for any number of programs running
concurrently, and is very easy to use, but depending on your use case, there
are other options.

Configuration & Data
--------------------

A Reticulum stores all information that it needs to function in a single file-
system directory. By default, this directory is ``~/.reticulum``, but you can
use any directory you wish. You can also run multiple separate Reticulum
instances on the same physical system, in complete isolation from each other,
or connected together.

In most cases, a single physical system will only need to run one Reticulum
instance. This can either be launched at boot, as a system service, or simply
be brought up when a program needs it. In either case, any number of programs
running on the same system will automatically share the same Reticulum instance,
if the configuration allows for it, which it does by default.

The entire configuration of Reticulum is found in the ``~/.reticulum/config``
file. When Reticulum is first started on a new system, a basic, functional
configuration file is created. The default configuration looks like this:

.. code::

  # This is the default Reticulum config file.
  # You should probably edit it to include any additional,
  # interfaces and settings you might need.

  # Only the most basic options are included in this default
  # configuration. To see a more verbose, and much longer,
  # configuration example, you can run the command:
  # rnsd --exampleconfig


  [reticulum]

  # If you enable Transport, your system will route traffic
  # for other peers, pass announces and serve path requests.
  # This should only be done for systems that are suited to
  # act as transport nodes, ie. if they are stationary and
  # always-on. This directive is optional and can be removed
  # for brevity.

  enable_transport = False


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


  # You can configure Reticulum to panic and forcibly close
  # if an unrecoverable interface error occurs, such as the
  # hardware device for an interface disappearing. This is
  # an optional directive, and can be left out for brevity.
  # This behaviour is disabled by default.

  panic_on_interface_error = No


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
      interface_enabled = True

If Reticulum infrastructure already exists locally, you probably don't need to
change anything, and you may already be connected to a wider network. If not,
you will probably need to add relevant *interfaces* to the configuration, in
order to communicate with other systems. It is a good idea to read the comments
and explanations in the above default config. It will teach you the basic
concepts you need to understand to configure your network. Once you have done that,
take a look at the :ref:`Interfaces<interfaces-main>` chapter of this manual.

Included Utility Programs
-------------------------

If you often use Reticulum from several different programs, or simply want
Reticulum to stay available all the time, for example if you are hosting
a transport node, you might want to run Reticulum as a separate service that
other programs, applications and services can utilise.

The rnsd Utility
================

It is very easy to run Reticulum as a service. Simply run the included ``rnsd`` command.
When ``rnsd`` is running, it will keep all configured interfaces open, handle transport if
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
     Status  : Up
     Serving : 1 program
     Rate    : 1.00 Gbps
     Traffic : 83.13 KB↑
               86.10 KB↓

  AutoInterface[Local]
     Status  : Up
     Mode    : Full
     Rate    : 10.00 Mbps
     Peers   : 1 reachable
     Traffic : 63.23 KB↑
               80.17 KB↓

  TCPInterface[RNS Testnet Frankfurt/frankfurt.rns.unsigned.io:4965]
     Status  : Up
     Mode    : Full
     Rate    : 10.00 Mbps
     Traffic : 187.27 KB↑
               74.17 KB↓

  RNodeInterface[RNode UHF]
     Status  : Up
     Mode    : Access Point
     Rate    : 1.30 kbps
     Access  : 64-bit IFAC by <…e702c42ba8>
     Traffic : 8.49 KB↑
               9.23 KB↓

  Reticulum Transport Instance <5245a8efe1788c6a70e1> running

.. code:: text

  usage: rnstatus [-h] [--config CONFIG] [--version] [-a] [-v]

  Reticulum Network Stack Status

  optional arguments:
    -h, --help       show this help message and exit
    --config CONFIG  path to alternative Reticulum config directory
    --version        show program's version number and exit
    -a, --all        show all interfaces
    -v, --verbose


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

  usage: rnpath.py [-h] [--config CONFIG] [--version] [-t] [-r] [-d] [-D] [-w seconds] [-v] [destination]
  
  Reticulum Path Discovery Utility
  
  positional arguments:
    destination           hexadecimal hash of the destination
  
  optional arguments:
    -h, --help            show this help message and exit
    --config CONFIG       path to alternative Reticulum config directory
    --version             show program's version number and exit
    -t, --table           show all known paths
    -r, --rates           show announce rate info
    -d, --drop            remove the path to a destination
    -D, --drop-announces  drop all queued announces
    -w seconds            timeout before giving up
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

On a Reticulum instance with several serial port based interfaces, it can be
beneficial to use the fixed device names for the serial ports, instead
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
might be plugged and unplugged in different orders, or when device name
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