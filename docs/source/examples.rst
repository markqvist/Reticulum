.. _examples-main:

********
Examples
********
A number of examples are included in the source distribution of Reticulum.
You can use these examples to learn how to write your own programs.

.. _example-minimal:

Minimal
=======
This example can be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Minimal.py>`_.

The *Minimal* example demonstrates the bare-minimum setup required to connect to
a Reticulum network from your program. In about five lines of code, you will
have the Reticulum Network Stack initialised, and ready to pass traffic in your
program.

.. _example-announce:

Announce
========
This example can be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Announce.py>`_.

The *Announce* example builds upon the previous example by exploring how to
announce a destination on the network, and how to let your program receive
notifications about announces from relevant destinations.

.. _example-broadcast:

Broadcast
=========
This example can be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Broadcast.py>`_.

The *Broadcast* example explores how to transmit plaintext broadcast messages
over the network.

.. _example-echo:

Echo
====
This example can be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Echo.py>`_.

The *Echo* example demonstrates communication between two destinations using
the Packet interface.

.. _example-link:

Link
====
This example can be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Link.py>`_.

The *Link* example explores establishing an encrypted link to a remote
destination, and passing traffic back and forth over the link.

.. _example-filetransfer:

Filetransfer
============
This example can be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Filetransfer.py>`_.

The *Filetransfer* example implements a basic file-server program that
allow clients to connect and download files. The program uses the Resource
interface to efficiently pass files of any size over a Reticulum :ref:`Link<api-link>`.