### 2024-05-05: RNS β 0.7.4

This maintenance release fixes a number of bugs, improves path requests and responses, and adds several useful features and capabilities. Thanks to @cobraPA, @jsculthess, @thiaguetz and @nothingbutlucas who contributed to this release!

**Changes**
- Added support for flashing and autoinstalling Heltec V3 boards to `rnodeconf`
- Added custom EEPROM bootstrapping capabilities to `rnodeconf`
- Added ability to load identities from file to Echo and Link examples
- Added ability to specify multicast address type in AutoInterface configuration
- Added link getter to resource advertisement class
- Improved path response logic and timing
- Improved path request timing
- Fixed a bug in Link Request proof delivery on unknown hop count paths
- Fixed broken link packet routing in topologies where transport packets leak to non-intended instances in the link chain
- Fixed typos in documentation

**Release Hashes**
```
f5c35f1b8720778eb508b687d66334d01b4ab266b2d8c2bc186702220dcaae29  rns-0.7.4-py3-none-any.whl
9eaa7170f97dad49551136965d3fcc971b56b1c2eda48c24b9ffd58d71daa016  rnspure-0.7.4-py3-none-any.whl
```

### 2024-03-09: RNS β 0.7.3

This release adds the ability to specify custom firmware URLs for flashing boards with `rnodeconf`. Thanks to @attermann who contributed to this release!

**Changes**
- Added ability to specify custom firmware URLs for flashing boards with `rnodeconf`

**Release Hashes**
```
bb24445ae9a3a63d348e4d7fe80b750608f257851b97b38fadab929b7a774bc9 rns-0.7.3-py3-none-any.whl
1b148d013103c35ba9a8e105082ef50686c130676d0a560ed709cb546129287e rnspure-0.7.3-py3-none-any.whl
```

### 2024-03-02: RNS β 0.7.2

This maintenance release improves memory consumption, fixes a few bugs, and adds ability to flash new boards with `rnodeconf`.

**Changes**
- Added ability to flash new boards with `rnodeconf`, including T3 boards with TCXOs
- Improved memory consumption on Transport Instances with many interfaces
- Fixed a bug that could cause the on-disk known destinations store to become corrupted

**Release Hashes**
```
3ce3ba80d5ae8d19c6b55bd51f44bd4beccbcea31554cb1f0d65428e4587b3d6 rns-0.7.2-py3-none-any.whl
83f914aaba2a8929a8cee95830a847e190197232a0cca4e7b906b15c6bbf8296 rnspure-0.7.2-py3-none-any.whl
```

### 2024-02-14: RNS β 0.7.1

This release adds support for RNodes based on SX1262, SX1268 and SX1280 modems, and fixes a number of bugs. Thanks to @jacobeva, who contributed to this release!

**Changes**
- Added support for SX1262, SX1268 and SX1280 based RNodes
- Updated `rnodeconf` to allow flashing T-Beam devices with SX126x chips
- Fixed an invalid RSSI offset reference

**Release Hashes**
```
8ecfbb42b6a699fd4ac5374ab5640e4bb164e80bb9ab4401ea82da132e497877 rns-0.7.1-py3-none-any.whl
e0ab487305ba1aee2d16044640e7eb72d332bbf51aeb0b8bf984d037a64cb493 rnspure-0.7.1-py3-none-any.whl
```

### 2024-01-17: RNS β 0.7.0

This maintenance release fixes a number of bugs. Thanks to @jooray and @jacobeva, who contributed to this release!

**Changes**
- Fixed large resource transfers failing under some conditions
- Fixed a potential division by zero
- Fixed a missing check on malformed advertisement packets
- Fixed a formatting issue in `rnprobe`
- Improved resource timeout calculations

**Release Hashes**
```
0dc2abe5373b9afadfba7ec05bf7ddeff659c004aa339a94001ebed5b46f5b47 rns-0.7.0-py3-none-any.whl
97f6e65a20b53bbdccd54b4d2bdaa36dc1712e144a55f40800c63fe7113819a5 rnspure-0.7.0-py3-none-any.whl
```

### 2023-12-07: RNS β 0.6.9

This release adds a few convenience functions to the `rnid` utility, and improves roaming support on Android.

**Changes**
- Added identity import and export in hex, base32 and base64 formats to the `rnid` utility.
- Added better carrier change detection for AutoInterface on Android.

**Release Hashes**
```
258daf22cb6e72c6cd04fe94447daedf51dfd968eb2f3370eab9c71ad0898dd0 rns-0.6.9-py3-none-any.whl
3644b64af5b4efd3969172bf0cf95ae1afba6c8ea99ce47d8e49e31a832bbaf8 rnspure-0.6.9-py3-none-any.whl
```

### 2023-11-14: RNS β 0.6.8

This maintenance release fixes a single bug.

**Bugfixes**
- Fixed packet receipts not being initialised in time for arriving proofs on fast interfaces

**Release Hashes**
```
3ffb01f3f45e35105ea30e60e5e493ba50528df38b4ea62672c9e1c093073b1c rns-0.6.8-py3-none-any.whl
de372814082ef7db59f4b2745b1f22b2ef9d97815190ec16c0596ba20406e0fb rnspure-0.6.8-py3-none-any.whl
```

### 2023-11-06: RNS β 0.6.7

This maintenance release improves tranport performance and fixes a logging bug.

**Changes**
- Improved local and remote transport performance by approximately 6x on faster links
- Significantly decreased latency over faster links

**Bugfixes**
- Fixed logging an error message when local clients connect while shared instance is still starting up

**Release Hashes**
```
c37dd1f59e037841f69ec518deecdae6719f978947de2473f04e7d95247805ac rns-0.6.7-py3-none-any.whl
1e2dcb44ec7271a4d26180db138fc54dce6d0d3cf3f816432d4d6a4b1cf83868 rnspure-0.6.7-py3-none-any.whl
```

### 2023-11-04: RNS β 0.6.6

This maintenance release improves transfers over unreliable links and fixes a bug in requests.

**Changes**
- Improved reliability of resource transfers over very slow and unreliable links

**Bugfixes**
- Fixed a bug that could cause requests to timeout prematurely

**Release Hashes**
```
b1127745750a43cd7389212d31aa09ccc735ab2d69e3b80bd28874f10082c322 rns-0.6.6-py3-none-any.whl
bf5ba5da4f37b93c14817367952cda63787ec88bbe601e41c13fcbb3fc22b6b6 rnspure-0.6.6-py3-none-any.whl
```

### 2023-11-02: RNS β 0.6.5

This release fixes a bug in path rediscovery for shared instance clients.

**Bugfixes**
- Fixed a bug in path rediscovery for shared instance clients

**Release Hashes**
```
5d54a5cfebe907c759351357a8f7d771670c895ff57f1325bf7fec42bcb46ba3 rns-0.6.5-py3-none-any.whl
accd2855e18ff06455b9454957388089e293073ec7093c64dee0dc7aa46ecb46 rnspure-0.6.5-py3-none-any.whl
```

### 2023-11-02: RNS β 0.6.4

This release fixes a number of bugs that had crept in while adding the new ultra low bandwidth link timing and faster path rediscovery mechanisms.

**Changes**
- Adjusted link timings for better support of very slow mediums
- Adjusted bluetooth read timeouts to account for occasional high latency in congested 2.4GHz environments
- Added a probe count option to the `rnprobe` utility.

**Bugfixes**
- Fixed a missing timeout calculation
- Fixed a redundant path request on path rediscovery
- Fixed missing path state resetting on stale path rediscovery
- Fixed a bug that could cause an attribute to be uninitialised

**Release Hashes**
```
566c725f68aa154eaca0880c894a39503027bf91714f17691e51d047800444c0 rns-0.6.4-py3-none-any.whl
a3a447fd40bf02fdb982523de0e4e9933e8e4cd4d4bd478254ea7dcac29e3fc1 rnspure-0.6.4-py3-none-any.whl
```

### 2023-10-31: RNS β 0.6.3

This release brings a series of under-the-hood reliability improvements and bugfixes. But most notably, Reticulum can now establish links over even ultra low bandwidth mediums, all the way down to 5 bits per second.

Thanks to @jschulthess, who contributed to this release!

**Changes**
- Implemented link establishment on ultra low bandwidth links
- Added link quality calculations to RNode interfaces
- Added physical layer link stats to Link and Packet classes
- Added userspace service documentation to the manual
- Improved path rediscovery in quickly changing topographies
- Improved shared interface reconnection on service restart
- Improved exception handling on interface detachment
- Updated formatted print functions

**Bugfixes**
- Fixed a missing USB command definition in the RNode interface driver
- Fixed a bug in link error handling that could cause an interface to detach

**Release Hashes**
```
1f54d4c6ff7ab7721089cbee6630783765f65efd51312879c0d3e5bee3ceab2f rns-0.6.3-py3-none-any.whl
5a90840f0fc9f1a62a3c37b514fb6222fd701a30024275dae8bcc27e29d40f25 rnspure-0.6.3-py3-none-any.whl
```

### 2023-10-07: RNS β 0.6.2

This maintenance release adds the ability to specify the shared instance RPC key in the Reticulum config file, making it possible to use all Reticulum functionality in the terminal on Android.

**Changes**
- Added configuration option to specify shared instance RPC key
- Reordered airtime stats in `rnstatus`
- Updated log levels on Android

**Bugfixes**
- Adding missing superclass init on Android interfaces

**Release Hashes**
```
a9958ad90f34f344003e18077f7abd3fa85666a39dc0cae8580071820dee13f9 rns-0.6.2-py3-none-any.whl
e68e8837d35d1a07a82c4b0e9db50ceace737a650e6e7e9ce2d9a013fd28f529 rnspure-0.6.2-py3-none-any.whl
```

### 2023-10-01: RNS β 0.6.1

This release brings a number of bugfixes, along with useful new mechanisms for ensuring network stability under high, non-constructive and unusual announce load situation.

**Changes**
- Added announce ingress rate control for new and unknown destinations
- Added per-interface announce frequency monitoring to the transport engine
- Added per-interface announce burst hold queues
- Added announce frequency statistics to `rnstatus`
- Added option to sort `rnstatus` output according to various metrics
- Added timeout options to `rnprobe`
- Added ability to drop all paths via a specific transport instance to `rnpath`
- Added new options and features to documentation and manual

**Bugfixes**
- Fixed announce queue not clearing all announces with exceeded retry limit at the same time
- Fixed a bug that caused local packet RSSI and SNR cache to get stuck
- Fixed output formatting in `rncp`
- Fixed `rnid` not allowing single-aspect destination names
- Fixed a number of typos in the documentation

**Release Hashes**
```
461e5cafa7560dcd3ec047141d10f0f48f151c36e1af1d65ec6c65f732cea46a rns-0.6.1-py3-none-any.whl
be6a4a6069f2d050e21582f2cf9d3bb59ed4040a0f07761a540bd752d90ea591 rnspure-0.6.1-py3-none-any.whl
```

#### 2023-09-21: RNS β 0.6.0

This release brings a few performance improvements, additions to the included utilities, and fixes a number of bugs.

**Changes**
- Added ability to run automatic probe responder on Transport Instances
- Improved `rnprobe` utility
- Improved AutoInterface peering on Android devices
- Improved Transport performance
- Improved path re-discovery when local nodes roam to other network segments
- Updated various parts of the documentation

**Bugfixes**
- Fixed missing timeout check in `rncp`
- Fixed missing link status check on `Identify()` call, which could lead to an unnecessary exception

**Release Hashes**
```
88a26b1593e82a628dab96dbe8820548aea0159235f730fa992bf1833db59246 rns-0.6.0-py3-none-any.whl
bcee416e4fb52346d01f6e0c46b1cebf84b127cc516603367fc2ae00a4149fa2 rnspure-0.6.0-py3-none-any.whl
```

### 2023-09-19: RNS β 0.5.9

This release brings major efficiency improvements to `Channel` and `Buffer` classes, adds a range of usability improvements to the included utilities and fixes a number of bugs.

**Changes**
- Improved `Channel` sequencing, retries and transfer efficiency
- Added adaptive compression to `Buffer` class
- Added `rnid` examples and documentation to manual
- Added silent mode to `rncp`
- Added remote fetch mode to `rncp`
- Added allowed_identities file support to `rncp`
- Added Transport Instance uptime to `rnstatus` output
- Added channel CSMA parameter stats to RNode Interface `rnstatus` output
- Added ability to set custom RNode OLED display address with rnodeconf

**Bugfixes**
- Fixed inadverdent AutoInterface multi-IF deque hit for resource transfer retries
- Fixed invalid path for firmware hash generation while using extracted firmware to autoinstall in `rnodeconf`
- Fixed various minor missing error checks
- Fixed `rnid` status output bug

**Release Hashes**
```
207ab20bd68bab16b417fbd41a4ecdbcf1e2f6fa553d48df6c8fc181b6e84dac rns-0.5.9-py3-none-any.whl
93f0965567dfc2c43f3d703481fe1a7d7b1b8d0b3837ad41c37f28a8af5c1acc rnspure-0.5.9-py3-none-any.whl
```

### 2023-09-14: RNS β 0.5.8

This maintenance release contains a number of usability improvements to Reticulum and related tools.

**Changes**
- Various documentation updates
- Improved path-resolution in mixed networks with roaming-mode nodes
- Added channel load and airtime stats to `rnstatus` output

**Release Hashes**
```
27ba5cdc4724fc8c7211c3b504f097f6adf47f7b80775e6297e4c4e621ef6348 rns-0.5.8-py3-none-any.whl
1ea1c949763c9478ec48f064f7f7864d9f859101ab91b44400879371f490800f rnspure-0.5.8-py3-none-any.whl
```

### 2023-08-14: RNS β 0.5.7

This maintenance release contains a number of bugfixes and quality improvements to Reticulum and related tools.

**Changes**
- Added bytes input to destination hash convenience functions
- Fixed possible invalid comparison in link watchdog job
- Add option to `rnodeconf` to set baud rate when flashing
- Added better explanation in `rnodeconf` when flashing fails
- Fixed EEPROM dump directory in `rnodeconf`

**Release Hashes**
```
867fbb5c73c2a49a75e1f8f3e9f376b507b683328e26c64d4387acd0cc1dbbc7 rns-0.5.7-py3-none-any.whl
7bab2865264b32208e023b5c4bbe88c37f51e3176ca4a8cf332d95f59a6d7f2c rnspure-0.5.7-py3-none-any.whl
```

### 2023-07-09: RNS β 0.5.6

This maintenance release contains a few bugfixes.

**Changes**
- Fixed an issue in `rnodeconf` that prevented Heltec LoRa32 v2 boards from being flashed.
- Fixed a typo in the `rnid` utility.

**Release Hashes**
```
255a5b4bac28326c6b2cc85f43b26dcb0606404a4abd2dfa8244937155838973 rns-0.5.6-py3-none-any.whl
1510b6da4641ceaa4c599a142e498c7e2c1ae12035868f9db1c111e5600161e9 rnspure-0.5.6-py3-none-any.whl
```

### 2023-06-13: RNS β 0.5.5

This maintenance release brings a single bugfix.

**Changes**
- Fixed a race condition for link initiators on timed out link establishments.

**Release Hashes**
```
4ae61d28bf981a7cb853c179e9de3b56b350d2dc984fb671a21d38c4ce5b449e rns-0.5.5-py3-none-any.whl
ed417cbd3c90e9f1b68565a3411ca5c9bc936b495300fd1ace3c4a6414aabd5a rnspure-0.5.5-py3-none-any.whl
```

### 2023-05-19: RNS β 0.5.4

This maintenance release brings a single bugfix.

**Changes**
- Fixed a potential race condition when timed-out link receives a late establishment proof a few milliseconds after it has timed out.

**Release Hashes**
```
71b42fe737da97a4b63bb227c29bb67854a7f003c9585f085b0ff68c8f460815 rns-0.5.4-py3-none-any.whl
af6949d581445444f57cfca75756200e7c509a6fc66483d859716ce6a06064db rnspure-0.5.4-py3-none-any.whl
```

### 2023-05-19: RNS β 0.5.3

This maintenance release brings a single, but important bugfix.

**Changes**
- Fixed a bug that could cause data corruption to occur over when using `Buffer` instances.

**Release Hashes**
```
f23c8d655c9e80a12a6728495aec56f19f27184d3d8e6b6ed6184b0e89d4be35 rns-0.5.3-py3-none-any.whl
2c692a2153bb766a9dc2391340a06f429c13a75b86b746b69c6fcd5a4fe5ee33 rnspure-0.5.3-py3-none-any.whl
```

### 2023-05-12: RNS β 0.5.2

This maintenance release brings a number of bugfixes and improvements.

**Important!** This release breaks backwards compatibility with `Channel` and `Buffer` for all previous releases, due to the addition of compression and windowing.

**Changes**
- Added ability to trust external signing keys to `rnodeconf`
- Added basic windowing to `Channel` and `Buffer`, improving performance over faster links
- Added per-packet compression to `Channel`
- Added automatic multi-interface duplicate deque to AutoInterface
- Fixed received link packet proofs not resetting link watchdog stale timer
- Fixed a missing exception isolation of packet delivery callbacks
- Fixed resent packets not getting repacked

**Release Hashes**
```
f3b1e9cf39420ad74c2b5c81ad339fd2a548320c9f6925bad9b614feb4c9b9d7 rns-0.5.2-py3-none-any.whl
8463f7365f179d02e7e4d4fe4afc69da4218ce40107305dfd06b9e6b29513e0f rnspure-0.5.2-py3-none-any.whl
```

### 2023-05-05: RNS β 0.5.1

This maintenance release brings a number of bugfixes and improvements. Thanks to @VioletEternity, who contributed to this release!

**Changes**
- Removed dependency on netifaces module
- Added ability to configure RNode display intensity to rnodeconf
- Added preliminary rnodeconf flasher/autoinstaller support for T3 v1.0 boards
- Fixed a bug that caused AutoInterface discovery scopes to fail
- Fixed rnodeconf firmware extraction for unverifiable devices
- Improved setting rnsd verbosity from command line
- Improved support for shared instances on Windows
- Improved rnodeconf support on Windows
- Improved rnodeconf zip-file handling
- Fixed a potentail race condition in announce queue handling for AutoInterface
- Various minor bugfixes

**Release Hashes**
```
01d76e03f93e427d9c0b95ab5d07e84ed39047e912b8afa6d619a65ac6b5e05b rns-0.5.1-py3-none-any.whl
2cfe431bec1160410b80bbcbf87eb2ab0d5abe5c6546f41eaf3f0f5faf9b2140 rnspure-0.5.1-py3-none-any.whl
```

### 2023-03-08: RNS β 0.5.0

This release brings two major new additions to the Reticulum API: The Channel and Buffer classes, that provides reliable delivery, and streams over Reticulum. Thanks to @acehoss, @erethon, @gdt and @faragher, who contributed to this release!

**Changes**
- Added the Buffer class to the API
- Added the Channel class to the API
- Improved error messages for offline RNode flashing
- Improved RNode reconnection when serial device disappears
- Fixed embedded scope identifier handling for AutoInterface on BSD
- Fixed AutoInterface not ignoring lo0 on BSD
- Fixed a bug causing JSON output from rnstatus to fail
- Fixed invalid installation of test suite into root module path
- Added EPUB version of the documentation
- Updated documentation

**Release Hashes**
```
0aaf8c0b0b58f07071de5ecd432f4d9cc176b9614419c828b81ad71aa7151624 rns-0.5.0-py3-none-any.whl
f310a5192c2df7665339c5998ae13815a647283af75b95ad7acbee8c20989954 rnspure-0.5.0-py3-none-any.whl
```

### 2023-02-17: RNS β 0.4.9

This maintenance release contains a number of bugfixes and minor improvements, along with a few additions to the API.

**Changes**
- Added JSON output mode to rnstatus
- Added Link ID to response_generator callback
- Added Link establishment rate calculation
- Added get_establishment_rate call to Link API
- Fixed a number of typos in programs and documentation
- Fixed some broken links in documentation

**Release Hashes**
```
b44eaed796dcd194bec7a541aaeeb1685b07b2ffce068ca268841e6a8661717f rns-0.4.9-py3-none-any.whl
a15f965a27d208493485724486eb6bc6268d699f2a22ae4fb816bb9b979330fc rnspure-0.4.9-py3-none-any.whl
```

### 2023-02-04: RNS β 0.4.8

This release introduces the useful `rnid` utility, which makes it possible to use Reticulum Identities for offline file encryption, decryption, signing and validation. The IFAC system has also been significantly improved, and several outdated parts of the documentation was updated and fixed. Thanks to @Erethon and @jooray who contributed to this release!

**Changes**
- Added header and payload masking to the IFAC system
- Added `rnid` utility for encrypting, decrypting, signing and validating with Reticulum Identities
- Added Bluetooth pairing PIN output to `rnodeconf` utility
- Fixed a bug in announce callback handling
- Fixed a inconsistency in header flag handling since IFACs were introduced
- Updated documentation and manual

**Release Hashes**
```
fbbd55ee43a68c18491f5deabed51085c46fadca7e1bda823ad455c2f7c95a51 rns-0.4.8-py3-none-any.whl
335b0d5dd1d2aacd0d8810191aa09567ecf5d3aa990c446f3e3b1bbf7fce1387 rnspure-0.4.8-py3-none-any.whl
```

### 2023-01-14: RNS β 0.4.7

This maintenance release adds support for using the `rnodeconf` utility to replicate RNode devices, and bootstrap device creation using only tools and software packages obtained from an RNode Bootstrap Console.

**Changes**
- Added the ability to use rnodeconf to bootstrap RNode creation without needing a connection to the Internet
- Added ability for rnodeconf to extract firmwares from existing RNodes
- Added ability for rnodeconf to use extracted firmwares for autoinstaller and updates
- Updated documentation and manual

**Release Hashes**
```
7ea22be8f4cc9504d8a612c5589132351cc0c6b474899204afd71367ab3fb226 rns-0.4.7-py3-none-any.whl
3dc337b80df37c247abc9cee06c3ecba0f908449005d0eb365c2a9577d689e57 rnspure-0.4.7-py3-none-any.whl
```

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

### 2022-11-03: RNS β 0.3.17

This maintenance release fixes a regression in the 0.3.16 release.

**Changes**
- Fixed an incorrect import that inadverdently caused Android-specific interfaces to be used on non Android operating systems.

**Release Hashes**
```
SHA256 0e8327461e2d39f859059cc14e94fb33f21e1186c422bb766950f42ca1387656 rns-0.3.17-py3-none-any.whl
SHA256 9e31160cc38e0d5531460d5eca7b3f6e6d8c3b2a7afb04338ee72cc488a2ba18 rnspure-0.3.17-py3-none-any.whl
```

### 2022-10-20: RNS β 0.3.16

This maintenance release fixes a single bug that prevented running RNS in Termux (and similar) on Android.

**Changes**
- Fixed missing imports and module checks for API-limited environments on Android

**Release Hashes**
```
SHA256 dc4202302b1f1503a0f1c8fef7123b31f7d5d7131ae5b9f988064ebe22e29ed8 rns-0.3.16-py3-none-any.whl
SHA256 127624d2592745602d4a056c347fa6f5989f049275a5b8bfa97c296af9bc497f rnspure-0.3.16-py3-none-any.whl
```

### 2022-10-20: RNS β 0.3.15

This maintenance release primarily adds support for external hardware interfaces on Android. A number of bugs have also been fixed, and improvements made to logging output consistency.

**Changes**
- Added support for RNode interfaces on Android
- Added support for KISS interfaces on Android
- Added support for Serial interfaces on Android
- Added AutoInterface support for kernel network devices that rotate MAC addresses on roaming and/or reconnects
- Updated various helper functions
- Minor log output cleanup and fixes
- Fixed missing lookup for locally running destinations in Identity.recall() when running as a shared transport instance
- Fixed missing announce cap property on hot-plugged interfaces
- Fixed incorrect behaviour in announce processing for instance-local destinations to roaming- or boundary-mode interfaces

**Release Hashes**
```
SHA256 c56f32dbfd10fae1b5d2dddafe7d2a0f2127908827a71fce9e43fd051ea453bc rns-0.3.15-py3-none-any.whl
SHA256 597d6df05b3586eaa1515c0215cec30d7a018a209e7900634345c39514efcd18 rnspure-0.3.15-py3-none-any.whl
```

### 2022-10-07: RNS β 0.3.14

This maintenance release brings a few improvements, including optimised announce packet structure and updated documentation.

**Please note!** While this is a small maintenance release, it includes changes to packe structure that breaks backwards compatibility with all previous RNS versions.

**Changes**
- Optimised announce packet structure
- Reject mismatching public keys on hash collision.
- Minor updates to documentation

**Release Hashes**
```
SHA256 b761efc24d20c5719817bfefbbe8ce69f7c91d65bb8273cb02578f77d6f88bc5 rns-0.3.14-py3-none-any.whl
SHA256 cc24a1f010431c8f193ec0ffc6dccade614a5be40c47ac12e3e9ae60b52f046e rnspure-0.3.14-py3-none-any.whl
```

### 2022-10-04: RNS β 0.3.13

This maintenance release includes a single but important bugfix.

**Changes**
- Fixed missing hash construction step in announce emission and validation

**Release Hashes**
```
SHA256 d6c8a7cb8ea7edc99800df92abff246e8159f2d9c9f1a2b57672385d49647c90 rns-0.3.13-py3-none-any.whl
SHA256 c07c28942e374342c4e807a0b6e81d831737b87cf59651670b8c1c191030a326 rnspure-0.3.13-py3-none-any.whl
```

### 2022-09-30: RNS β 0.3.12

This maintenance release includes a fix to the [serious security flaw discussed here](https://github.com/markqvist/Reticulum/discussions/103). **Please Note!** Updating to RNS 0.3.12 will intentionally break backwards compatibility with all previous verstions for link establishment. It is recommended to upgrade all your systems to 0.3.12 as soon as possible.

Additionally, this release brings a range of small, but very useful improvements to reliability and user experience, along with a significant update to the documentation material.

**Changes**
- Fixed a [serious security flaw](https://github.com/markqvist/Reticulum/discussions/103) in link establishment key exchanges
- Allow hot-plug of RNode devices
- Better detachment handler for TCP clients on shutdown
- Implemented better config directory path handling
- Clarifications and improvements to various documentation chapters
- Improved writing quality of documentation, courtesy of @huyndao
- Improved overall presentation of documentation and manual
- Improved reliability of data persistence in case of unexpected shutdowns or hardware crashes
- Added rnsd warning on start as client
- Fixed a rendering bug in the rnpath utility
- Added initial connection timeout configuration option to TCP Client interfaces
- Brought deprecated native python API calls up to date

**Release Hashes**
```
SHA256 74a4881ebf8d805bffb43efef91769b1cbb87affe56ac630355946c7484cffbf rns-0.3.12-py3-none-any.whl
SHA256 03429122b3b4133667632ba2404df7bbf57ea5df1b9c815d7608b1d59cd29a76 rnspure-0.3.12-py3-none-any.whl
```

### 2022-07-09: RNS β 0.3.11

This maintenance release contains a single but important bug fix in resource transfers.

**Changes**
- Fixed a an incorrect size calculation for resource advertisements, that would lead to resources of specific sizes failing with an MTU error.

**Release Hashes**
```
SHA256 7c03a003326bcd127226414b08cf48f87bcc6b88a7279c52e28415315668543c rns-0.3.11-py3-none-any.whl
SHA256 1a6aaa3ba370ece28cc975ba94b0461c61497cf0797f92662472e0ec20576cb1 rnspure-0.3.11-py3-none-any.whl
```

### 2022-07-08: RNS β 0.3.10

This maintenance release contains a single but important bug fix for systems running Reticulum Transport Instances.

**Changes**
- Fixed a potential race condition in link establishment flow, that could lead to links not being established over hops with very low latency.

**Release Hashes**
```
SHA256 1c9fb56b967aed507694e6b5d5fca7a89b022cad9fa2058d248e359dc150fba7 rns-0.3.10-py3-none-any.whl
SHA256 8eae07f9e6241ea1f3778430456225dee3ef73bb1c4df5e5362dd00226404628 rnspure-0.3.10-py3-none-any.whl
```

### 2022-07-05: RNS β 0.3.9

This release expands the address space of Reticulum to 128 bits, and brings improvements to the documentation, along with a few bugfixes and updates.

**Changes**
- Expanded address space to 128 bits
- Updated documentation
- Improved rnx interactive mode
- Improved readme file
- Added reticulum.network website
- Added periodic cache cleaning
- Fixed a bug in the --no-auth option in rncp

**Release Hashes**
```
SHA256 892005e95fc9eda4c4c5d9f94dd33cdc27d3ac6e228d1b0b2519e35069951b86 rns-0.3.9-1-py3-none-any.whl
SHA256 cb7d873c51c746ecdb8963a6a7a0e8d010fb6c61ee785c5e97376d3779a7bae8 rnspure-0.3.9-1-py3-none-any.whl
```

### 2022-06-22: RNS β 0.3.8

This release brings big improvements to compatibility with various system types, along with several convenient new features, and a lot of tuning, optimisation and stability improvements. In a continued effort, the documentation has also been updated, restructured, and had several new and informative sections added.

**Changes**
- Added ability to install and run RNS without any dependencies
- Added backend abstraction for cryptographic primitives
- Added pure-python implementations of all cryptographic primitives
- Added accept option to Link API
- Added several undocumented API calls to the documentation
- Added option to filter interfaces to rnstatus utility
- Added "Communications Hardware" chapter to the documentation
- Improved multiple chapters and restructured documentation
- Improved efficiency of Transport instances
- Improved performance of Resource transfers
- Improved Resource handling strategies over different physical link types
- Improved link capacity and speed estimation calculations
- Improved I2P interface error handling and stability
- Tuned Resource and Link timeouts
- Tuned TCP socket options for better reliability over intermittent links
- Tuned I2P interface timeouts for better reliability over intermittent links
- Fixed a missing check for zero-length packets on IFAC-enabled interfaces
- Fixed a socket allocation leak in I2P interfaces
- Added unit tests
- Added performance profiling tools
- Improved build system

Release SHA-256 for `rns-0.3.8-py3-none-any.whl` is `fdb53aba14840edf3d71dde1a745f319e7f60d6993851b7651bf8ba3d5c53ba7`
Release SHA-256 for `rnspure-0.3.8-py3-none-any.whl` is `b0eb004c3725bc20496b1c855e7d22729d8a39fd0cde957ab95aa8c7e13ee3a4`

### 2022-05-29: RNS β 0.3.7

This release comes with a big upgrade to reliability and resilience, with lots of small bug fixes and improvements, along with some significant new additions and features. The documentation and API reference has also seen several improvements for clarity.

Users of I2P interfaces will see big improvements in reliability with better handling of errors from the I2P SAM API, and much better automatic recovery when I2P connectivity is intermittent.

Reticulum is now able to perform network-wide discovery of unknown paths, using the new Gateway interface mode. The stability of established links has also been improved by using a better timeout calculation method.

It is also worth mentioning the addition of the two new utilities, `rncp` and `rnx`, that allow you to transfer files to remote systems, and perform remote command execution.

*Please Note!* For using 64-bit IFACs on RNode hardware, your RNodes must be running at least firmware version 1.28.

**Changes**
- Added gateway interface mode
- Added `rncp` utility for transferring files to remote destinations
- Added `rnx` utility for remotely executing commands and returning output
- Implemented unknown path discovery
- Implemented recursive path request loop avoidance
- Implemented bandwidth cap for recursive path requests
- Improved Link authentication callbacks
- Improved Link stale time calculations and process
- Improved error detection and handling in I2P interfaces
- Improved automatic recovery and reliability on intermittent I2P interfaces
- Added request size to receipts, and updated relevant API documentation
- Added default identity storage folder
- Fixed deprecated options in libi2p's asyncio calls
- Fixed I2P controller startup when event loop is not immediately ready
- Fixed bug in conditional resource acceptance callback
- Fixed an invalid interface mode check
- Fixed missing recursive progress callback allocation in segmented resource transfer
- Fixed expired AP and Roaming interface mode paths not being removed at the correct time
- Fixed announce rate targets not being set on I2PInterface peers
- Fixed naming conflict in resource advertisements
- Fixed link stale time calculation on newly created links without any actual traffic
- Fixed a bug that caused large packets (over 492 bytes) with IFAC enabled to be dropped on RNode hardware
- Improved output of `rnstatus` utility
- Improved Destination and Link API documentation
- Updated documentation and readme

Release SHA-256 for Python Wheel is `2cd9a584d6b13bb478a43b49b7de3f2a8270c4b8979666b1ca40cd81daacbf42`

### 2022-05-17: RNS β 0.3.6

This release adds a number of improvements, a new interface type, and some very useful new interface modes.

**Changes**
- Added PipeInterface, create interfaces with any program over stdio
- Added "roaming" and "boundary" interface modes
- Added per-interface announce rate control
- Added ability to drop announce queues to rnpath utility
- Added announce rate information output to rnpath utility
- Improved announce queue processing
- Improved several documentation chapters
- Improved logging output

### 2022-04-28: RNS β 0.3.5

This release brings major improvements and upgrades to Reticulum, along with better documentation and improved usability of the bundled utilities.

**Changes**
- Greatly improved convergence time. Even on huge networks, newly created destinations become globally reachable in less than a minute.
- New announce propagation mechanism allows flexible scalability. Extremely slow network segments can now interconnect seamlessly with huge, high-bandwidth networks while still prioritising end-to-end connectivity for local nodes.
- Reticulum can now scale to huge and complex networks with up to 128 hops, and billions of active endpoints.
- Added virtual network segmentation for running multiple virtual networks over the same physical channel.
- Added interface authentication for creating private access network interfaces and access points.
- Updated documentation in accordance with current implementation of announce propagation mechanism.
- Updated several outdated documentation chapters.
- Added documentation for new interface features.
- The output display of the rnstatus utility has been greatly improved.
- Added ability to drop paths to the rnpath utility.
- Added path table display to rnpath utility.
- Added interface rate determination and estimation.
- Added configurable bandwidth allocation for announce traffic.
- Improved and cleaned logging output.
- Various Transport optimisations.
- Improved AutoInterface peering timing.
- Updated manual in accordance with release.
- Fixed a possible race condition in Transport startup when a local shared instance was restarted and apps reconnected.

### 2022-03-28: RNS β 0.3.4

This is a small maintenance release with a bugfix and some documentation and reliability improvements.

**Changes**
- Fixed https://github.com/markqvist/Reticulum/issues/18 that could potentially cause a routing loop if the API was used in an unintended way
- Improved cryptography API compatibility
- Improved documentation

### 2022-02-26: RNS β 0.3.3

This release adds major new functionality to Reticulum, including new connectivity options, improves stability, simplifies configuration and fixes a few bugs.

**Improvements**
 - Added the I2P Interface to Reticulum
 - Added I2P tunneling support for TCP interfaces
 - Improved recovery of AutoInterface on underlying medium carrier loss
 - Improved AutoInterface timeouts and timing
 - Enabled the "outbound" interface option as on by default
 - Added the "Access Point" interface mode
 - Simplified default configuration
 - Added verbose configuration example to the "rnsd" program
 - Improved documentation and manual
 - Fixed a potential race condition in resource assembly
 - Fixed a reference error in TCP interfaces
 - Fixed a configuration keyword error

### 2022-01-28: RNS β 0.3.2

This maintenance release adds support for using a much wider range of devices as RNode LoRa interfaces with Reticulum, and also contains a few bugfixes and improvements.

**Important!** From this release, RNodes used with Reticulum must have at least firmware version 1.26 installed, due to the new multiplatform RNode support.

**Improvements**
 - Added full support for RNodes based on ESP32 and ATmega2560 boards
 - Fixed a bug in TCP interfaces on macOS
 - Updated documentation and manual

### 2022-01-26: RNS β 0.3.1

This is a small maintenance and update release of Reticulum, including a few improvements. It also adds support for using ESP32-based T-Beam devices.

Improvements:
 - Added support for using T-Beam devices using the RNodeInterface
 - Improved AutoInterface on Android
 - Improved platform handling
 - Improved malformed packet handling

### 2021-12-11: RNS β 0.3.0

This is a major release of Reticulum, including a range of stability and performance improvements, along with important new features, expanding the connectivity of Reticulum.

An important improvement in this release is the addition of the AutoInterface, that will now be configured as the default interface on new installs. This interface automatically meshes with other Reticulum peers over any available system network devices, and doesn't require any existing IP infrastructure like a DHCP server or a router. For more information, consult the relevant section of the manual.

**Improvements**
 - Added new AutoInterface as default interface for new installs
 - Serial port interfaces now automatically attempt to reconnect devices that are unplugged and replugged
 - Added support for KISS over TCP in the TCPClientInterface
 - Added support for running Reticulum as a systemd service
 - Initial support for the Android operating system
 - Added documentation for installing Reticulum on Android in Termux
 - Improved documentation and manual
 - Better path request handling for shared instances
 - Better shutdown handling on external interrupts
 - Many small stability and reliability improvements
 - Fine-tuned various timing parameters for different link types

### 2021-10-15: RNS β 0.2.9

This beta release adds the fundamentals of RSSI and SNR functionality. It also implements timing improvements, allowing Reticulum to function on even lower bitrate physical links.

**Improvements**
 - Added RSSI and SNR reporting on supported interfaces
 - Added RSSI and SNR to rnprobe utility
 - Added RSSI and SNR to Echo example
 - Support for physical layer throughput down to 500 bits per second.
 - Improved callback handling

### 2021-10-10: RNS β 0.2.8

This beta release brings a single, but important improvement. Paths are now updated much more fluidly for peers moving around the network.

Since updates were made to how tunnels and path table entries are represented in this release, it is recommended to delete the following files on Transport Nodes:

~/.reticulum/storage/destination_table
~/.reticulum/storage/packet_hashlist
~/.reticulum/storage/tunnels
~/.reticulum/storage/cache/*

The files will be recreated when Reticulum is started.

**Improvements**
 - Improved path updates for peers moving around the network

### 2021-10-08: RNS β 0.2.7

This beta release brings a range of stability improvements and one bugfix.

**Improvements**
 - Improved output of the rnstatus utility
 - Improved shared instance and local client handling
 - Improved documentation
 - Improved path restoration on tunnels
 - Added log rotation

**Fixed bugs**
 - Fixed incorrect interface detachment on TCP client interfaces

### 2021-09-25: RNS β 0.2.6

This beta release brings a range of improvements and a few bugfixes.

**Improvements**
 - Added the "rnsd" utility for running Reticulum as a service
 - Added the "rnstatus" utility for viewing interface status
 - Added the "rnpath" utility for path lookups
 - Added the "rnprobe" utility for testing connectivity
 - Documentation has been improved and expanded
 - Improved shutdown handling for shared instances
 - Improved default configuration
 - Improved recovery of TCP interfaces over unreliable links

**Fixed bugs**
 - Fixed a bug in reverse table culling
 - Fixed a regression in TCP interface client spawner

### 2021-09-18: RNS β 0.2.5

This beta release brings a range of improvements and bugfixes.

**Improvements**
 - Added endpoint tunneling for path restoration over intermittent or roving link layer connections.
 - Added ability for TCP client interfaces to automatically reconnect if TCP socket drops.
 - Improved link teardown handling.
 - Improved interface error handling on non-recoverable / hardware errors.

**Fixed bugs**
 - Fixed a bug that could cause path table entries to be culled two times in rare cases.
 - Fixed a bug that could lead to the "outgoing" directive of interface configuration entries not being parsed correctly.

### 2021-09-11: RNS β 0.2.4

This beta release brings a range of improvements and bugfixes.

**Improvements**
 - Increased link MDU from 415 to 431 bytes by optimising transfer of Fernet tokens.
 - All data lengths are now calculated dynamically from Reticulums base MTU, laying the groundwork for dynamic MTU interoperability.
 - Disabled option to allow unencrypted links.
 - Improved documentation.
 - Improved request timeouts and handling.
 - Improved link establishment.
 - Improved resource transfer timing. 

**Fixed bugs**
 - Fixed a race condition in inbound proof handling.
 - Fixed sequencing errors caused by duplicate HMU/request packets not being filtered.

### 2021-08-29: RNS β 0.2.3

This beta release brings a range of improvements and bugfixes.

**Improvements**
 - Improved resource handling.
 - Improved timeout calculation for packets, links, resources and requests.
 - Improved announce handling for shared instances.
 - Improved default configuration template.
 - Added example "Speedtest".

**Fixed bugs**
 - Fixed an issue that caused request timeout even though response had occurred.
 - Fixed an issue that caused identity files to be written incorrectly.
 - Fixed resource sequencing errors not being handled gracefully.

### 2021-08-21: RNS β 0.2.2

This beta release brings several new features to Reticulum along with two bugfixes.

IMPORTANT! This version breaks wire-format compatibility with all previous versions of Reticulum. You must update *all* of your nodes at the same time.

**New features**
 - Link initiators can now identify to the remote peer over the link, once it has been set up. This can be used for authentication, amongst other things.
 - Requests and responses of arbitrary sizes can now be carried out over links.
 - UDP and TCP interfaces can now be bound to network device names (eth0, wlan0, etc.) instead of manually specifying listen IPs.

**Fixed bugs**
 - Fixed a race condition in outbound transport packet filtering.
 - Fixed an issue where local UDP broadcast echoes could get processed as inbound packets.

### 2021-05-20: RNS β 0.2.1

This beta release sees significant improvements to bandwidth utilization and efficiency, while improving security by dropping RSA and moving completely to Curve25519.

- All asymmetric cryptography migrated to X25519/Ed25519. This has greatly improved efficiency and reduced protocol overhead significantly.
- Work has continued on the documentation, and the "Understanding Reticulum" chapters have been improved significantly in this release.
- Class methods dealing with setting callbacks have been renamed to be more intuitive.

As a few examples of the improved efficiency, a complete link establishment now only costs 240 bytes, down from 409 in the previous RSA version. An announce takes up 151 bytes vs 323.

### 2021-05-18: RNS β 0.2.0

This is the first beta release of RNS. This release also marks the publication of the Reticulum documentation, manual, and API documentation. All core features of Reticulum are now implemented, functional and ready to use in external programs. The wire-format and API will only change if there is a very good reason, though internals are still likely to be altered and optimised, and features are likely to be added.

### 2021-05-13: RNS α 0.1.9

This was a pre-release alpha version. No changelog available.

### 2020-08-13: RNS α 0.1.8

This was a pre-release alpha version. No changelog available.

### 2020-08-13: RNS α 0.1.7

This was a pre-release alpha version. No changelog available.

### 2020-06-10: RNS α 0.1.6

This was a pre-release alpha version. No changelog available.

### 2020-06-09: RNS α 0.1.5

This was a pre-release alpha version. No changelog available.

### 2020-05-29: RNS α 0.1.4

This was a pre-release alpha version. No changelog available.

### 2020-05-21: RNS α 0.1.3

This was a pre-release alpha version. No changelog available.

### 2020-05-15: RNS α 0.1.2

This was a pre-release alpha version. No changelog available.

### 2020-05-14: RNS α 0.1.1

This was a pre-release alpha version. No changelog available.

### 2020-05-12: RNS α 0.1.0

This was a pre-release alpha version. No changelog available.

### 2020-04-28: RNS α 0.0.9

This was a pre-release alpha version. No changelog available.

### 2020-04-28: RNS α 0.0.8

This was the first publicly available pre-release alpha of Reticulum.

### 2016-05-29: Inintial Repository Commit

The first commit to the Reticulum reference implementation was 9a9630cfd29e11ace3f12716ddb4dff0e5419b4b, which occurred on Sunday, the 29th of May 2016.
