# Programs Using Reticulum

This chapter provides a non-exhaustive list of notable programs, systems and application-layer protocols that have been built using Reticulum.

Many different applications using Reticulum already exist, serving a wide variety of purposes from day-to-day communication and information sharing to systems administration and tackling advanced networking and communications challenges.

These programs will let you get a feel for how Reticulum works. Most of them have been designed to run well even over slow networks based on LoRa or packet radio, but all can also be used over fast links, such as local WiFi, wired Ethernet, the Internet, or any combination.

As such, it is easy to get started experimenting, without having to set up any radio transceivers or infrastructure just to try it out. Launching the programs on separate devices connected to the same WiFi network is enough to get started, and physical radio interfaces can then be added later.

Development of Reticulum-based applications and systems is ongoing, so consider this list a non-exhaustive starting point of *some* of the options available. With a bit of searching, primarily over Reticulum itself, you will find many more interesting things.

## Browsing & Publishing

In addition to the programs listed in this section, other Nomad Network clients include:

- [MeshChatX](https://meshchatx.com/)
- [Columba](https://github.com/torlando-tech/columba/)

### Nomad Network

The terminal-based program [Nomad Network](https://github.com/markqvist/nomadnet) provides a complete encrypted communications suite built with Reticulum.

It features encrypted LXMF messaging (both direct and delayed-delivery for offline users), file sharing, and has a built-in text-browser and page server with support for dynamically rendered pages, user authentication and more. It also includes an RRC client and a suite of network utilities.

### Ren Browser

[Ren Browser](https://github.com/Quad4-Software/Ren-Browser) is a modern, standalone browser for Nomad Network using the [Reticulum-Go](https://github.com/Quad4-Software/Reticulum-Go) implementation. The project is actively being developed, and should be considered alpha level software, but much of the functionality is already working. If you want to help expanding the ecosystem, this is an excellent project to take a look at.

Ren Browser is great example of an application aiming for true, seamless interoperability with the existing software ecosystem. It can operate fully standalone using it’s own embedded [Go implementation](https://github.com/Quad4-Software/Reticulum-Go) of Reticulum, or seamlessly utilise a shared RNS instance already running on the system.

### RNS Page Node

[RNS Page Node](https://github.com/Quad4-Software/rns-page-node) is a simple way to serve pages and files to any other Nomad Network compatible client. Drop-in replacement for NomadNet nodes that primarily serve pages and files.

### Retipedia

You can host the entirity of Wikipedia, StackExchange or any other `.zim` file, to Nomad Network clients using [Retipedia](https://github.com/RFnexus/Retipedia).

### Git Over Reticulum

The included [rngit](git.md#git-main) system provides a fully distributed solution for managing, hosting, collaborating on and interacting with Git repositories over Reticulum.

## Messaging & Voice

### Sideband

[Sideband](https://github.com/markqvist/Sideband) is a technical LXMF and LXST client, for Android, Linux, macOS and Windows. It also serves as a multi-purpose Reticulum utility, with features and functionality targeted at advanced users.

Sideband allows you to communicate with other people or LXMF-compatible systems over Reticulum networks using LoRa, Packet Radio, WiFi, I2P, Encrypted QR Paper Messages, or anything else Reticulum supports.

It interoperates with all other LXMF clients, and provides advanced features such as PTT and voice messaging, real-time voice calls, file attachments, private telemetry sharing, and a full plugin system for expandability.

### MeshChatX

[MeshChatX](https://meshchatx.com/) is an all-in-one Reticulum client with messaging, calling, and a NomadNet browser, providing everything you need for Reticulum, LXMF, and LXST in one beautiful and feature-rich application.

Features include full LXST support, custom voicemail, phonebook, contact sharing, ringtone support, multi-identity handling, modern UI/UX, offline documentation, expanded tools, page archiving, integrated maps, telemetry and improved application security.

### Columba

[Columba](https://github.com/torlando-tech/columba/) is a simple and familiar LXMF messaging app Android, built with a native Android interface and Material Design 3. It also includes LXST voice call functionality, and a mobile Nomad Network page browser.

### Ren TUI

[Ren TUI](https://github.com/Quad4-Software/Ren-TUI) is an early prototype terminal LXMF client for Reticulum built with Odin on librns (Reticulum-Go). It aims for NomadNet-like messaging/browsing without urwid or ncurses.

## Chat

### Reticulum Relay Chat

[Reticulum Relay Chat](https://rrc.kc1awv.net/) is a live chat system built on top of the Reticulum Network Stack. It exists to let people talk to each other in real time over Reticulum without dragging in message databases, synchronization engines, or architectural commitments they did not ask for.

RRC is closer in spirit to IRC than to modern “everything platforms.” You connect, you join a room, you talk, and then you leave. If you were present, you saw the conversation. If you were not, the conversation did not wait for you. This is not an accident. This is the entire design.

The [rrcd](https://github.com/kc1awv/rrcd) program provides a functional, reference RRC hub-server daemon implementation. RRC user clients include:

- [Nomad Network](https://github.com/markqvist/NomadNet/)
- [MeshChatX](https://meshchatx.com/)
- [Eridanus](https://github.com/torlando-tech/eridanus)
- [rrc-gui](https://github.com/kc1awv/rrc-gui)
- [rrc-web](https://github.com/kc1awv/rrc-web)

### RetiBBS

[RetiBBS](https://github.com/kc1awv/RetiBBS) is an old-school bulletin board system implementation for Reticulum networks.

RetiBBS allows users to communicate through message boards in a secure manner.

## Voice & Telephony

In addition to the programs listed in this section, other LXST voice clients include:

- [Sideband](https://github.com/markqvist/Sideband)
- [MeshChatX](https://meshchatx.com/)
- [Columba](https://github.com/torlando-tech/columba/)

### Reticulum Network Telephone

The `rnphone` program, included as part of the [LXST](https://github.com/markqvist/LXST) package is a command-line Reticulum telephone utility and daemon, that allows building physical, hardware telephones for LXST and Reticulum, as well as simply performing calls via the command line.

It supports interfacing directly with hardware peripherals such as GPIO keypads and LCD displays, providing a modular system for building secure hardware telephones.

### Partyline

[Partyline](https://github.com/RFnexus/partyline) is a group voice application for Reticulum, built on [LXST](https://github.com/markqvist/LXST), inspired by [Mumble](https://github.com/mumble-voip/mumble).

It provides both realtime group voice over any Reticulum transport capable of >6 kilobits per second, LXST dial-in support, listen-only music/broadcasting rooms, and many other useful functions.

### LXST Phone

The [LXST Phone](https://github.com/kc1awv/lxst_phone) program is a cross-platform desktop application for performing LXST voice calls over Reticulum. It supports various advanced features such as SAS verification, peer blocking, rate limiting, encrypted call history storage and contact management.

## System Administration

### Remote Shell

The included [rnsh](using.md#using-rnsh) program lets you establish fully interactive
remote shell sessions over Reticulum. It also allows you to pipe any program to or from a
remote system, and is similar to how `ssh` works. The `rnsh` program is very efficient, and
can facilitate fully interactive shell sessions, even over extremely low-bandwidth links,
such as LoRa or packet radio.

In addition to the default, fully interactive terminal mode, for extremely limited links,
`rnsh` offers line-interactive mode, allowing you to interact with remote systems, even
when link throughput is counted in a few hundreds of bits per second.

### RNS FileSync

The [RNS FileSync](https://github.com/Quad4-Software/RNS-Filesync) program enables automatic file synchronization between devices without requiring central servers, internet connectivity, or cloud services. It works over any network medium supported by Reticulum, including radio, LoRa, WiFi, or the internet, making it ideal for off-grid, privacy-focused, and resilient file sharing.

## Utilities & Components

### Modem73

[MODEM73](https://github.com/RFnexus/modem73) and its companion [Modem73Interface](https://github.com/RFnexus/modem73interface) is an open source software modem that works with any HF, VHF, or UHF radio capable of 2400 Hz of bandwidth. All you need is a sound card and audio cable for your radio.

### LXMFy

[LXMFy](https://lxmfy.quad4.io/) is a comprehensive and advanced bot creation framework for LXMF, that allows building any kind of automation or bot system running over LXMF and Reticulum. [Bot implementations exist](https://lxmfy.quad4.io/latest/creating-bots/) for Home Assistant control, LLM integrations, and various other purposes.

### Micron Parser JS

[Micron Parser JS](https://github.com/RFnexus/micron-parser-js) is the JavaScript-based parser for the Micron markup language, that most web-based Nomad Network browsers use. If you want to make utilities or tools that display Micron pages, this library is essential.

### Reticulated

[Reticulated](https://github.com/RFnexus/Reticulated) is a Reticulum Network simulator that spawns live, interactive Reticulum instances controllable from a node-based Web UI.

You can create networks of any topology and set bitrate, MTU, and configure path loss and propagation behavior. It provides a top-down view to a live network. You can connect any Reticulum application to the simulated network. It also has built in utilities like a basic LXMF chat function and Resource transfer included.

### RNMon

[RNMon](https://github.com/lbatalha/rnmon) is a monitoring daemon designed to monitor the status of multiple RNS applications and push the metrics to an InfluxDB instance over the influx line protocol.

## Device Flashers

In addition to the included command-line `rnodeconf` flasher, several community-provided RNode device flashers exist:

- [RNS Moscow](https://flasher.rns.moscow/)
- [Aetherlab](https://flasher.aetherlab.org/)

Several programs, such as [Sideband](https://github.com/markqvist/Sideband) and [MeshChatX](https://meshchatx.com/) also include built-in device flashers that can be used fully offline.

## Protocols

A number of standard protocols have emerged through real-world usage and testing in the Reticulum community. While you may sometimes want to use completely custom protocols and implementations when writing Reticulum-based software, using these protocols provides application developers with an easy way to implement advanced functionality quickly and effortlessly. Using them also ensures compatibility and interoperability between many different client applications, creating an open communications ecosystem where users are free to choose the applications that suit their needs, while remaining connected to everyone else.

### LXMF

[LXMF](https://github.com/markqvist/lxmf) is a simple and flexible messaging format and delivery protocol that allows a wide variety of applications, while using as little bandwidth as possible. It offers zero-conf message routing, end-to-end encryption and Forward Secrecy, and can be transported over any kind of medium that Reticulum supports.

LXMF is efficient enough that it can deliver messages over extremely low-bandwidth systems such as packet radio or LoRa. Encrypted LXMF messages can also be encoded as QR-codes or text-based URIs, allowing completely analog paper message transport.

Using Propagation Nodes, LXMF also offer a way to store and forward messages to users or endpoints that are not directly reachable at the time of message emission.

### LXST

[LXST](https://github.com/markqvist/lxst) is a simple and flexible real-time streaming format and delivery protocol that allows a wide variety of applications, while using as little bandwidth as possible. It is built on top of Reticulum and offers zero-conf stream routing, end-to-end encryption and Forward Secrecy, and can be transported over any kind of medium that Reticulum supports. It currently powers real-time voice and telephony applications over Reticulum.

### RRC

The [Reticulum Relay Chat](https://rrc.kc1awv.net/) protocol, is a live chat system built on top of the Reticulum Network Stack. It exists to provide near real-time group communication without dragging in message history databases, federation machinery, or architectural guilt.

RRC is intentionally simple. It does not pretend to be email, a mailbox, or a distributed archive. It behaves more like a conversation in a room. If you were there, you heard it. If you were not, you did not. That is not a bug, that is the point.

## Interface Modules & Connectivity Resources

This section provides a list of various community-provided interface modules, guides and resources for creating Reticulum networks over special or challenging mediums.

* [Modem73](https://github.com/RFnexus/modem73) is an efficient software modem that can be used with Reticulum
* Custom interface module for running [RNS over HTTP](https://github.com/Quad4-Software/RNS-over-HTTP)
* Guide for running [Reticulum over ICMP](https://github.com/matvik22000/rns-over-icmp) using `PipeInterface`
* Guide for running [Reticulum over DNS](https://github.com/markqvist/Reticulum/discussions/1002) with Iodine
* Guide for running [Reticulum over HF radio](https://github.com/RFnexus/reticulum-over-hf)