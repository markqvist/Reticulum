Reticulum Network Stack α
==========

Reticulum is a cryptography-based networking stack for low-bandwidth, high-latency, wide-area networks built on cheap and readily available hardware. Reticulum allows you to build very wide-area networks with cheap off-the-shelf tools, and offers end-to-end encryption, autoconfiguring cryptographically backed multi-hop transport, efficient addressing, resource caching, unforgeable packet acknowledgements and much more.

Reticulum is a complete networking stack, and does not use IP or higher layers, although it can be easily tunnelled through conventional IP networks. This frees up a lot of overhead, that has been utilised to implement a networking stack built directly on cryptographic principles, allowing resilience and stable functionality in open and trustless networks.

Reticulum runs completely in userland, and can run on practically any system that runs Python.

For more info, see [unsigned.io/projects/reticulum](https://unsigned.io/projects/reticulum/)

## What hardware does Reticulum work with?
Practically any hardware that can support at least a half-duplex channel with 1.000 bits per second throughput, and an MTU of 500 bytes. Data radios, modems, LoRa radios, serial lines, AX.25 TNCs, HAM radio digital modes, free-space optical links and similar systems are all examples of the types of interfaces Reticulum was designed for.

An open-source LoRa-based interface called [RNode](https://unsigned.io/projects/rnode/) has been designed specifically for use with Reticulum. It is easy to build yourself, or can be purchased as a complete radio that just needs a USB connection to the host.

Reticulum can also be tunneled over existing IP networks, so there's nothing stopping you from using it over gigabit fiber or your local WiFi network, where it'll work just as well. In fact, one of the strengths of Reticulum is how easily it allows you to connect different mediums into a self-configuring, resilient and encrypted mesh.

As an example, it's possible to set up a Raspberry Pi connected to both a LoRa radio, a packet radio TNC and your home WiFi. Once the interfaces are configured, Reticulum will take care of the rest, and any device on your home WiFi can communicate with nodes on the LoRa and packet radio sides of the network.

## Current Status
Consider Reticulum experimental at this stage. Most features are implemented and working, but at this point the protocol may still change significantly, and is made publicly available for development collaboration, previewing and testing.

An API- and wireformat-stable alpha release is coming in the near future. Until then expect things to change unexpectedly if something warrants it.

## What is implemented at this point?
 - All basic adressing and identification features
 - RSA assymetric encryption and signatures as basis for all communication
 - Elliptic curve encryption for links (on the SECP256R1 curve)
 - Unforgeable packet delivery confirmations
 - Fully self-configuring multi-hop routing
 - A variety of supported interface types
 - Efficient and easy resource transfers
 - A simple and easy-to-use API
 - A few basic examples

## What features are still missing?
 - On-network caching and cache queries

## What is currently being worked on?
 - Useful example programs and utilities
 - API documentation
 - Cleanup and code commenting
 - A few useful-in-the-real-world apps built with Reticulum

## Can I use Reticulum on amateur radio spectrum?
Some countries still ban the use of encryption when operating under an amateur radio license. Reticulum offers several encryptionless modes, while still using cryptographic principles for station verification, link establishment, data integrity verification, acknowledgements and routing. It is therefore perfectly possible to include Reticulum in amateur radio use, even if your country bans encryption.

## Dependencies:
 - Python 2.7
 - cryptography.io
 - pyserial 3.1

## How do I get started?
Full documentation and video tutorials are coming with the stable alpha release. Until then, you are mostly on your own. If you really want to experiment already, you could take a look in the "Examples" folder, for some well-documented example programs. Be sure to also read the [Reticulum Overview Document](http://unsigned.io/wp-content/uploads/2018/04/Reticulum_Overview_v0.4.pdf).

To install dependencies and get started:

```
# Install dependencies
pip install cryptography pyserial

# Clone repository
git clone https://github.com/markqvist/Reticulum.git

# Move into Reticulum folder and symlink library to examples folder
cd Reticulum
ln -s ../RNS ./Examples/

# Run an example
python Examples/Echo.py -s

# Unless you've manually created a config file, Reticulum will do so now, and immediately exit. Make any necessary changees to the file and launch the example again.
python Examples/Echo.py -s

# You can now repeat the process on another computer, and run the same example with -h to get command line options.
python Examples/Echo.py -h

# Run the example in client mode to "ping" the server. Replace the hash below with the actual destination hash of your server.
python Examples/Echo.py 3e12fc71692f8ec47bc5

# Have a look at another example
python Examples/Filetransfer.py -h
```

I'll add configuration examples for LoRa, packet radio TNCs and more in the near future. Until then, it should be possible to infer the config format quite easily from the classes in the Interfaces directory and the UDPInterface example created by default.