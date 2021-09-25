.. _examples-main:

*************
Code Examples
*************

A number of examples are included in the source distribution of Reticulum.
You can use these examples to learn how to write your own programs.

.. _example-minimal:

Minimal
=======

The *Minimal* example demonstrates the bare-minimum setup required to connect to
a Reticulum network from your program. In about five lines of code, you will
have the Reticulum Network Stack initialised, and ready to pass traffic in your
program.

.. literalinclude:: ../../Examples/Minimal.py

This example can also be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Minimal.py>`_.

.. _example-announce:

Announce
========

The *Announce* example builds upon the previous example by exploring how to
announce a destination on the network, and how to let your program receive
notifications about announces from relevant destinations.

.. literalinclude:: ../../Examples/Announce.py

This example can also be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Announce.py>`_.

.. _example-broadcast:

Broadcast
=========
The *Broadcast* example explores how to transmit plaintext broadcast messages
over the network.

.. literalinclude:: ../../Examples/Broadcast.py

This example can also be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Broadcast.py>`_.

.. _example-echo:

Echo
====

The *Echo* example demonstrates communication between two destinations using
the Packet interface.

.. literalinclude:: ../../Examples/Echo.py

This example can also be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Echo.py>`_.

.. _example-link:

Link
====

The *Link* example explores establishing an encrypted link to a remote
destination, and passing traffic back and forth over the link.

.. literalinclude:: ../../Examples/Link.py

This example can also be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Link.py>`_.

.. _example-identify:

Identification
==============

The *Identify* example explores identifying an intiator of a link, once
the link has been established.

.. literalinclude:: ../../Examples/Identify.py

This example can also be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Identify.py>`_.

.. _example-request:

Requests & Responses
====================

The *Request* example explores sendig requests and receiving responses.

.. literalinclude:: ../../Examples/Request.py

This example can also be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Request.py>`_.

.. _example-filetransfer:

Filetransfer
============

The *Filetransfer* example implements a basic file-server program that
allow clients to connect and download files. The program uses the Resource
interface to efficiently pass files of any size over a Reticulum :ref:`Link<api-link>`.

.. literalinclude:: ../../Examples/Filetransfer.py

This example can also be found at `<https://github.com/markqvist/Reticulum/blob/master/Examples/Filetransfer.py>`_.