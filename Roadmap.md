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

- The current `0.8.x` release cycle aims at completing
  - [ ] Hot-pluggable interface system
  - [ ] External interface plugins
  - [ ] Network-wide path balancing and multi-pathing
  - [ ] Expanded hardware support
  - [ ] Overhauling and updating the documentation
  - [ ] Distributed Destination Naming System
  - [ ] A standalone RNS Daemon app for Android
  - [ ] Addding automatic retries to all use cases of the `Request` API
  - [ ] Performance and memory optimisations of the Python reference implementation
  - [ ] Fixing bugs discovered while operating Reticulum systems and applications

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
        - Update software descriptions and screenshots
    - Communications hardware section
        - Add information about RNode external displays.
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

- Add support for user-supplied external interface drivers
- Add interface hot-plug and live up/down control to running instances
- Add automatic retries to all use cases of the `Request` API
- Network-wide path balancing
- Distributed Destination Naming System
- Globally routable multicast
- Destination proxying
- [Metric-based path selection and multiple paths](https://github.com/markqvist/Reticulum/discussions/86)

### Usability & Utility
These effors seek to make Reticulum easier to use and operate, and to expand the utility of the stack on deployed systems.

- Easy way to share interface configurations, see [#19](https://github.com/markqvist/Reticulum/discussions/19)
- Transit traffic display in rnstatus
- rnsconfig utility

### Interfaceability
These efforts aim to expand the types of physical and virtual interfaces that Reticulum can natively use to transport data.

- Plain ESP32 devices (ESP-Now, WiFi, Bluetooth, etc.)
- More LoRa transceivers
- AT-compatible modems
- Filesystem interface
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
    - [x] Create a WebUSB-based bootstrapping utility, and integrate this directly into the [RNode Bootstrap Console](#), both on-device, and on an Internet-reachable copy. This will make it much easier to create new RNodes for average users.

## Release History

Please see the [Changelog](./Changelog.md) for a complete release history and changelog of Reticulum.