Reticulum Network Stack α
==========

Reticulum is a cryptography-based networking stack for low-bandwidth, high-latency, wide-area networks built on cheap and readily available hardware. Reticulum allows you to build very wide-area networks with cheap off-the-shelf tools, and offers end-to-end encryption, cryptographically backed multi-hop transport, efficient addressing, resource caching, unforgeable packet acknowledgements and much more.

Reticulum is a complete networking stack, and does not use IP or higher layers, although it can be easily tunnelled through conventional IP networks. This frees up a lot of overhead, that has been utilised to implement a networking stack built directly on cryptographic principles, allowing resilience and stable functionality in open and trustless networks.

For more info, see [unsigned.io/projects/reticulum](http://unsigned.io/projects/reticulum/)

## Current Status
Reticulum is currently in pre-alpha state. Even the master branch should be considered experimental. At this point the protocol may change without notice, and is made publicly available for development collaboration, previewing and testing features. Do not build anything serious with Reticulum yet. Stable alpha release will be at the end of May 2018.

## Dependencies:
 - cryptography.io
 - pyserial 3.1

