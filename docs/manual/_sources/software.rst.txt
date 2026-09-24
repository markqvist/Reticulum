.. _software-main:

************************
Programs Using Reticulum
************************

This chapter provides a non-exhaustive list of notable programs, systems and application-layer protocols that have been built using Reticulum.

Many different applications using Reticulum already exist, serving a wide variety of purposes from day-to-day communication and information sharing to systems administration and tackling advanced networking and communications challenges.

.. tip::
   For ease of discovery while reading this manual over the web or as an e-book, links provided in this chapter primarily point to repositories and pages located on internet servers. In many cases, these are public web mirrors, with the upstream repositories residing on Reticulum nodes. For the latest source, updates and information regarding any project, be sure to check their Nomad Network or ``rngit`` nodes.

These programs will let you get a feel for how Reticulum works. Most of them have been designed to run well even over slow networks based on LoRa or packet radio, but all can also be used over fast links, such as local WiFi, wired Ethernet, the Internet, or any combination.

As such, it is easy to get started experimenting, without having to set up any radio transceivers or infrastructure just to try it out. Launching the programs on separate devices connected to the same WiFi network is enough to get started, and physical radio interfaces can then be added later.

Development of Reticulum-based applications and systems is ongoing, so consider this list a non-exhaustive starting point of *some* of the options available. With a bit of searching, primarily over Reticulum itself, you will find many more interesting things.

Browsing & Publishing
=====================

In addition to the programs listed in this section, other Nomad Network clients include:

- `MeshChatX <https://meshchatx.com/>`_
- `Columba <https://github.com/torlando-tech/columba/>`_

Nomad Network
^^^^^^^^^^^^^

The terminal-based program `Nomad Network <https://github.com/markqvist/nomadnet>`_ provides a complete encrypted communications suite built with Reticulum.

.. only:: html

  .. image:: screenshots/nomadnet_6.webp
      :align: center
      :target: https://github.com/markqvist/nomadnet

.. only:: latex

  .. image:: screenshots/nomadnet_6.png
      :align: center
      :target: https://github.com/markqvist/nomadnet

It features encrypted LXMF messaging (both direct and delayed-delivery for offline users), file sharing, and has a built-in text-browser and page server with support for dynamically rendered pages, user authentication and more. It also includes an RRC client and a suite of network utilities.


Ren Browser
^^^^^^^^^^^

`Ren Browser <https://github.com/Quad4-Software/Ren-Browser>`_ is a modern, standalone browser for Nomad Network using the `Reticulum-Go <https://github.com/Quad4-Software/Reticulum-Go>`_ implementation. The project is actively being developed, and should be considered alpha level software, but much of the functionality is already working. If you want to help expanding the ecosystem, this is an excellent project to take a look at.

.. only:: html

  .. image:: screenshots/ren_browser.webp
      :align: center
      :target: https://github.com/fr33n0w/rBrowser

.. only:: latex

  .. image:: screenshots/ren_browser.png
      :align: center
      :target: https://github.com/fr33n0w/rBrowser

Ren Browser is great example of an application aiming for true, seamless interoperability with the existing software ecosystem. It can operate fully standalone using it's own embedded `Go implementation <https://github.com/Quad4-Software/Reticulum-Go>`_ of Reticulum, or seamlessly utilise a shared RNS instance already running on the system.

RNS Page Node
^^^^^^^^^^^^^

`RNS Page Node <https://github.com/Quad4-Software/rns-page-node>`_ is a simple way to serve pages and files to any other Nomad Network compatible client. Drop-in replacement for NomadNet nodes that primarily serve pages and files.


Retipedia
^^^^^^^^^

You can host the entirity of Wikipedia, StackExchange or any other ``.zim`` file, to Nomad Network clients using `Retipedia <https://github.com/RFnexus/Retipedia>`_.

.. only:: html

  .. image:: screenshots/retipedia.webp
      :align: center
      :target: https://github.com/RFnexus/Retipedia

.. only:: latex

  .. image:: screenshots/retipedia.png
      :align: center
      :target: https://github.com/RFnexus/Retipedia


Git Over Reticulum
^^^^^^^^^^^^^^^^^^

The included :ref:`rngit<git-main>` system provides a fully distributed solution for managing, hosting, collaborating on and interacting with Git repositories over Reticulum.

.. only:: html

  .. image:: screenshots/rngit.webp
      :align: center

.. only:: latex

  .. image:: screenshots/rngit.png
      :align: center


.. raw:: latex

    \newpage

Messaging & Voice
=================

Sideband
^^^^^^^^

`Sideband <https://github.com/markqvist/Sideband>`_ is a technical LXMF and LXST client, for Android, Linux, macOS and Windows. It also serves as a multi-purpose Reticulum utility, with features and functionality targeted at advanced users.

.. only:: html

  .. image:: screenshots/sideband_devices.webp
      :align: center
      :target: https://github.com/markqvist/Sideband

.. only:: latex

  .. image:: screenshots/sideband_devices.png
      :align: center
      :target: https://github.com/markqvist/Sideband

Sideband allows you to communicate with other people or LXMF-compatible systems over Reticulum networks using LoRa, Packet Radio, WiFi, I2P, Encrypted QR Paper Messages, or anything else Reticulum supports.

It interoperates with all other LXMF clients, and provides advanced features such as PTT and voice messaging, real-time voice calls, file attachments, private telemetry sharing, and a full plugin system for expandability.

.. raw:: latex

    \newpage

MeshChatX
^^^^^^^^^

`MeshChatX <https://meshchatx.com/>`_ is an all-in-one Reticulum client with messaging, calling, and a NomadNet browser, providing everything you need for Reticulum, LXMF, and LXST in one beautiful and feature-rich application.

.. only:: html

  .. image:: screenshots/meshchatx.webp
      :align: center
      :target: https://meshchatx.com/

.. only:: latex

  .. image:: screenshots/meshchatx.png
      :align: center
      :target: https://meshchatx.com/


Features include full LXST support, custom voicemail, phonebook, contact sharing, ringtone support, multi-identity handling, modern UI/UX, offline documentation, expanded tools, page archiving, integrated maps, telemetry and improved application security.

Columba
^^^^^^^

`Columba <https://github.com/torlando-tech/columba/>`_ is a simple and familiar LXMF messaging app Android, built with a native Android interface and Material Design 3. It also includes LXST voice call functionality, and a mobile Nomad Network page browser.

.. only:: html

  .. image:: screenshots/columba.webp
      :align: center
      :target: https://github.com/torlando-tech/columba/

.. only:: latex

  .. image:: screenshots/columba.png
      :align: center
      :target: https://github.com/torlando-tech/columba/


Ren TUI
^^^^^^^

`Ren TUI <https://github.com/Quad4-Software/Ren-TUI>`_ is an early prototype terminal LXMF client for Reticulum built with Odin on librns (Reticulum-Go). It aims for NomadNet-like messaging/browsing without urwid or ncurses.

.. only:: html

  .. image:: screenshots/rentui.webp
      :align: center
      :target: https://github.com/Quad4-Software/Ren-TUI

.. only:: latex

  .. image:: screenshots/rentui.png
      :align: center
      :target: https://github.com/Quad4-Software/Ren-TUI

Chat
====

Reticulum Relay Chat
^^^^^^^^^^^^^^^^^^^^

`Reticulum Relay Chat <https://rrc.kc1awv.net/>`_ is a live chat system built on top of the Reticulum Network Stack. It exists to let people talk to each other in real time over Reticulum without dragging in message databases, synchronization engines, or architectural commitments they did not ask for.

.. only:: html

  .. image:: screenshots/rrc.webp
      :align: center

.. only:: latex

  .. image:: screenshots/rrc.png
      :align: center

RRC is closer in spirit to IRC than to modern “everything platforms.” You connect, you join a room, you talk, and then you leave. If you were present, you saw the conversation. If you were not, the conversation did not wait for you. This is not an accident. This is the entire design.

The `rrcd <https://github.com/kc1awv/rrcd>`_ program provides a functional, reference RRC hub-server daemon implementation. RRC user clients include:

- `Nomad Network <https://github.com/markqvist/NomadNet/>`_
- `MeshChatX <https://meshchatx.com/>`_
- `Eridanus <https://github.com/torlando-tech/eridanus>`_
- `rrc-gui <https://github.com/kc1awv/rrc-gui>`_
- `rrc-web <https://github.com/kc1awv/rrc-web>`_

RetiBBS
^^^^^^^

`RetiBBS <https://github.com/kc1awv/RetiBBS>`_ is an old-school bulletin board system implementation for Reticulum networks.

.. only:: html

  .. image:: screenshots/retibbs.webp
      :align: center
      :target: https://github.com/kc1awv/RetiBBS

.. only:: latex

  .. image:: screenshots/retibbs.png
      :align: center
      :target: https://github.com/kc1awv/RetiBBS

RetiBBS allows users to communicate through message boards in a secure manner.

.. raw:: latex

    \newpage

Voice & Telephony
=================

In addition to the programs listed in this section, other LXST voice clients include:

- `Sideband <https://github.com/markqvist/Sideband>`_
- `MeshChatX <https://meshchatx.com/>`_
- `Columba <https://github.com/torlando-tech/columba/>`_

Reticulum Network Telephone
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``rnphone`` program, included as part of the `LXST <https://github.com/markqvist/LXST>`_ package is a command-line Reticulum telephone utility and daemon, that allows building physical, hardware telephones for LXST and Reticulum, as well as simply performing calls via the command line.

.. only:: html

  .. image:: screenshots/rnphone.webp
      :align: center
      :target: https://github.com/markqvist/LXST

.. only:: latex

  .. image:: screenshots/rnphone.jpg
      :align: center
      :target: https://github.com/markqvist/LXST

It supports interfacing directly with hardware peripherals such as GPIO keypads and LCD displays, providing a modular system for building secure hardware telephones.


Partyline
^^^^^^^^^

`Partyline <https://github.com/RFnexus/partyline>`_ is a group voice application for Reticulum, built on `LXST <https://github.com/markqvist/LXST>`_, inspired by `Mumble <https://github.com/mumble-voip/mumble>`_.

.. only:: html

  .. image:: screenshots/partyline.webp
      :align: center
      :target: https://github.com/markqvist/LXST

.. only:: latex

  .. image:: screenshots/partyline.png
      :align: center
      :target: https://github.com/markqvist/LXST

It provides both realtime group voice over any Reticulum transport capable of >6 kilobits per second, LXST dial-in support, listen-only music/broadcasting rooms, and many other useful functions.


LXST Phone
^^^^^^^^^^

The `LXST Phone <https://github.com/kc1awv/lxst_phone>`_ program is a cross-platform desktop application for performing LXST voice calls over Reticulum. It supports various advanced features such as SAS verification, peer blocking, rate limiting, encrypted call history storage and contact management.

.. only:: html

  .. image:: screenshots/lxst_phone.webp
      :align: center
      :target: https://github.com/kc1awv/lxst_phone

.. only:: latex

  .. image:: screenshots/lxst_phone.png
      :align: center
      :target: https://github.com/kc1awv/lxst_phone


.. raw:: latex

    \newpage

System Administration
=====================

Remote Shell
^^^^^^^^^^^^

The included :ref:`rnsh<using-rnsh>` program lets you establish fully interactive
remote shell sessions over Reticulum. It also allows you to pipe any program to or from a
remote system, and is similar to how ``ssh`` works. The ``rnsh`` program is very efficient, and
can facilitate fully interactive shell sessions, even over extremely low-bandwidth links,
such as LoRa or packet radio.

In addition to the default, fully interactive terminal mode, for extremely limited links,
``rnsh`` offers line-interactive mode, allowing you to interact with remote systems, even
when link throughput is counted in a few hundreds of bits per second.

RNS FileSync
^^^^^^^^^^^^

The `RNS FileSync <https://github.com/Quad4-Software/RNS-Filesync>`_ program enables automatic file synchronization between devices without requiring central servers, internet connectivity, or cloud services. It works over any network medium supported by Reticulum, including radio, LoRa, WiFi, or the internet, making it ideal for off-grid, privacy-focused, and resilient file sharing.

.. raw:: latex

    \newpage

Utilities & Components
======================

Modem73
^^^^^^^

`MODEM73 <https://github.com/RFnexus/modem73>`_ and its companion `Modem73Interface <https://github.com/RFnexus/modem73interface>`_ is an open source software modem that works with any HF, VHF, or UHF radio capable of 2400 Hz of bandwidth. All you need is a sound card and audio cable for your radio.

.. only:: html

  .. image:: screenshots/modem73.webp
      :align: center
      :target: https://github.com/RFnexus/modem73

.. only:: latex

  .. image:: screenshots/modem73.jpg
      :align: center
      :target: https://github.com/RFnexus/modem73

LXMFy
^^^^^

`LXMFy <https://lxmfy.quad4.io/>`_ is a comprehensive and advanced bot creation framework for LXMF, that allows building any kind of automation or bot system running over LXMF and Reticulum. `Bot implementations exist <https://lxmfy.quad4.io/latest/creating-bots/>`_ for Home Assistant control, LLM integrations, and various other purposes.


Micron Parser JS
^^^^^^^^^^^^^^^^

`Micron Parser JS <https://github.com/RFnexus/micron-parser-js>`_ is the JavaScript-based parser for the Micron markup language, that most web-based Nomad Network browsers use. If you want to make utilities or tools that display Micron pages, this library is essential.

Reticulated
^^^^^^^^^^^

`Reticulated <https://github.com/RFnexus/Reticulated>`_ is a Reticulum Network simulator that spawns live, interactive Reticulum instances controllable from a node-based Web UI.

.. only:: html

  .. image:: screenshots/reticulated.webp
      :align: center
      :target: https://github.com/RFnexus/Reticulated

.. only:: latex

  .. image:: screenshots/reticulated.jpg
      :align: center
      :target: https://github.com/RFnexus/Reticulated

You can create networks of any topology and set bitrate, MTU, and configure path loss and propagation behavior. It provides a top-down view to a live network. You can connect any Reticulum application to the simulated network. It also has built in utilities like a basic LXMF chat function and Resource transfer included.


RNMon
^^^^^

`RNMon <https://github.com/lbatalha/rnmon>`_ is a monitoring daemon designed to monitor the status of multiple RNS applications and push the metrics to an InfluxDB instance over the influx line protocol.


.. raw:: latex

    \newpage

Device Flashers
===============

In addition to the included command-line ``rnodeconf`` flasher, several community-provided RNode device flashers exist:

- `RNS Moscow <https://flasher.rns.moscow/>`_
- `Aetherlab <https://flasher.aetherlab.org/>`_

Several programs, such as `Sideband <https://github.com/markqvist/Sideband>`_ and `MeshChatX <https://meshchatx.com/>`_ also include built-in device flashers that can be used fully offline.

Protocols
=========

A number of standard protocols have emerged through real-world usage and testing in the Reticulum community. While you may sometimes want to use completely custom protocols and implementations when writing Reticulum-based software, using these protocols provides application developers with an easy way to implement advanced functionality quickly and effortlessly. Using them also ensures compatibility and interoperability between many different client applications, creating an open communications ecosystem where users are free to choose the applications that suit their needs, while remaining connected to everyone else.

LXMF
^^^^

`LXMF <https://github.com/markqvist/lxmf>`_ is a simple and flexible messaging format and delivery protocol that allows a wide variety of applications, while using as little bandwidth as possible. It offers zero-conf message routing, end-to-end encryption and Forward Secrecy, and can be transported over any kind of medium that Reticulum supports.

LXMF is efficient enough that it can deliver messages over extremely low-bandwidth systems such as packet radio or LoRa. Encrypted LXMF messages can also be encoded as QR-codes or text-based URIs, allowing completely analog paper message transport.

Using Propagation Nodes, LXMF also offer a way to store and forward messages to users or endpoints that are not directly reachable at the time of message emission.

LXST
^^^^

`LXST <https://github.com/markqvist/lxst>`_ is a simple and flexible real-time streaming format and delivery protocol that allows a wide variety of applications, while using as little bandwidth as possible. It is built on top of Reticulum and offers zero-conf stream routing, end-to-end encryption and Forward Secrecy, and can be transported over any kind of medium that Reticulum supports. It currently powers real-time voice and telephony applications over Reticulum.

RRC
^^^

The `Reticulum Relay Chat <https://rrc.kc1awv.net/>`_ protocol, is a live chat system built on top of the Reticulum Network Stack. It exists to provide near real-time group communication without dragging in message history databases, federation machinery, or architectural guilt.

RRC is intentionally simple. It does not pretend to be email, a mailbox, or a distributed archive. It behaves more like a conversation in a room. If you were there, you heard it. If you were not, you did not. That is not a bug, that is the point.

Interface Modules & Connectivity Resources
==========================================

This section provides a list of various community-provided interface modules, guides and resources for creating Reticulum networks over special or challenging mediums.

* `Modem73 <https://github.com/RFnexus/modem73>`_ is an efficient software modem that can be used with Reticulum
* Custom interface module for running `RNS over HTTP <https://github.com/Quad4-Software/RNS-over-HTTP>`_
* Guide for running `Reticulum over ICMP <https://github.com/matvik22000/rns-over-icmp>`_ using ``PipeInterface``
* Guide for running `Reticulum over DNS <https://github.com/markqvist/Reticulum/discussions/1002>`_ with Iodine
* Guide for running `Reticulum over HF radio <https://github.com/RFnexus/reticulum-over-hf>`_