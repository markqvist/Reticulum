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