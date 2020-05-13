Reticulum Network Stack α
==========

Reticulum is a cryptography-based networking stack for high-latency, wide-area networks built on readily available hardware. Reticulum allows you to build very wide-area networks with off-the-shelf tools, and offers end-to-end encryption, autoconfiguring cryptographically backed multi-hop transport, efficient addressing, resource caching, unforgeable packet acknowledgements and much more.

Reticulum is a complete networking stack, and does not use IP or higher layers, although it can be easily tunnelled through conventional IP networks. This frees up overhead, that has been utilised to implement a networking stack built directly on cryptographic principles, allowing resilience and stable functionality in open and trustless networks.

No kernel modules or drivers are required. Reticulum runs completely in userland, and can run on practically any system that runs Python 3.

For more info, see [unsigned.io/projects/reticulum](https://unsigned.io/projects/reticulum/)

## Where can Reticulum be used?
On practically any hardware that can support at least a half-duplex channel with 1.000 bits per second throughput, and an MTU of 500 bytes. Data radios, modems, LoRa radios, serial lines, AX.25 TNCs, amateur radio digital modes, free-space optical links and similar systems are all examples of the types of interfaces Reticulum was designed for.

An open-source LoRa-based interface called [RNode](https://unsigned.io/projects/rnode/) has been designed specifically for use with Reticulum. It is possible to build yourself, or can be purchased as a complete transceiver that just needs a USB connection to the host.

Reticulum can also be encapsulated over existing IP networks, so there's nothing stopping you from using it over wired ethernet or your local WiFi network, where it'll work just as well. In fact, one of the strengths of Reticulum is how easily it allows you to connect different mediums into a self-configuring, resilient and encrypted mesh.

As an example, it's possible to set up a Raspberry Pi connected to both a LoRa radio, a packet radio TNC and a WiFi network. Once the interfaces are configured, Reticulum will take care of the rest, and any device on the WiFi network can communicate with nodes on the LoRa and packet radio sides of the network, and vice versa.

## Current Status
Consider Reticulum experimental at this stage. Most features are implemented and working, but at this point the protocol may still change significantly, and is made publicly available for development collaboration, previewing and testing.

An API- and wireformat-stable alpha release is coming in the near future. Until then expect things to change unexpectedly if something warrants it.

## What is implemented at this point?
 - Adressing and identification
 - Fully self-configuring multi-hop routing
 - RSA assymetric encryption and signatures as basis for all communication
 - AES-128 symmetric encryption for group destinations
 - Elliptic curve encryption for links (on the SECP256R1 curve)
 - Perfect Forward Secrecy on links with ephemereal ECDH keys
 - Unforgeable packet delivery confirmations
 - A variety of supported interface types
 - Efficient and easy resource transfers
 - A simple and easy-to-use API
 - Some basic programming examples

## Supported interface types and devices

Reticulum implements a range of generalised interface types that covers most of the communications hardware that Reticulum can run over. If your hardware is not supported, it's relatively simple to implement an interface class. Currently, the following interfaces are supported:

 - Any ethernet device
 - LoRa using [RNode](https://unsigned.io/projects/rnode/)
 - Packet Radio TNCs (with or without AX.25)
 - Any device with a serial port
 - TCP over IP networks
 - UDP over IP networks

## What is currently being worked on?
 - Delay/disruption tolerant bundle transfers
 - Useful example programs and utilities
 - API documentation
 - A messaging protocol built on Reticulum, see [LXMF](https://github.com/markqvist/lxmf)
 - A few useful-in-the-real-world apps built with Reticulum

## Can I use Reticulum on amateur radio spectrum?
Some countries still ban the use of encryption when operating under an amateur radio license. Reticulum offers several encryptionless modes, while still using cryptographic principles for station verification, link establishment, data integrity verification, acknowledgements and routing. It is therefore perfectly possible to include Reticulum in amateur radio use, even if your country bans encryption.

## Dependencies:
 - Python 3
 - cryptography.io
 - pyserial

## How do I get started?
Full documentation and tutorials are coming with the stable alpha release. Until then, you are mostly on your own. If you want to experiment already, you could take a look in the "Examples" folder, for some well-documented example programs. The default configuration file created by Reticulum on the first run is also worth reading. Be sure to also read the [Reticulum Overview Document](http://unsigned.io/wp-content/uploads/2018/04/Reticulum_Overview_v0.4.pdf).

If you just need Reticulum as a dependency for another application, the easiest way is probably via pip:

```bash
pip3 install rns
```

For development, you might want to get the latest source from GitHub. In that case, don't use pip, but try this recipe:

```bash
# Install dependencies
pip3 install cryptography pyserial

# Clone repository
git clone https://github.com/markqvist/Reticulum.git

# Move into Reticulum folder and symlink library to examples folder
cd Reticulum
ln -s ../RNS ./Examples/

# Run an example
python3 Examples/Echo.py -s

# Unless you've manually created a config file, Reticulum will do so now,
# and immediately exit. Make any necessary changes to the file:
nano ~/.reticulum/config

# ... and launch the example again.
python3 Examples/Echo.py -s

# You can now repeat the process on another computer,
# and run the same example with -h to get command line options.
python3 Examples/Echo.py -h

# Run the example in client mode to "ping" the server.
# Replace the hash below with the actual destination hash of your server.
python3 Examples/Echo.py 3e12fc71692f8ec47bc5

# Have a look at another example
python3 Examples/Filetransfer.py -h
```

The default config file contains examples for using Reticulum with LoRa transceivers (specifically [RNode](https://unsigned.io/projects/rnode/)), packet radio TNCs/modems and UDP. By default a UDP interface is already enabled in the default config, which will enable Reticulum communication in your local ethernet broadcast domain.

You can use the examples in the config file to expand communication over other mediums such as packet radio or LoRa, or over fast IP links using the UDP interface. I'll add in-depth tutorials and explanations on these topics later. For now, the included examples will hopefully be enough to get started.

## Caveat Emptor
Reticulum is alpha software, and should be considered experimental. While it has been built with cryptography best-practices very foremost in mind, it _has not_ been externally security audited, and there could very well be privacy-breaking bugs. If you want to help out, or help sponsor an audit, please do get in touch.