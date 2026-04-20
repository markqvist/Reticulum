********************
Getting Started Fast
********************

The best way to get started with the Reticulum Network Stack depends on what
you want to do. This guide will outline sensible starting paths for different
scenarios.


Standalone Reticulum Installation
=================================
If you simply want to install Reticulum and related utilities on a system,
the easiest way is via the ``pip`` package manager:

.. code:: shell

   pip install rns

If you do not already have pip installed, you can install it using the package manager
of your system with a command like ``sudo apt install python3-pip``,
``sudo pamac install python-pip`` or similar.

You can also dowload the Reticulum release wheels from GitHub, or other release channels,
and install them offline using ``pip``:

.. code:: shell

   pip install ./rns-1.1.2-py3-none-any.whl

On platforms that limit user package installation via ``pip``, you may need to manually
allow this using the ``--break-system-packages`` command line flag when installing. This
will not actually break any packages, unless you have installed Reticulum directly via
your operating system's package manager.

.. code:: shell

  pip install rns --break-system-packages

For more detailed installation instructions, please see the
:ref:`Platform-Specific Install Notes<install-guides>` section.

After installation is complete, it might be helpful to refer to the
:ref:`Using Reticulum on Your System<using-main>` chapter.

Resolving Dependency & Installation Issues
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
On some platforms, there may not be binary packages available for all dependencies, and
``pip`` installation may fail with an error message. In these cases, the issue can usually
be resolved by installing the development essentials packages for your platform:

.. code:: shell

    # Debian / Ubuntu / Derivatives
    sudo apt install build-essential

    # Arch / Manjaro / Derivatives
    sudo pamac install base-devel

    # Fedora
    sudo dnf groupinstall "Development Tools" "Development Libraries"

With the base development packages installed, ``pip`` should be able to compile any missing
dependencies from source, and complete installation even on platforms that don't have pre-
compiled packages available.

Try Using a Reticulum-based Program
=============================================

If you simply want to try using a program built with Reticulum, a :ref:`range of different
programs <software-main>` exist that allow basic communication and a various other useful functions,
even over extremely low-bandwidth Reticulum networks.


Using the Included Utilities
=============================================
Reticulum comes with a range of included utilities that make it easier to
manage your network, check connectivity and make Reticulum available to other
programs on your system.

You can use ``rnsd`` to run Reticulum as a background or foreground service,
and the ``rnstatus``, ``rnpath`` and ``rnprobe`` utilities to view and query
network status and connectivity.

To learn more about these utility programs, have a look at the
:ref:`Using Reticulum on Your System<using-main>` chapter of this manual.


Creating a Network With Reticulum
=============================================
To create a network, you will need to specify one or more *interfaces* for
Reticulum to use. This is done in the Reticulum configuration file, which by
default is located at ``~/.reticulum/config``. You can get an example
configuration file with all options via ``rnsd --exampleconfig``.

When Reticulum is started for the first time, it will create a default
configuration file, with one active interface. This default interface uses
your existing Ethernet and WiFi networks (if any), and only allows you to
communicate with other Reticulum peers within your local broadcast domains.

To communicate further, you will have to add one or more interfaces. The default
configuration includes a number of examples, ranging from using TCP over the
internet, to LoRa and Packet Radio interfaces.

With Reticulum, you only need to configure what interfaces you want to communicate
over. There is no need to configure address spaces, subnets, routing tables,
or other things you might be used to from other network types.

Once Reticulum knows which interfaces it should use, it will automatically
discover topography and configure transport of data to any destinations it
knows about.

In situations where you already have an established WiFi or Ethernet network, and
many devices that want to utilise the same external Reticulum network paths (for example over
LoRa), it will often be sufficient to let one system act as a Reticulum gateway, by
adding any external interfaces to the configuration of this system, and then enabling transport on it. Any
other device on your local WiFi will then be able to connect to this wider Reticulum
network just using the default (:ref:`AutoInterface<interfaces-auto>`) configuration.

Possibly, the examples in the config file are enough to get you started. If
you want more information, you can read the :ref:`Building Networks<networks-main>`
and :ref:`Interfaces<interfaces-main>` chapters of this manual, but most importantly,
start with reading the next section, :ref:`Bootstrapping Connectivity<bootstrapping-connectivity>`,
as this provides the most essential understanding of how to ensure reliable
connectivity with a minimum of maintenance.


.. _bootstrapping-connectivity:

Bootstrapping Connectivity
==========================

Reticulum is not a service you subscribe to, nor is it a single global network you "join". It is a *networking stack*; a toolkit for building communications systems that align with your specific values, requirements, and operational environment. The way you choose to connect to other Reticulum peers is entirely your own choice.

One of the most powerful aspects of Reticulum is that it provides a multitude of tools to establish, maintain, and optimize connectivity. You can use these tools in isolation or combine them in complex configurations to achieve a vast array of goals.

Whether your aim is to create a completely private, air-gapped network for your family; to build a resilient community mesh that survives infrastructure collapse; to connect far and wide to as many nodes as possible; or simply to maintain a reliable, encrypted link to a specific organization you care about, Reticulum provides the mechanisms to make it happen.

There is no "right" or "wrong" way to build a Reticulum network, and you don't need to be a network engineer just to get started. If the information flows in the way you intend, and your privacy and security requirements are met, your configuration is a success. Reticulum is designed to make the most challenging and difficult scenarios attainable, even when other networking technologies fail.


Finding Your Way
^^^^^^^^^^^^^^^^

When you first start using Reticulum, you need a way to obtain connectivity with the peers you want to communicate with - the process of *bootstrapping connectivity*.

.. important::
  
  A common mistake in modern networking is the reliance on a few centralized, hard-coded entrypoints. If every user simply connects to the same list of public IP addresses found on a website, the network becomes brittle, centralized, and ultimately fails to deliver on the promise of decentralization and resilience. You have a responsibility here.

Reticulum encourages the approach of *organic growth*. Instead of relying on permanent static connections to distant servers, you can use temporary bootstrap connections to continously *discover* more relevant or local infrastructure. Once discovered, your system can automatically form stronger, more direct links to these peers, and discard the temporary bootstrap links. This results in a web of connections that are geographically relevant, resilient and efficient.

It *is* possible to simply add a few public entrypoints to the ``[interfaces]`` section of your Reticulum configuration and be connected, but a better option is to enable :ref:`interface discovery<using-interface_discovery>` and either manually select relevant, local interfaces, or enable discovered interface auto-connection.

A relevant option in this context is the :ref:`bootstrap only<interfaces-options>` interface option. This is an automated tool for better distributing connectivity. By enabling interface discovery and auto-connection, and marking an interface as ``bootstrap_only``, you tell Reticulum to use that interface primarliy to find connectivity options, and then disconnect it once sufficient entrypoints have been discovered. This helps create a network topology that favors locality and resilience over the simple centralization caused by using only a few static entrypoints.

Good places to find interface definitions for bootstrapping connectivity are websites like
`directory.rns.recipes <https://directory.rns.recipes/>`_ and `rmap.world <https://rmap.world/>`_.


Build Personal Infrastructure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You do not need a datacenter to be a meaningful part of the Reticulum ecosystem. In fact, the most important nodes in the network are often the smallest ones.

We strongly encourage everyone, even home users, to think in terms of building **personal infrastructure**. Don't connect every phone, tablet, and computer in your house directly to a public internet gateway. Instead, repurpose an old computer, a Raspberry Pi, or a supported router to act as your own, personal **Transport Node**:

*   Your local Transport Node sits in your home, connected to your WiFi and perhaps a radio interface (like an RNode).
*   You configure this node with a ``bootstrap_only`` interface (perhaps a TCP tunnel to a wider network) and enable interface discovery.
*   While you sleep, work, or cook, your node listens to the network. It discovers other local community members, validates their Network Identities, and automatically establishes direct links.
*   Your personal devices now connect to your *local* node, which is integrated into a living, breathing local mesh. Your traffic flows through local paths provided by other real people in the community rather than bouncing off a distant server.

**Don't wait for others to build the networks you want to see**. Every network is important, perhaps even most so those that support individual families and persons. Once enough of this personal, local infrastructure exist, connecting them directly to each other, without traversing the public Internet, becomes inevitable.


Mixing Strategies
^^^^^^^^^^^^^^^^^

There is no requirement to commit to a single strategy. The most robust setups often mix static, dynamic, and discovered interfaces.

*   **Static Interfaces:** You maintain a permanent interface to a trusted friend or organization using a static configuration.
*   **Bootstrap Links:** You connect a ``bootstrap_only`` interface to a public gateway on the Internet to scan for new connectable peers or to regain connectivity if your other interfaces fail.
*   **Local Wide-Area Connectivity:** You run a ``RNodeInterface`` on a shared frequency, giving you completely self-sovereign and private wide-area access to both your own network and other Reticulum peers globally, without any "service providers" being able to control or monitor how you interact with people.

By combining these methods, you create a system that is secure against single points of failure, adaptable to changing network conditions, and better integrated into your physical and social reality.


Network Health & Responsibility
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As you participate in the wider networks you discover and build, you will inevitably encounter peers that are misconfigured, malicious, or simply broken. To protect your resources and those of your local peers, you can utilize the :ref:`Blackhole Management<using-blackhole_management>` system.

Whether you manually block a spamming identity or subscribe to a blackhole list maintained by a trusted Network Identity, these tools help ensure that *your* transport capacity is used for what *you* consider legitimate communication. This keeps your local segment efficient and contributes to the health of the wider network.


Contributing to the Global Ret
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have the means to host a stable node with a public IP address, consider becoming a :ref:`Public Entrypoint<hosting-entrypoints>`. By :ref:`publishing your interface as discoverable<interfaces-discoverable>`, you provide a potential connection point for others, helping the network grow and reach new areas.

For guidelines on how to properly configure a public entrypoint, refer to the :ref:`Hosting Public Entrypoints<hosting-entrypoints>` section.

Connect to the Distributed Backbone
===================================

A global, distributed backbone of Reticulum Transport Nodes is being run by volunteers from around the world. This network constitutes a heterogenous collection of both public and private nodes that form an uncoordinated, voluntary inter-networking backbone that currently provides global transport and internetworking capabilities for Reticulum.

As a good starting point, you can find interface definitions for connecting your own networks to this backbone on websites such as `directory.rns.recipes <https://directory.rns.recipes/>`_ and `rmap.world <https://rmap.world/>`_.

.. tip::
  Don't rely on just a single connection to the distributed backbone for everyday use. It is much better to have several redundant connections configured, and enable the interface discovery options, so your nodes can continously discover peering opportunities as the network evolves. Refer to the :ref:`Bootstrapping Connectivity<bootstrapping-connectivity>` section to understand the options.



.. _hosting-entrypoints:

Hosting Public Entrypoints
==========================

If you want to help build a strong global interconnection backbone, you can host a public (or private) entry-point to a Reticulum network over the
Internet. This section offers some helpful pointers. Once you have set up your public entrypoint, it is a great idea to :ref:`make it discoverable over Reticulum<interfaces-discoverable>`.

You will need a machine, physical or virtual with a public IP address, that can be reached by other devices on the Internet.

The most efficient and performant way to host a connectable entry-point supporting many
users is to use the ``BackboneInterface``. This interface type is fully compatible with
the ``TCPClientInterface`` and ``TCPServerInterface`` types, but much faster and uses
less system resources, allowing your device to handle thousands of connections even on
small systems.

It is also important to set your connectable interface to ``gateway`` mode, since this
will greatly improve network convergence time and path resolution for anyone connecting
to your entry-point.

.. code:: ini

  # This example demonstrates a backbone interface
  # configured for acting as a gateway for users to
  # connect to either a public or private network

  [[Public Gateway]]
    type = BackboneInterface
    enabled = yes
    mode = gateway
    listen_on = 0.0.0.0
    port = 4242

    # On publicly available interfaces, it can be
    # a good idea to configure sensible announce
    # rate targets.
    announce_rate_target = 3600
    announce_rate_penalty = 3600
    announce_rate_grace = 12

If instead you want to make a private entry-point from the Internet, you can use the
:ref:`IFAC name and passphrase options<interfaces-options>` to secure your interface with a network name and passphrase.

.. code:: ini

  # A private entry-point requiring a pre-shared
  # network name and passphrase to connect to.

  [[Private Gateway]]
    type = BackboneInterface
    enabled = yes
    mode = gateway
    listen_on = 0.0.0.0
    port = 4242
    network_name = private_ret
    passphrase = 2owjajquafIanPecAc

If you are hosting an entry-point on an operating system that does not support
``BackboneInterface``, you can use ``TCPServerInterface`` instead, although it will
not be as performant.


Connecting Reticulum Instances Over the Internet
================================================
Reticulum currently offers three interfaces suitable for connecting instances over the Internet: :ref:`Backbone<interfaces-backbone>`, :ref:`TCP<interfaces-tcps>`
and :ref:`I2P<interfaces-i2p>`. Each interface offers a different set of features, and Reticulum
users should carefully choose the interface which best suites their needs.

The ``TCPServerInterface`` allows users to host an instance accessible over TCP/IP. This
method is generally faster, lower latency, and more energy efficient than using ``I2PInterface``,
however it also leaks more data about the server host.

The ``BackboneInterface`` is a very fast and efficient interface type available on POSIX operating
systems, designed to handle thousands of connections simultaneously with low memory, processing
and I/O overhead. It is fully compatible with the TCP-based interface types.

TCP connections reveal the IP address of both your instance and the server to anyone who can
inspect the connection. Someone could use this information to determine your location or identity. Adversaries
inspecting your packets may be able to record packet metadata like time of transmission and packet size.
Even though Reticulum encrypts traffic, TCP does not, so an adversary may be able to use
packet inspection to learn that a system is running Reticulum, and what other IP addresses connect to it.
Hosting a publicly reachable instance over TCP also requires a publicly reachable IP address,
which most Internet connections don't offer anymore.

The ``I2PInterface`` routes messages through the `Invisible Internet Protocol
(I2P) <https://geti2p.net/en/>`_. To use this interface, users must also run an I2P daemon in
parallel to ``rnsd``. For always-on I2P nodes it is recommended to use `i2pd <https://i2pd.website/>`_.

By default, I2P will encrypt and mix all traffic sent over the Internet, and
hide both the sender and receiver Reticulum instance IP addresses. Running an I2P node
will also relay other I2P user's encrypted packets, which will use extra
bandwidth and compute power, but also makes timing attacks and other forms of
deep-packet-inspection much more difficult.

I2P also allows users to host globally available Reticulum instances from non-public IP's and behind firewalls and NAT.

In general it is recommended to use an I2P node if you want to host a publicly accessible
instance, while preserving anonymity. If you care more about performance, and a slightly
easier setup, use TCP.

Adding Radio Interfaces
=======================
Once you have Reticulum installed and working, you can add radio interfaces with
any compatible hardware you have available. Reticulum supports a wide range of radio
hardware, and if you already have any available, it is very likely that it will
work with Reticulum. For information on how to configure this, see the
:ref:`Interfaces<interfaces-main>` section of this manual.

If you do not already have transceiver hardware available, you can easily and
cheaply build an :ref:`RNode<rnode-main>`, which is a general-purpose long-range
digital radio transceiver, that integrates easily with Reticulum.

To build one yourself requires installing a custom firmware on a supported LoRa
development board with an auto-install script or web-based flasher.
Please see the :ref:`Communications Hardware<hardware-main>` chapter for a guide.
If you prefer purchasing a ready-made unit, you can refer to the
:ref:`list of suppliers<rnode-suppliers>`. 

Other radio-based hardware interfaces are being developed and made available by
the broader Reticulum community. You can find more information on such topics
over Reticulum-based information sharing systems.

If you have communications hardware that is not already supported by any of the
:ref:`existing interface types<interfaces-main>`, it is easy to write (and potentially
publish) a :ref:`custom interface module<interfaces-custom>` that makes it compatible with Reticulum.


Creating and Using Custom Interfaces
====================================

While Reticulum includes a flexible and broad range of built-in interfaces, these
will not cover every conceivable type of communications hardware that Reticulum
can potentially use to communicate.

It is therefore possible to easily write your own interface modules, that can be
loaded at run-time and used on-par with any of the built-in interface types.

For more information on this subject, and code examples to build on, please see
the :ref:`Configuring Interfaces<interfaces-main>` chapter.


Develop a Program with Reticulum
===========================================
If you want to develop programs that use Reticulum, the easiest way to get
started is to install the latest release of Reticulum via pip:

.. code::

   pip install rns

The above command will install Reticulum and dependencies, and you will be
ready to import and use RNS in your own programs. The next step will most
likely be to look at some :ref:`Example Programs<examples-main>`.

The entire Reticulum API is documented in the :ref:`API Reference<api-main>`
chapter of this manual. Before diving in, it's probably a good idea to read
this manual in full, but at least start with the :ref:`Understanding Reticulum<understanding-main>` chapter.


.. _install-guides:

Platform-Specific Install Notes
==============================================

Some platforms require a slightly different installation procedure, or have
various quirks that are worth being aware of. These are listed here.

Android
^^^^^^^^^^^^^^^^^^^^^^^^
Reticulum can be used on Android in different ways. The easiest way to get
started is using an app like `Sideband <https://unsigned.io/sideband>`_.

For more control and features, you can use Reticulum and related programs via
the `Termux app <https://termux.com/>`_, at the time of writing available on
`F-droid <https://f-droid.org>`_.

Termux is a terminal emulator and Linux environment for Android based devices,
which includes the ability to use many different programs and libraries,
including Reticulum.

To use Reticulum within the Termux environment, you will need to install
``python`` and the ``python-cryptography`` library using ``pkg``, the package-manager
build into Termux. After that, you can use ``pip`` to install Reticulum.

From within Termux, execute the following:

.. code:: shell

    # First, make sure indexes and packages are up to date.
    pkg update
    pkg upgrade

    # Then install python and the cryptography library.
    pkg install python python-cryptography

    # Make sure pip is up to date, and install the wheel module.
    pip install wheel pip --upgrade

    # Install Reticulum
    pip install rns

If for some reason the ``python-cryptography`` package is not available for
your platform via the Termux package manager, you can attempt to build it
locally on your device using the following command:

.. code:: shell

    # First, make sure indexes and packages are up to date.
    pkg update
    pkg upgrade

    # Then install dependencies for the cryptography library.
    pkg install python build-essential openssl libffi rust

    # Make sure pip is up to date, and install the wheel module.
    pip install wheel pip --upgrade

    # To allow the installer to build the cryptography module,
    # we need to let it know what platform we are compiling for:
    export CARGO_BUILD_TARGET="aarch64-linux-android"

    # Start the install process for the cryptography module.
    # Depending on your device, this can take several minutes,
    # since the module must be compiled locally on your device.
    pip install cryptography

    # If the above installation succeeds, you can now install
    # Reticulum and any related software
    pip install rns

It is also possible to include Reticulum in apps compiled and distributed as
Android APKs. A detailed tutorial and example source code will be included
here at a later point. Until then you can use the `Sideband source code <https://github.com/markqvist/sideband>`_ as an example and starting point.


ARM64
^^^^^^^^^^^^^^^^^^^^^^^^
On some architectures, including ARM64, not all dependencies have precompiled
binaries. On such systems, you may need to install ``python3-dev`` (or similar) before
installing Reticulum or programs that depend on Reticulum.

.. code:: shell

   # Install Python and development packages
   sudo apt update
   sudo apt install python3 python3-pip python3-dev

   # Install Reticulum
   python3 -m pip install rns

With these packages installed, ``pip`` will be able to build any missing dependencies
on your system locally.


Debian Bookworm
^^^^^^^^^^^^^^^^^^^^^^^^
On versions of Debian released after April 2023, it is no longer possible by default
to use ``pip`` to install packages onto your system. Unfortunately, you will need to
use the replacement ``pipx`` command instead, which places installed packages in an
isolated environment. This should not negatively affect Reticulum, but will not work
for including and using Reticulum in your own scripts and programs.

.. code:: shell

    # Install pipx
    sudo apt install pipx

    # Make installed programs available on the command line
    pipx ensurepath

    # Install Reticulum
    pipx install rns

Alternatively, you can restore normal behaviour to ``pip`` by creating or editing
the configuration file located at ``~/.config/pip/pip.conf``, and adding the
following section:

.. code:: ini

    [global]
    break-system-packages = true

For a one-shot installation of Reticulum, without globally enabling the ``break-system-packages``
option, you can use the following command:

.. code:: shell

    pip install rns --break-system-packages

.. note::
   The ``--break-system-packages`` directive is a somewhat misleading choice
   of words. Setting it will of course not break any system packages, but will simply
   allow installing ``pip`` packages user- and system-wide. While this *could* in rare
   cases lead to version conflicts, it does not generally pose any problems, especially
   not in the case of installing Reticulum.


MacOS
^^^^^^^^^^^^^^^^^^^^^^^^^
To install Reticulum on macOS, you will need to have Python and the ``pip`` package
manager installed.

Systems running macOS can vary quite widely in whether or not Python is pre-installed,
and if it is, which version is installed, and whether the ``pip`` package manager is
also installed and set up. If in doubt, you can `download and install <https://www.python.org/downloads/>`_
Python manually.

When Python and ``pip`` is available on your system, simply open a terminal window
and use one of the following commands:

.. code:: shell

   # Install Reticulum and utilities with pip:
   pip3 install rns
   
   # On some versions, you may need to use the
   # flag --break-system-packages to install:
   pip3 install rns --break-system-packages

.. note::
   The ``--break-system-packages`` directive is a somewhat misleading choice
   of words. Setting it will of course not break any system packages, but will simply
   allow installing ``pip`` packages user- and system-wide. While this *could* in rare
   cases lead to version conflicts, it does not generally pose any problems, especially
   not in the case of installing Reticulum.

Additionally, some version combinations of macOS and Python require you to
manually add your installed ``pip`` packages directory to your `PATH` environment
variable, before you can use installed commands in your terminal. Usually, adding
the following line to your shell init script (for example ``~/.zshrc``) will be enough:

.. code:: shell

   export PATH=$PATH:~/Library/Python/3.9/bin

Adjust Python version and shell init script location according to your system.


OpenWRT
^^^^^^^^^^^^^^^^^^^^^^^^^
On OpenWRT systems with sufficient storage and memory, you can install
Reticulum and related utilities using the `opkg` package manager and `pip`.

.. note::

   At the time of releasing this manual, work is underway to create pre-built
   Reticulum packages for OpenWRT, with full configuration, service
   and ``uci`` integration. Please see the `feed-reticulum <https://github.com/gretel/feed-reticulum>`_
   and `reticulum-openwrt <https://github.com/gretel/reticulum-openwrt>`_
   repositories for more information.

To install Reticulum on OpenWRT, first log into a command line session, and
then use the following instructions:

.. code:: shell

   # Install dependencies
   opkg install python3 python3-pip python3-cryptography python3-pyserial
   
   # Install Reticulum
   pip install rns

   # Start rnsd with debug logging enabled
   rnsd -vvv

.. note::
   
   The above instructions have been verified and tested on OpenWRT 21.02 only.
   It is likely that other versions may require slightly altered installation
   commands or package names. You will also need enough free space in your
   overlay FS, and enough free RAM to actually run Reticulum and any related
   programs and utilities.

Depending on your device configuration, you may need to adjust firewall rules
for Reticulum connectivity to and from your device to work. Until proper
packaging is ready, you will also need to manually create a service or startup
script to automatically laucnh Reticulum at boot time.

Please also note that the `AutoInterface` requires link-local IPv6 addresses
to be enabled for any Ethernet and WiFi devices you intend to use. If ``ip a``
shows an address starting with ``fe80::`` for the device in question,
``AutoInterface`` should work for that device.

Raspberry Pi
^^^^^^^^^^^^^^^^^^^^^^^^^
It is currently recommended to use a 64-bit version of the Raspberry Pi OS
if you want to run Reticulum on Raspberry Pi computers, since 32-bit versions
don't always have packages available for some dependencies. If Python and the
`pip` package manager is not already installed, do that first, and then
install Reticulum using `pip`.

.. code:: shell

   # Install dependencies
   sudo apt install python3 python3-pip python3-cryptography python3-pyserial
   
   # Install Reticulum
   pip install rns --break-system-packages

.. note::
   The ``--break-system-packages`` directive is a somewhat misleading choice
   of words. Setting it will of course not break any system packages, but will simply
   allow installing ``pip`` packages user- and system-wide. While this *could* in rare
   cases lead to version conflicts, it does not generally pose any problems, especially
   not in the case of installing Reticulum.

While it is possible to install and run Reticulum on 32-bit Rasperry Pi OSes,
it will require manually configuring and installing required build dependencies,
and is not detailed in this manual.


RISC-V
^^^^^^^^^^^^^^^^^^^^^^^^
On some architectures, including RISC-V, not all dependencies have precompiled
binaries. On such systems, you may need to install ``python3-dev`` (or similar) before
installing Reticulum or programs that depend on Reticulum.

.. code:: shell

   # Install Python and development packages
   sudo apt update
   sudo apt install python3 python3-pip python3-dev

   # Install Reticulum
   python3 -m pip install rns

With these packages installed, ``pip`` will be able to build any missing dependencies
on your system locally.


Ubuntu Lunar
^^^^^^^^^^^^^^^^^^^^^^^^
On versions of Ubuntu released after April 2023, it is no longer possible by default
to use ``pip`` to install packages onto your system. Unfortunately, you will need to
use the replacement ``pipx`` command instead, which places installed packages in an
isolated environment. This should not negatively affect Reticulum, but will not work
for including and using Reticulum in your own scripts and programs.

.. code:: shell

    # Install pipx
    sudo apt install pipx

    # Make installed programs available on the command line
    pipx ensurepath

    # Install Reticulum
    pipx install rns

Alternatively, you can restore normal behaviour to ``pip`` by creating or editing
the configuration file located at ``~/.config/pip/pip.conf``, and adding the
following section:

.. code:: text

    [global]
    break-system-packages = true

For a one-shot installation of Reticulum, without globally enabling the ``break-system-packages``
option, you can use the following command:

.. code:: text

    pip install rns --break-system-packages

.. note::
   The ``--break-system-packages`` directive is a somewhat misleading choice
   of words. Setting it will of course not break any system packages, but will simply
   allow installing ``pip`` packages user- and system-wide. While this *could* in rare
   cases lead to version conflicts, it does not generally pose any problems, especially
   not in the case of installing Reticulum.

Windows
^^^^^^^^^^^^^^^^^^^^^^^^^
On Windows operating systems, the easiest way to install Reticulum is by using the
``pip`` package manager from the command line (either the command prompt or Windows
Powershell).

If you don't already have Python installed, `download and install Python <https://www.python.org/downloads/>`_.
At the time of publication of this manual, the recommended version is `Python 3.12.7 <https://www.python.org/downloads/release/python-3127>`_.

**Important!** When asked by the installer, make sure to add the Python program to
your PATH environment variables. If you don't do this, you will not be able to
use the ``pip`` installer, or run the included Reticulum utility programs (such as
``rnsd`` and ``rnstatus``) from the command line.

After installing Python, open the command prompt or Windows Powershell, and type:

.. code:: shell

   pip install rns

You can now use Reticulum and all included utility programs directly from your
preferred command line interface.

Pure-Python Reticulum
==============================================

.. warning::
   If you use the ``rnspure`` package to run Reticulum on systems that
   do not support `PyCA/cryptography <https://github.com/pyca/cryptography>`_, it is
   important that you read and understand the :ref:`Cryptographic Primitives <understanding-primitives>`
   section of this manual.

In some rare cases, and on more obscure system types, it is not possible to
install one or more dependencies. In such situations,
you can use the ``rnspure`` package instead of the ``rns`` package, or use ``pip``
with the ``--no-dependencies`` command-line option. The ``rnspure``
package requires no external dependencies for installation. Please note that the
actual contents of the ``rns`` and ``rnspure`` packages are *completely identical*.
The only difference is that the ``rnspure`` package lists no dependencies required
for installation.

No matter how Reticulum is installed and started, it will load external dependencies
only if they are *needed* and *available*. If for example you want to use Reticulum
on a system that cannot support ``pyserial``, it is perfectly possible to do so using
the `rnspure` package, but Reticulum will not be able to use serial-based interfaces.
All other available modules will still be loaded when needed.
