# Reticulum Development Roadmap
This document outlines the currently established development roadmap for Reticulum.

1. [Currently Active Work Areas](#currently-active-work-areas)
2. [Primary Efforts](#primary-efforts)
    - [Comprehensibility](#comprehensibility)
    - [Universality](#universality)
    - [Functionality](#functionality)
    - [Usability & Utility](#usability--utility)
    - [Interfaceability](#interfaceability)
3. [Auxillary Efforts](#auxillary-efforts)
4. [Release History](#release-history)

## Currently Active Work Areas
For each release cycle of Reticulum, improvements and additions from the five [Primary Efforts](#primary-efforts) are selected as active work areas, and can be expected to be included in the upcoming releases within that cycle. While not entirely set in stone for each release cycle, they serve as a pointer of what to expect in the near future.

- The current `0.4.x` release cycle aims at completing:
  - [x] Improve storage persist call on local client connect/disconnect
  - [x] Better path invalidation on roaming interfaces
  - [x] Improved roaming support on Android
  - [x] Add bluetooth pairing code output to rnodeconf
  - [x] Add `rnid` utility with encryption, signing and Identity funcionality
  - [x] JSON output mode for rnstatus
  - [x] Add `Buffer` class to the API
- Targets for related applications
  - [x] Add offline & paper message transport to LXMF
  - [x] Implement paper messaging in Nomad Network
  - [x] Implement paper messaging in Sideband
  - [x] Add spatial and multi-interface roaming support in Sideband
  - [x] Expand device support in Sideband to support older Android devices
  - [x] And input fields, data submission and dynamic request links to Nomad Network
  - [x] Add bandwidth-based weighting to LXMF propagation node sync peer prioritisation
- The upcoming `0.5.x` release cyclo aims at completing
  - [ ] Updating the documentation to reflect recent changes and improvements
  - [ ] Add automatic retries to all use cases of the `Request` API
  - [ ] Improve performance and efficiency of the `Buffer` and `Channel` API
  - [ ] Performance and memory optimisations of the Python reference implementation

## Primary Efforts
The development path for Reticulum is currently laid out in five distinct areas: *Comprehensibility*, *Universality*, *Functionality*, *Usability & Utility* and *Interfaceability*. Conceptualising the development of Reticulum into these areas serves to advance the implementation and work towards the Foundational Goals & Values of Reticulum.

### Comprehensibility
These efforts are aimed at improving the ease of which Reticulum is understood, and lowering the barrier to entry for people who wish to start building systems on Reticulum.

- Improving [the manual](https://markqvist.github.io/Reticulum/manual/) with tutorials specifically for beginners
- Updating the documentation to reflect recent changes and improvements
    - Update descriptions of protocol mechanics
        - Update announce description
        - Add in-depth explanation of the IFAC system
    - Software
        - Update Sideband screenshots
        - Update Sideband description
        - Update NomadNet screenshots
        - Update Sideband screenshots
    - Installation
        - Install docs for fedora, needs `python3-netifaces`
        - Add a *Reticulum On Raspberry Pi* section
        - Update *Reticulum On Android* section if necessary
        - Update Android install documentation.
    - Communications hardware section
        - Add information about RNode external displays.
        - Packet radio modems.
        - Possibly add other relevant types here as well.
    - Setup *Best Practices For...* / *Installation Examples* section.
        - Home or office (example)
        - Vehicles (example)
        - No-grid/solar/remote sites (example)

### Universality
These efforts seek to broaden the universality of the Reticulum software and hardware ecosystem by continously diversifying platform support, and by improving the overall availability and ease of deployment of the Reticulum stack.

- OpenWRT support
- Create a standalone RNS Daemon app for Android
- A lightweight and portable C implementation for microcontrollers, µRNS
- A portable, high-performance Reticulum implementation in C/C++, see [#21](https://github.com/markqvist/Reticulum/discussions/21)
- Performance and memory optimisations of the Python implementation
- Bindings for other programming languages

### Functionality
These efforts aim to expand and improve the core functionality and reliability of Reticulum.

- Add automatic retries to all use cases of the `Request` API
- Network-wide path balancing
- Distributed Destination Naming System
- Globally routable multicast
- Destination proxying
- [Metric-based path selection and multiple paths](https://github.com/markqvist/Reticulum/discussions/86)

### Usability & Utility
These effors seek to make Reticulum easier to use and operate, and to expand the utility of the stack on deployed systems.

- Add bluetooth pairing code output to rnodeconf
- Easy way to share interface configurations, see [#19](https://github.com/markqvist/Reticulum/discussions/19)
- Transit traffic display in rnstatus
- rnsconfig utility

### Interfaceability
These efforts aim to expand the types of physical and virtual interfaces that Reticulum can natively use to transport data.

- Filesystem interface
- Plain ESP32 devices (ESP-Now, WiFi, Bluetooth, etc.)
- More LoRa transceivers
- AT-compatible modems
- Direct SDR Support
- Optical mediums
- IR Transceivers
- AWDL / OWL
- HF Modems
- GNU Radio
- CAN-bus
- Raw SPI
- Raw i²c
- MQTT
- XBee
- Tor

## Auxillary Efforts
The Reticulum ecosystem is enriched by several other software and hardware projects, and the support and improvement of these, in symbiosis with the core Reticulum project helps expand the reach and utility of Reticulum itself.

This section lists, in no particular order, various important efforts that would be beneficial to the goals of Reticulum.

- The [RNode](https://unsigned.io/rnode/) project
    - [x] Evolve RNode into a self-replicating system, so that anyone can use an existing RNode to create more RNodes, and bootstrap functional networks based on Reticulum, even in absence of the Internet.
    - [ ] Create a WebUSB-based bootstrapping utility, and integrate this directly into the [RNode Bootstrap Console](#), both on-device, and on an Internet-reachable copy. This will make it much easier to create new RNodes for average users.

## Release History

Please see the [Changelog](./Changelog.md) for a complete release history and changelog of Reticulum.