.. _using-main:

******************************
Using Reticulum on Your System
******************************

Reticulum is not installed as a driver or kernel module, as one might expect
of a networking stack. Instead, Reticulum is distributed as a Python module, 
containing the networking core, and a set of utility and daemon programs.

This means that no special privileges are required to install or use it. It
is also very light-weight, and easy to transfer to, and install on new systems.

When you have Reticulum installed, any program or application that uses Reticulum
will automatically load and initialise Reticulum when it starts, if it is not
already running.

In many cases, this approach is sufficient. When any program needs to use
Reticulum, it is loaded, initialised, interfaces are brought up, and the
program can now communicate over any Reticulum networks available. If another
program starts up and also wants access to the same Reticulum network, the already
running instance is simply shared. This works for any number of programs running
concurrently, and is very easy to use, but depending on your use case, there
are other options.

Configuration & Data
--------------------

Reticulum stores all information that it needs to function in a single file-system
directory. When Reticulum is started, it will look for a valid configuration
directory in the following places:

- ``/etc/reticulum``
- ``~/.config/reticulum``
- ``~/.reticulum``

If no existing configuration directory is found, the directory ``~/.reticulum``
is created, and the default configuration will be automatically created here.
You can move it to one of the other locations if you wish.

It is also possible to use completely arbitrary configuration directories by
specifying the relevant command-line parameters when running Reticulum-based
programs. You can also run multiple separate Reticulum instances on the same
physical system, either in isolation from each other, or connected together.

In most cases, a single physical system will only need to run one Reticulum
instance. This can either be launched at boot, as a system service, or simply
be brought up when a program needs it. In either case, any number of programs
running on the same system will automatically share the same Reticulum instance,
if the configuration allows for it, which it does by default.

The entire configuration of Reticulum is found in the ``~/.reticulum/config``
file. When Reticulum is first started on a new system, a basic, but fully functional
configuration file is created. The default configuration looks like this:

.. code:: ini

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
  # instance names for each. On platforms supporting domain
  # sockets, this can be done with the instance_name option:

  instance_name = default

  # Some platforms don't support domain sockets, and if that
  # is the case, you can isolate different instances by
  # specifying a unique set of ports for each:

  # shared_instance_port = 37428
  # instance_control_port = 37429


  # If you want to explicitly use TCP for shared instance
  # communication, instead of domain sockets, this is also
  # possible, by using the following option:

  # shared_instance_type = tcp


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

  # panic_on_interface_error = No


  # When Transport is enabled, it is possible to allow the
  # Transport Instance to respond to probe requests from
  # the rnprobe utility. This can be a useful tool to test
  # connectivity. When this option is enabled, the probe
  # destination will be generated from the Identity of the
  # Transport Instance, and printed to the log at startup.
  # Optional, and disabled by default.

  # respond_to_probes = No


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
order to communicate with other systems.

You can generate a much more verbose configuration example by running the command:

``rnsd --exampleconfig``

The output includes examples for most interface types supported
by Reticulum, along with additional options and configuration parameters.

It is a good idea to read the comments and explanations in the above default config.
It will teach you the basic concepts you need to understand to configure your network.
Once you have done that, take a look at the :ref:`Interfaces<interfaces-main>` chapter
of this manual.

Included Utility Programs
-------------------------

Reticulum includes a range of useful utilities, both for managing your Reticulum
networks, and for carrying out common tasks over Reticulum networks, such as
transferring files to remote systems, and executing commands and programs remotely.

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

You can even run multiple instances of ``rnsd`` with different configurations on
the same system.

**Usage Examples**

Run ``rnsd``:

.. code:: text

  $ rnsd

  [2023-08-18 17:59:56] [Notice] Started rnsd version 0.5.8

Run ``rnsd`` in service mode, ensuring all logging output is sent directly to file:

.. code:: text

  $ rnsd -s

Generate a verbose and detailed configuration example, with explanations of all the
various configuration options, and interface configuration examples:

.. code:: text

  $ rnsd --exampleconfig

**All Command-Line Options**

.. code:: text

  usage: rnsd.py [-h] [--config CONFIG] [-v] [-q] [-s] [--exampleconfig] [--version]

  Reticulum Network Stack Daemon

  options:
    -h, --help        show this help message and exit
    --config CONFIG   path to alternative Reticulum config directory
    -v, --verbose
    -q, --quiet
    -s, --service     rnsd is running as a service and should log to file
    -i, --interactive drop into interactive shell after initialisation
    --exampleconfig   print verbose configuration example to stdout and exit
    --version         show program's version number and exit

You can easily add ``rnsd`` as an always-on service by :ref:`configuring a service<using-systemd>`.

The rnstatus Utility
====================

Using the ``rnstatus`` utility, you can view the status of configured Reticulum
interfaces, similar to the ``ifconfig`` program.

**Usage Examples**

Run ``rnstatus``:

.. code:: text

  $ rnstatus

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

  TCPInterface[RNS Testnet Dublin/dublin.connect.reticulum.network:4965]
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

  Reticulum Transport Instance <5245a8efe1788c6a1cd36144a270e13b> running

Filter output to only show some interfaces:

.. code:: text

  $ rnstatus rnode

  RNodeInterface[RNode UHF]
     Status  : Up
     Mode    : Access Point
     Rate    : 1.30 kbps
     Access  : 64-bit IFAC by <…e702c42ba8>
     Traffic : 8.49 KB↑
               9.23 KB↓

  Reticulum Transport Instance <5245a8efe1788c6a1cd36144a270e13b> running

**All Command-Line Options**

.. code:: text

  usage: rnstatus [-h] [--config CONFIG] [--version] [-a] [-A]
                  [-l] [-t] [-s SORT] [-r] [-j] [-R hash] [-i path]
                  [-w seconds] [-d] [-D] [-m] [-I seconds] [-v] [filter]

  Reticulum Network Stack Status

  positional arguments:
    filter                only display interfaces with names including filter

  options:
    -h, --help            show this help message and exit
    --config CONFIG       path to alternative Reticulum config directory
    --version             show program's version number and exit
    -a, --all             show all interfaces
    -A, --announce-stats  show announce stats
    -l, --link-stats      show link stats
    -t, --totals          display traffic totals
    -s, --sort SORT       sort interfaces by [rate, traffic, rx, tx, rxs, txs,
                                              announces, arx, atx, held]
    -r, --reverse         reverse sorting
    -j, --json            output in JSON format
    -R hash               transport identity hash of remote instance to get status from
    -i path               path to identity used for remote management
    -w seconds            timeout before giving up on remote queries
    -d, --discovered      list discovered interfaces
    -D                    show details and config entries for discovered interfaces
    -m, --monitor         continuously monitor status
    -I, --monitor-interval seconds
                          refresh interval for monitor mode (default: 1)
    -v, --verbose


.. note::
   When using ``-R`` to query a remote transport instance, you must also specify ``-i`` with the path to a management identity file that is authorized for remote management on the target system.

The rnid Utility
====================

With the ``rnid`` utility, you can generate, manage and view Reticulum Identities.
The program can also calculate Destination hashes, and perform encryption and
decryption of files.

Using ``rnid``, it is possible to asymmetrically encrypt files and information for
any Reticulum destination hash, and also to create and verify cryptographic signatures.

**Usage Examples**

Generate a new Identity:

.. code:: text

  $ rnid -g ./new_identity

Display Identity key information:

.. code:: text

  $ rnid -i ./new_identity -p

  Loaded Identity <984b74a3f768bef236af4371e6f248cd> from new_id
  Public Key  : 0f4259fef4521ab75a3409e353fe9073eb10783b4912a6a9937c57bf44a62c1e
  Private Key : Hidden

Encrypt a file for an LXMF user:

.. code:: text

  $ rnid -i 8dd57a738226809646089335a6b03695 -e my_file.txt

  Recalled Identity <bc7291552be7a58f361522990465165c> for destination <8dd57a738226809646089335a6b03695>
  Encrypting my_file.txt
  File my_file.txt encrypted for <bc7291552be7a58f361522990465165c> to my_file.txt.rfe

If the Identity for the destination is not already known, you can fetch it from the network by using the ``-R`` command-line option:

.. code:: text

  $ rnid -R -i 30602def3b3506a28ed33db6f60cc6c9 -e my_file.txt

  Requesting unknown Identity for <30602def3b3506a28ed33db6f60cc6c9>...
  Received Identity <2b489d06eaf7c543808c76a5332a447d> for destination <30602def3b3506a28ed33db6f60cc6c9> from the network
  Encrypting my_file.txt
  File my_file.txt encrypted for <2b489d06eaf7c543808c76a5332a447d> to my_file.txt.rfe

Decrypt a file using the Reticulum Identity it was encrypted for:

.. code:: text

  $ rnid -i ./my_identity -d my_file.txt.rfe

  Loaded Identity <2225fdeecaf6e2db4556c3c2d7637294> from ./my_identity
  Decrypting ./my_file.txt.rfe...
  File ./my_file.txt.rfe decrypted with <2225fdeecaf6e2db4556c3c2d7637294> to ./my_file.txt

**All Command-Line Options**

.. code:: text

  usage: rnid.py [-h] [--config path] [-i identity] [-g path] [-v] [-q] [-a aspects]
                 [-H aspects] [-e path] [-d path] [-s path] [-V path] [-r path] [-w path]
                 [-f] [-R] [-t seconds] [-p] [-P] [--version]

  Reticulum Identity & Encryption Utility

  options:
    -h, --help            show this help message and exit
    --config path         path to alternative Reticulum config directory
    -i, --identity identity
                          hexadecimal Reticulum identity or destination hash, or path to Identity file
    -g, --generate file   generate a new Identity
    -m, --import identity_data
                          import Reticulum identity in hex, base32 or base64 format
    -x, --export          export identity to hex, base32 or base64 format
    -v, --verbose         increase verbosity
    -q, --quiet           decrease verbosity
    -a, --announce aspects
                          announce a destination based on this Identity
    -H, --hash aspects    show destination hashes for other aspects for this Identity
    -e, --encrypt file    encrypt file
    -d, --decrypt file    decrypt file
    -s, --sign path       sign file
    -V, --validate path   validate signature
    -r, --read file       input file path
    -w, --write file      output file path
    -f, --force           write output even if it overwrites existing files
    -R, --request         request unknown Identities from the network
    -t seconds            identity request timeout before giving up
    -p, --print-identity  print identity info and exit
    -P, --print-private   allow displaying private keys
    -b, --base64          Use base64-encoded input and output
    -B, --base32          Use base32-encoded input and output
    --version             show program's version number and exit

.. _utility-rnpath:

The rnpath Utility
====================

With the ``rnpath`` utility, you can look up and view paths for
destinations on the Reticulum network.

**Usage Examples**

Resolve path to a destination:

.. code:: text

  $ rnpath c89b4da064bf66d280f0e4d8abfd9806

  Path found, destination <c89b4da064bf66d280f0e4d8abfd9806> is 4 hops away via <f53a1c4278e0726bb73fcc623d6ce763> on TCPInterface[Testnet/dublin.connect.reticulum.network:4965]

**All Command-Line Options**

.. code:: text

  usage: rnpath [-h] [--config CONFIG] [--version] [-t] [-m hops] [-r] [-d] [-D]
                [-x] [-w seconds] [-R hash] [-i path] [-W seconds] [-b] [-B] [-U]
                [--duration DURATION] [--reason REASON] [-p] [-j] [-v]
                [destination] [list_filter]

  Reticulum Path Management Utility

  positional arguments:
    destination           hexadecimal hash of the destination
    list_filter           filter for remote blackhole list view

  options:
    -h, --help            show this help message and exit
    --config CONFIG       path to alternative Reticulum config directory
    --version             show program's version number and exit
    -t, --table           show all known paths
    -m, --max hops        maximum hops to filter path table by
    -r, --rates           show announce rate info
    -d, --drop            remove the path to a destination
    -D, --drop-announces  drop all queued announces
    -x, --drop-via        drop all paths via specified transport instance
    -w seconds            timeout before giving up
    -R hash               transport identity hash of remote instance to manage
    -i path               path to identity used for remote management
    -W seconds            timeout before giving up on remote queries
    -b, --blackholed      list blackholed identities
    -B, --blackhole       blackhole identity
    -U, --unblackhole     unblackhole identity
    --duration DURATION   duration of blackhole enforcement in hours
    --reason REASON       reason for blackholing identity
    -p, --blackholed-list
                          view published blackhole list for remote transport instance
    -j, --json            output in JSON format
    -v, --verbose


The rnprobe Utility
====================

The ``rnprobe`` utility lets you probe a destination for connectivity, similar
to the ``ping`` program. Please note that probes will only be answered if the
specified destination is configured to send proofs for received packets. Many
destinations will not have this option enabled, so most destinations will not
be probable.

You can enable a probe-reply destination on Reticulum Transport Instances by
setting the ``respond_to_probes`` configuration directive. Reticulum will then
print the probe destination to the log on Transport Instance startup.

**Usage Examples**

Probe a destination:

.. code:: text

  $ rnprobe rnstransport.probe 2d03725b327348980d570f739a3a5708

  Sent 16 byte probe to <2d03725b327348980d570f739a3a5708>
  Valid reply received from <2d03725b327348980d570f739a3a5708>
  Round-trip time is 38.469 milliseconds over 2 hops

Send a larger probe:

.. code:: text

  $ rnprobe rnstransport.probe 2d03725b327348980d570f739a3a5708 -s 256

  Sent 16 byte probe to <2d03725b327348980d570f739a3a5708>
  Valid reply received from <2d03725b327348980d570f739a3a5708>
  Round-trip time is 38.781 milliseconds over 2 hops

If the interface that receives the probe replies supports reporting radio
parameters such as **RSSI** and **SNR**, the ``rnprobe`` utility will print
these as part of the result as well.

.. code:: text

  $ rnprobe rnstransport.probe e7536ee90bd4a440e130490b87a25124
  
  Sent 16 byte probe to <e7536ee90bd4a440e130490b87a25124>
  Valid reply received from <e7536ee90bd4a440e130490b87a25124>
  Round-trip time is 1.809 seconds over 1 hop [RSSI -73 dBm] [SNR 12.0 dB]

**All Command-Line Options**

.. code:: text

  usage: rnprobe [-h] [--config CONFIG] [-s SIZE] [-n PROBES]
                 [-t seconds] [-w seconds] [--version] [-v]
                 [full_name] [destination_hash]

  Reticulum Probe Utility

  positional arguments:
    full_name             full destination name in dotted notation
    destination_hash      hexadecimal hash of the destination

  options:
    -h, --help            show this help message and exit
    --config CONFIG       path to alternative Reticulum config directory
    -s SIZE, --size SIZE  size of probe packet payload in bytes
    -n PROBES, --probes PROBES
                          number of probes to send
    -t seconds, --timeout seconds
                          timeout before giving up
    -w seconds, --wait seconds
                          time between each probe
    --version             show program's version number and exit
    -v, --verbose


The rncp Utility
================

The ``rncp`` utility is a simple file transfer tool. Using it, you can transfer
files through Reticulum.

**Usage Examples**

Run rncp on the receiving system, specifying which identities are allowed to send files:
  
.. code:: text

  $ rncp --listen -a 1726dbad538775b5bf9b0ea25a4079c8 -a c50cc4e4f7838b6c31f60ab9032cbc62

You can also specify allowed identity hashes (one per line) in the file ~/.rncp/allowed_identities
and simply running the program in listener mode:

.. code:: text

  $ rncp --listen

From another system, copy a file to the receiving system:

.. code:: text

  $ rncp ~/path/to/file.tgz 73cbd378bb0286ed11a707c13447bb1e

Or fetch a file from the remote system:

.. code:: text

  $ rncp --fetch ~/path/to/file.tgz 73cbd378bb0286ed11a707c13447bb1e

The default identity file is stored in ``~/.reticulum/identities/rncp``, but you can use
another one, which will be created if it does not already exist

.. code:: text

  $ rncp ~/path/to/file.tgz 73cbd378bb0286ed11a707c13447bb1e -i /path/to/identity

**All Command-Line Options**

.. code:: text

  usage: rncp [-h] [--config path] [-v] [-q] [-S] [-l] [-F] [-f]
              [-j path] [-b seconds] [-a allowed_hash] [-n] [-p]
              [-i identity] [-w seconds] [--version] [file] [destination]

  Reticulum File Transfer Utility

  positional arguments:
    file                  file to be transferred
    destination           hexadecimal hash of the receiver

  options:
    -h, --help            show this help message and exit
    --config path         path to alternative Reticulum config directory
    -v, --verbose         increase verbosity
    -q, --quiet           decrease verbosity
    -S, --silent          disable transfer progress output
    -l, --listen          listen for incoming transfer requests
    -C, --no-compress     disable automatic compression
    -F, --allow-fetch     allow authenticated clients to fetch files
    -f, --fetch           fetch file from remote listener instead of sending
    -j, --jail path       restrict fetch requests to specified path
    -s, --save path       save received files in specified path
    -O, --overwrite       Allow overwriting received files, instead of adding postfix
    -b seconds            announce interval, 0 to only announce at startup
    -a allowed_hash       allow this identity (or add in ~/.rncp/allowed_identities)
    -n, --no-auth         accept requests from anyone
    -p, --print-identity  print identity and destination info and exit
    -i identity           path to identity to use
    -w seconds            sender timeout before giving up
    -P, --phy-rates       display physical layer transfer rates
    --version             show program's version number and exit


The rnx Utility
================

The ``rnx`` utility is a basic remote command execution program. It allows you to
execute commands on remote systems over Reticulum, and to view returned command
output. For a fully interactive remote shell solution, be sure to also take a look
at the `rnsh <https://github.com/acehoss/rnsh>`_ program.

**Usage Examples**

Run rnx on the listening system, specifying which identities are allowed to execute commands:

.. code:: text

  $ rnx --listen -a 941bed5e228775e5a8079fc38b1ccf3f -a 1b03013c25f1c2ca068a4f080b844a10

From another system, run a command on the remote:

.. code:: text

  $ rnx 7a55144adf826958a9529a3bcf08b149 "cat /proc/cpuinfo"

Or enter the interactive mode pseudo-shell:

.. code:: text

  $ rnx 7a55144adf826958a9529a3bcf08b149 -x

The default identity file is stored in ``~/.reticulum/identities/rnx``, but you can use
another one, which will be created if it does not already exist 

.. code:: text

  $ rnx 7a55144adf826958a9529a3bcf08b149 -i /path/to/identity -x

**All Command-Line Options**

.. code:: text

  usage: rnx [-h] [--config path] [-v] [-q] [-p] [-l] [-i identity] [-x] [-b] [-n] [-N]
             [-d] [-m] [-a allowed_hash] [-w seconds] [-W seconds] [--stdin STDIN]
             [--stdout STDOUT] [--stderr STDERR] [--version] [destination] [command]

  Reticulum Remote Execution Utility

  positional arguments:
    destination           hexadecimal hash of the listener
    command               command to be execute

  optional arguments:
    -h, --help            show this help message and exit
    --config path         path to alternative Reticulum config directory
    -v, --verbose         increase verbosity
    -q, --quiet           decrease verbosity
    -p, --print-identity  print identity and destination info and exit
    -l, --listen          listen for incoming commands
    -i identity           path to identity to use
    -x, --interactive     enter interactive mode
    -b, --no-announce     don't announce at program start
    -a allowed_hash       accept from this identity
    -n, --noauth          accept files from anyone
    -N, --noid            don't identify to listener
    -d, --detailed        show detailed result output
    -m                    mirror exit code of remote command
    -w seconds            connect and request timeout before giving up
    -W seconds            max result download time
    --stdin STDIN         pass input to stdin
    --stdout STDOUT       max size in bytes of returned stdout
    --stderr STDERR       max size in bytes of returned stderr
    --version             show program's version number and exit


The rnodeconf Utility
=====================

The ``rnodeconf`` utility allows you to inspect and configure existing :ref:`RNodes<rnode-main>`, and
to create and provision new :ref:`RNodes<rnode-main>` from any supported hardware devices.

**All Command-Line Options**

.. code:: text

  usage: rnodeconf [-h] [-i] [-a] [-u] [-U] [--fw-version version]
                   [--fw-url url] [--nocheck] [-e] [-E] [-C]
                   [--baud-flash baud_flash] [-N] [-T] [-b] [-B] [-p] [-D i]
                   [--display-addr byte] [--freq Hz] [--bw Hz] [--txp dBm]
                   [--sf factor] [--cr rate] [--eeprom-backup] [--eeprom-dump]
                   [--eeprom-wipe] [-P] [--trust-key hexbytes] [--version] [-f]
                   [-r] [-k] [-S] [-H FIRMWARE_HASH] [--platform platform]
                   [--product product] [--model model] [--hwrev revision]
                   [port]

  RNode Configuration and firmware utility. This program allows you to change
  various settings and startup modes of RNode. It can also install, flash and
  update the firmware on supported devices.

  positional arguments:
    port                  serial port where RNode is attached

  options:
    -h, --help            show this help message and exit
    -i, --info            Show device info
    -a, --autoinstall     Automatic installation on various supported devices
    -u, --update          Update firmware to the latest version
    -U, --force-update    Update to specified firmware even if version matches or is older than installed version
    --fw-version version  Use a specific firmware version for update or autoinstall
    --fw-url url          Use an alternate firmware download URL
    --nocheck             Don't check for firmware updates online
    -e, --extract         Extract firmware from connected RNode for later use
    -E, --use-extracted   Use the extracted firmware for autoinstallation or update
    -C, --clear-cache     Clear locally cached firmware files
    --baud-flash baud_flash
                          Set specific baud rate when flashing device. Default is 921600
    -N, --normal          Switch device to normal mode
    -T, --tnc             Switch device to TNC mode
    -b, --bluetooth-on    Turn device bluetooth on
    -B, --bluetooth-off   Turn device bluetooth off
    -p, --bluetooth-pair  Put device into bluetooth pairing mode
    -D, --display i       Set display intensity (0-255)
    -t, --timeout s       Set display timeout in seconds, 0 to disable
    -R, --rotation rotation
                          Set display rotation, valid values are 0 through 3
    --display-addr byte   Set display address as hex byte (00 - FF)
    --recondition-display
                          Start display reconditioning
    --np i                Set NeoPixel intensity (0-255)
    --freq Hz             Frequency in Hz for TNC mode
    --bw Hz               Bandwidth in Hz for TNC mode
    --txp dBm             TX power in dBm for TNC mode
    --sf factor           Spreading factor for TNC mode (7 - 12)
    --cr rate             Coding rate for TNC mode (5 - 8)
    -x, --ia-enable       Enable interference avoidance
    -X, --ia-disable      Disable interference avoidance
    -c, --config          Print device configuration
    --eeprom-backup       Backup EEPROM to file
    --eeprom-dump         Dump EEPROM to console
    --eeprom-wipe         Unlock and wipe EEPROM
    -P, --public          Display public part of signing key
    --trust-key hexbytes  Public key to trust for device verification
    --version             Print program version and exit
    -f, --flash           Flash firmware and bootstrap EEPROM
    -r, --rom             Bootstrap EEPROM without flashing firmware
    -k, --key             Generate a new signing key and exit
    -S, --sign            Display public part of signing key
    -H, --firmware-hash FIRMWARE_HASH
                          Set installed firmware hash
    --platform platform   Platform specification for device bootstrap
    --product product     Product specification for device bootstrap
    --model model         Model code for device bootstrap
    --hwrev revision      Hardware revision for device bootstrap


For more information on how to create your own RNodes, please read the :ref:`Creating RNodes<rnode-creating>`
section of this manual.

.. _using-interface_discovery:
Discovering Interfaces
----------------------

Reticulum includes built-in functionality for discovering connectable interfaces over Reticulum itself. This is particularly useful in situations where you want to do one or more of the following:

* Discover connectable entrypoints available on the Internet
* Find connectable radio access points in the physical world
* Maintain connectivity to RNS instances with unknown or changing IP addresses

Discovered interfaces can be **auto-connected** by Reticulum, which makes it possible to create setups where an arbitrary interface can act simply as a bootstrap connection, that can be torn down again once more suitable interfaces have been discovered and connected.

The interface discovery mechanism uses announces sent over Reticulum itself, and supports both publicly readable interfaces and private, encrypted discovery, that can only be decoded by specified *network identities*. It is also possible to specify which network identities should be considered valid sources for discovered interfaces, so that interfaces published by unknown entities are ignored.

.. note::
  A *network identity* is a normal Reticulum identity keyset that can be used by
  one or more transport nodes to identify them as belonging to the same overall
  network. In the context of interface discovery, this makes it easy to manage
  connecting to only the particular networks you care about, even if those networks
  utilize many individual physical transport node.

  This also makes it convenient to auto-connect discovered interfaces only for networks you have some level of trust in.

For information on how to make your interfaces discoverable, see the :ref:`Discoverable Interfaces<interfaces-discoverable>` chapter of this manual. The current section will focus on how to actually *discover and connect to* interfaces available on the network.

In its most basic form, enabling interface discovery is as simple as setting ``discover_interfaces`` to ``true`` in your Reticulum config:

.. code:: text
  
  [reticulum]
  ...
  discover_interfaces = yes
  ...

Once this option is enabled, your RNS instance will start listening for interface discovery announces, and store them for later use or inspection. You can list discovered interfaces with the ``rnstatus`` utility:

.. code:: text

  $ rnstatus -d
  
  Name           Type      Status       Last Heard   Value  Location       
  -------------------------------------------------------------------------
  Sideband Hub   Backbone  ✓ Available  1h  ago      16     46.2316, 6.0536
  RNS Amsterdam  Backbone  ✓ Available  32m ago      16     52.3865, 4.9037


You can view more detailed information about discovered interfaces, including configuration snippets for pasting directly into your ``[interfaces]`` config, by using the ``rnstatus -D`` option:

.. code:: text
  
  $ rnstatus -D sideband

  Transport ID : 521c87a83afb8f29e4455e77930b973b
  Name         : Sideband Hub
  Type         : BackboneInterface
  Status       : Available
  Transport    : Enabled
  Distance     : 2 hops
  Discovered   : 9h and 40m ago
  Last Heard   : 1h and 15m ago
  Location     : 46.2316, 6.0536
  Address      : sideband.connect.reticulum.network:7822
  Stamp Value  : 16

  Configuration Entry:
    [[Sideband Hub]]
      type = BackboneInterface
      enabled = yes
      remote = sideband.connect.reticulum.network
      target_port = 7822
      transport_identity = 521c87a83afb8f29e4455e77930b973b

In addition to providing local interface discovery information and control, the ``rnstatus`` utility can export discovered interface data in machine-readable JSON format using the ``rnstatus -d --json`` option. This can be useful for exporting the data to external applications such as status pages, access point maps and similar.

To control what sources are considered valid for discovered sources, additional
configuration options can be specified for the interface discovery system.

* The ``interface_discovery_sources`` option is a list of the network or transport identities from which interfaces will be accepted. If this option is set, all others will be ignored. If this option is not set, discovered interfaces will be accepted from any source, but are still subject to stamp value requirements.

* The ``required_discovery_value`` options specifies the minimum stamp value required for the interface announce to be considered valid. To make it computationally difficult to spam the network with a large number of defunct or malicious interfaces, each announced interface requires a valid cryptographical stamp, of configurable difficulty value.

* The ``autoconnect_discovered_interfaces`` value defaults to ``0``, and specifies the maximum number of discovered interfaces that should be auto-connected at any given time. If set to a number greater than ``0``, Reticulum automatically manages discovered interface connections, and will bring discovered interfaces up and down based on availability. You can at any time add discovered interfaces to your configuration manually, to persistently keep them available.

* The ``network_identity`` option specifies the *network identity* for this RNS instance. This identity is used both to sign (and potentially encrypt) *outgoing* interface discovery announces, and to decrypt incoming discovery information.

The configuration snippet below contains an example of setting these additional configuration options:

.. code:: text
  
  [reticulum]
  ...
  discover_interfaces = yes
  interface_discovery_sources = 521c87a83afb8f29e4455e77930b973b
  required_discovery_value = 16
  autoconnect_discovered_interfaces = 3
  network_identity = ~/.reticulum/storage/identities/my_network
  ...

Remote Management
-----------------

It is possible to allow remote management of Reticulum
systems using the various built-in utilities, such as
``rnstatus`` and ``rnpath``. To do so, you will need to set
the ``enable_remote_management`` directive in the ``[reticulum]``
section of the configuration file. You will also need to specify
one or more Reticulum Identity hashes for authenticating the
queries from client programs. For this purpose, you can use
existing identity files, or generate new ones with the rnid utility.

The following is a truncated example of enabling remote management
in the Reticulum configuration file:

.. code:: text
  
  [reticulum]
  ...
  enable_remote_management = yes
  remote_management_allowed = 9fb6d773498fb3feda407ed8ef2c3229, 2d882c5586e548d79b5af27bca1776dc
  ...

For a complete example configuration, you can run ``rnsd --exampleconfig``.

.. _using-blackhole_management:

Blackhole Management
--------------------

Reticulum networks are fundamentally permissionless and open, allowing anyone with a compatible interface to participate. While this openness is essential for a resilient and decentralized network, it also exposes the network to potential abuse, such as peers flooding the network with excessive announce broadcasts or other forms of resource exhaustion.

The **Blackhole** system provides tools to help manage this problem. It allows operators and individual users to block specific identities at the Transport layer, preventing them from propagating announces through your node, and for other nodes to reach them through your network.

.. note::
  
  There is fundamentally **no way** to *globally* block or censor any identity or destination in Reticulum networks. The blackhole functionality will prevent announces from (and traffic to) all destinations associated with the blackholed identity *on your own network segments only*.

  This provides users and operators with control over what they want to allow *on their own network segments*, but there is no way to globally censor or remove an identity, as long as *someone* is willing to provide transport for it.

This functionality serves a dual purpose:

*   **For Individual Users:** It offers a simple way to maintain a quiet and efficient local network by manually blocking spammy or unwanted peers.
*   **For Network Operators:** It enables the creation of federated, community-wide security standards. By publishing and sharing blackhole lists, operators can protect large infrastructures and distribute spam filtering rules across the mesh without manual intervention.


Local Blackhole Management
==========================

The most immediate way to manage unwanted identities is through manual configuration using the ``rnpath`` utility. This allows you to instantly block or unblock specific identities on your local Transport Instance.

**Blackholing an Identity**

To block an identity, use the ``-B`` (or ``--blackhole``) flag followed by the identity hash. You can optionally specify a duration and a reason, which are useful for logging and future reference.

.. code:: text

  $ rnpath -B 3a4f8b9c1d2e3f4g5h6i7j8k9l0m1n2o

You can also add a duration (in hours) and a reason:

.. code:: text

  $ rnpath -B 3a4f8b9c1d2e3f4g5h6i7j8k9l0m1n2o --duration 24 --reason "Excessive announces"

**Lifting Blackholes**

To remove an identity from the blackhole, use the ``-U`` (or ``--unblackhole``) flag:

.. code:: text

  $ rnpath -U 3a4f8b9c1d2e3f4g5h6i7j8k9l0m1n2o

**Viewing the Blackhole List**

To see all identities currently blackholed on your local instance, use the ``-b`` (or ``--blackholed``) flag:

.. code:: text

  $ rnpath -b

  <3a4f8b9c1d2e3f4g5h6i7j8k9l0m1n2o> blackholed for 23h, 56m (Excessive announces)
  <399ea050ce0eed1816c300bcb0840938> blackholed indefinitely (Announce spam)
  <d56a4fa02c0a77b3575935aedd90bdb2> blackholed indefinitely (Announce spam)
  <2b9ec651326d9bc274119054c70fb75e> blackholed indefinitely (Announce spam)
  <1178a8f1fad405bf2ad153bf5036bdfd> blackholed indefinitely (Announce spam)



Automated List Sourcing
=======================

Manually blocking identities is effective for immediate threats, but maintaining an up-to-date blocklist for a large network is impractical. Reticulum supports **automated list sourcing**, allowing your node to subscribe to blackhole lists maintained by trusted peers, or a central authority you manage yourself.

.. warning:: **Verify Before Subscribing!**
   Subscribing to a blackhole source is a powerful action that grants that source the ability to dictate who you can communicate with. Before adding a source to your configuration, verify that the maintainer aligns with your usage policy and values. Blindly subscribing to untrusted lists could inadvertently block legitimate peers or essential services.

When enabled, your Transport Instance will periodically (approximately once per hour) connect to configured sources, retrieve their latest blackhole lists, and automatically merge them into your local blocklist. This provides "set-and-forget" protection for both individual users and large networks.

**Configuration**

To enable automated sourcing, add the ``blackhole_sources`` option to the ``[reticulum]`` section of your configuration file. This option accepts a comma-separated list of Transport Identity hashes that you trust to provide valid blackhole lists.

.. code:: ini

  [reticulum]
  ...
  # Automatically fetch blackhole lists from these trusted sources
  blackhole_sources = 521c87a83afb8f29e4455e77930b973b, 68a4aa91ac350c4087564e8a69f84e86
  ...

**How It Works**

1.  The ``BlackholeUpdater`` service runs in the background.
2.  For every identity hash listed in ``blackhole_sources``, it attempts to establish a temporary link to the destination ``rnstransport.info.blackhole``.
3.  It requests the ``/list`` path, which returns a dictionary of blocked identities and their associated metadata.
4.  The received list is merged with your local ``blackholed_identities`` database.
5.  The lists are persisted to disk, ensuring they survive restarts.

.. note::
  You can verify the external lists you are subscribed to, and their contents, without importing them by using ``rnpath -p``. See the :ref:`rnpath utility documentation<utility-rnpath>` for details on querying remote blackhole lists.


Publishing Blackhole Lists
==========================

If you are operating a public gateway, a community hub, or simply wish to share your blocklist with others, you can configure your instance to act as a blackhole list publisher. This allows other nodes to subscribe to *your* definitions of unwanted traffic.

**Enabling Publishing**

To publish your local blackhole list, enable the ``publish_blackhole`` option in the ``[reticulum]`` section:

.. code:: ini

  [reticulum]
  ...
  publish_blackhole = yes
  ...

When this is enabled, your Transport Instance will register a request handler at ``rnstransport.info.blackhole``. Any peer that connects to this destination and requests ``/list`` will receive the complete set of identities currently present in your local blackhole database.

**Federation and Trust**

The blackhole system relies on the trust relationship between the subscriber and the publisher. By subscribing to a source, you are implicitly trusting that source to only block identities that are genuinely detrimental to the network.

As the ecosystem matures, this system is designed to integrate with **Network Identities**. This allows communities to verify that a published blackhole list is actually provided by a specific network or organization with a certain level of reputation and trustworthiness, adding a layer of cryptographic trust to the federation process. This prevents malicious actors from publishing fake lists intended to censor legitimate traffic.

For operators, this creates a scalable model where maintaining a single high-quality blocklist can protect thousands of downstream peers, drastically reducing the administrative overhead of network hygiene.

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

Systemwide Service
^^^^^^^^^^^^^^^^^^

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

Userspace Service
^^^^^^^^^^^^^^^^^

Alternatively you can use a user systemd service instead of a system wide one. This way the whole setup can be done as a regular user.
Create a user systemd service files ``~/.config/systemd/user/rnsd.service`` with the following content:

.. code:: text

  [Unit]
  Description=Reticulum Network Stack Daemon
  After=default.target

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
  ExecStart=RNS_BIN_DIR/rnsd --service

  [Install]
  WantedBy=default.target

Replace ``RNS_BIN_DIR`` with the path to your Reticulum binary directory (eg. /home/USERNAMEHERE/rns/bin).

Start user service:

.. code:: text

  systemctl --user daemon-reload
  systemctl --user start rnsd.service

If you want to automatically start ``rnsd`` without having to log in as the USERNAMEHERE, do:

.. code:: text
  
  sudo loginctl enable-linger USERNAMEHERE
  systemctl --user enable rnsd.service
  

