# Reticulum Development Roadmap
This document outlines the currently established development roadmap for Reticulum.

1. [Currently Active Work Areas](#currently-active-work-areas)
2. [Primary Efforts](#primary-efforts)
    - [Comprehensibility](#comprehensibility)
    - [Universality](#universality)
    - [Functionality](#functionality)
    - [Usability & Utility](#usability-utility)
    - [Interfaceability](#interfaceability)
3. [Release History](#release-history)

## Currently Active Work Areas
For each release cycle of Reticulum, improvements and additions from the five [Primary Efforts](#primary-efforts) are selected as active work areas, and can be expected to be included in the upcoming releases within that cycle. While not entirely set in stone for each release cycle, they serve as a pointer of what to expect in the near future.

- The current `0.4.x` release cycle aims at completing:
  - [x] Improve storage persist call on local client connect/disconnect
  - [x] Improved roaming support on Android
  - [ ] Updating the documentation to reflect recent changes and improvements
  - [ ] Add bluetooth pairing code output to rnodeconf
  - [ ] Improve storage persist call on every local client connect/disconnect
  - [ ] Transit traffic display in rnstatus
  - [ ] JSON output mode for rnstatus
  - [ ] Add `rnid` utility
  - [ ] Add `rnsign` utility
  - [ ] Add `rncrypt` utility
  - [ ] Create a standalone RNS Daemon app for Android
- Targets for related applications
  - [x] Add paper offline & paper message transport to LXMF
  - [x] Implement paper messaging in Nomad Network
  - [x] Implement paper messaging in Sideband
  - [x] Expand device support in Sideband to support older Android devices

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

- Improved roaming support on Android
- OpenWRT support
- Create a standalone RNS Daemon app for Android
- A lightweight and portable C implementation for microcontrollers, µRNS
- A portable, high-performance Reticulum implementation in C/C++, see [#21](https://github.com/markqvist/Reticulum/discussions/21)
- Performance and memory optimisations of the Python implementation
- Bindings for other programming languages

### Functionality
These efforts aim to expand and improve the core functionality and reliability of Reticulum.

- Improve storage persist call on local client connect/disconnect
- Faster path invalidation on physical topography changes
- Better path invalidation on roaming interfaces
- Network-wide path balancing
- Distributed Destination Naming System
- Globally routable multicast
- Destination proxying: Create a new random destination, and sign it with the original destination to create verifiable ephemeral destinations. This could actually be a very powerful feature for aggregating routes in the network, and it retains destination owners control over how they are routed
- [Metric-based path selection and multiple paths](https://github.com/markqvist/Reticulum/discussions/86)

### Usability & Utility
These effors seek to make Reticulum easier to use and operate, and to expand the utility of the stack on deployed systems.

- Add bluetooth pairing code output to rnodeconf
- Easy way to share interface configurations, see [#19](https://github.com/markqvist/Reticulum/discussions/19)
- Transit traffic display in rnstatus
- JSON output mode for rnstatus
- rnid utility
- rnsign utility
- rncrypt utility
- rnsconfig utility
- Expand rnx utility to true interactive remote shell

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

## Release History

This section contains the complete release log for Reticulum.

### 2022-12-23: RNS β 0.4.6

This maintenance release brings two bugfixes.

**Changes**
- Fixed missing path invalidation on failed link establishments made from a shared instance client
- Fixed a memory leak in link handling

**Release Hashes**
```
7f1b0b254dce5bb1bacc336b026dab2dda5859b43cb0f4ceed3f70ba825f8873 rns-0.4.6-py3-none-any.whl
775c1b9b5bdf202524e50e58dc7c7bad9262ca3c16471cbfc6fb3a528e732460 rnspure-0.4.6-py3-none-any.whl
```

### 2022-12-22: RNS β 0.4.5

This maintenance release significantly improves path rediscovery on roaming devices with multiple interfaces, and adds a few tweaks to interface handling, that are especially relevant on Android.

**Changes**
- Faster roaming path recovery for multiple interface non-transport instances
- Fixed AutoInterface multicast echoes failing on interfaces with rolling MAC addresses on every re-connect
- Added carrier change detection flag to AutoInterface
- Adjusted loglevels for some items

**Release Hashes**
```
6757d5d815d4d96c45c181daf321447914c0e90892d43e142f2bd3fffacda9d9 rns-0.4.5-py3-none-any.whl
11669065091d67e3abaddb0096e5c92fc48080692b5644559226b2e2e6721060 rnspure-0.4.5-py3-none-any.whl
```

### 2022-12-22: RNS β 0.4.4

This maintenance release improves path response handling and log output.

**Release Hashes**
```
b0b59c25910151db0c2085d812bcc3d06cb930ddb8cd1e281b40cb592c1427eb rns-0.4.4-py3-none-any.whl
fe29ce3eb9e55f6953312c8db8c350bd58a7777e8c8dffd5491b840254426332 rnspure-0.4.4-py3-none-any.whl
```

### 2022-12-22: RNS β 0.4.3

This maintenance release brings faster path rediscovery and improves hardware support on Android, along with a few other minor tweaks and bugfixes.

**Changes**
- Added automatic path rediscovery on failed link establishments
- Added signature validation for link request proof packets for every transport hop
- Improved RNode hotplug support over Bluetooth on Android
- Improved Resource transfer sequencing and retry handling
- Fixed driver initialisation for Qinheng CH34x serial chips on Android
- Updates to documentation

**Release Hashes**
```
c035c2e21b8b207b00937ad57e947c7b4f17a02fe4f253d6e1fcc000479019b7 rns-0.4.3-py3-none-any.whl
e367576893bada72329ad195ebaa1e295bbca8897241f258428e1957d2da9a55 rnspure-0.4.3-py3-none-any.whl
```

### 2022-11-24: RNS β 0.4.2

This maintenance release brings a number of minor improvements, and fixes a few bugs related to hardware support on Android.

**Changes**
- Fixed AutoInterface roaming not working on Android devices that rotate Ethernet and WiFi MAC addresses on every physical connection change
- Fixed RNode interface not working over Bluetooth on Android versions 10 and below
- Greatly improved startup time for programs connecting to a shared Reticulum instance on slow or resource-limited systems
- Improvements to internal utility-functions and logging
- Added a public development roadmap
- Updates and fixes to the documentation

**Release Hashes**
```
ba541ead4194e7ae3e295bf2c84b609041e4dc82e1b5bfce0885396ee090e37f rns-0.4.2-py3-none-any.whl
a352cb8d0862a1a23e66bda08357bf7e725b540bbdd3bb3b32914f3c0bb99a05 rnspure-0.4.2-py3-none-any.whl
```

### 2022-11-03: RNS β 0.4.1

This maintenance release fixes few bugs, and improves I2P interface recovery on unresponsive I2P tunnels.

**Changes**
- Added better I2P tunnel state visibility to rnstatus util
- Improved I2P recovery time on unresponsive tunnels
- Improved I2P tunnel state detection
- Fixed missing IFAC identity init on spawned TCP clients
- Fixed missing IFAC identity init on spawned I2P interfaces
- Fixed missing check for socket state on I2P interfaces

**Release Hashes**
```
e28643a7396c3a41d859eb7d3a14f166e648003da36fc49094561fbf49c04b7e rns-0.4.1-py3-none-any.whl
feaa326545c928f3d5dc7b6fdb31975517af15da0751927491c4ac23dac36edc rnspure-0.4.1-py3-none-any.whl
```

### 2022-11-03: RNS β 0.4.0

This maintenance release fixes minor bug in the rnodeconf utility.

**Changes**
- Fixed incorrect storage location for local firmware cache in the rnodeconf utility

**Release Hashes**
```
16dda7b087cff0c21b7b0460798cb433fc96f27d058eb7d50e38898a1a1e49c4 rns-0.4.0-py3-none-any.whl
5f137cfd42ee9d9e7ae43b25d25849bd087145b7edf2c29ffdfd93d57ab34284 rnspure-0.4.0-py3-none-any.whl
```

### 2022-11-03: RNS β 0.3.19

This release adds support for Bluetooth-connected RNode interfaces, and includes a few improvements to the rnodeconf utility.

**Changes**
- Added support for RNode interfaces connected over Bluetooth on Linux and Android
- Improved rnodeconf install and update timing, which fixes installs sometimes failing on T-Beam devices

**Release Hashes**
```
9d5bee8eb9b2160dab985017bfa3e3db9c35033cfae97653a9fa8faa6064f228 rns-0.3.19-py3-none-any.whl
0f0996b5e401ca5d4e91080df3d6de326fc591164c9e6932a2eb79f1d2b8d375 rnspure-0.3.19-py3-none-any.whl
```

### 2022-11-03: RNS β 0.3.18

This maintenance release includes the `rnodeconf` utility directly in the `rns` package, and brings a few improvements to interface handling and hardware interfacing.

**Important!** The minimum supported RNode firmware version for this release is `1.51`, and the firmware will needs to be updated with `rnodeconf` version `2.0.0` or greater, since earlier versions won't be able to fetch the new release files.

**Changes**
- Added `rnodeconf` utility
- Added more options for controlling log output
- Added ability to write to the external framebuffer of RNode devices
- Improved teardown handling on RNode interfaces

**Release Hashes**
```
dc0c56950b85be763270695faf441029f7e6c31cdc44447c6c470e09c734aa45 rns-0.3.18-1-py3-none-any.whl
760bfc52419a8c45a420df41c40a1bf96bd494dabd7efe461c7907b152bbf39c rnspure-0.3.18-1-py3-none-any.whl
```