.. _api-main:

*************
API Reference
*************
This reference guide lists and explains all classes exposed by the RNS API.

Classes
=========================
Communication over a Reticulum network is achieved using a set of classes exposed by RNS.

.. _api-reticulum:

Reticulum
---------

.. autoclass:: RNS.Reticulum
   :members:


.. _api-identity:

Identity
--------

.. autoclass:: RNS.Identity
   :members:

.. _api-destination:

Destination
-----------

.. autoclass:: RNS.Destination
   :members:

.. _api-packet:

Packet
------

.. autoclass:: RNS.Packet(destination, data, create_receipt = True)
   :members:

.. _api-packetreceipt:

Packet Receipt
--------------

.. autoclass:: RNS.PacketReceipt()
   :members:

.. _api-link:

Link
----

.. autoclass:: RNS.Link(destination, established_callback=None, closed_callback = None)
   :members:

.. _api-requestreceipt:

Request Receipt
---------------

.. autoclass:: RNS.RequestReceipt()
   :members:

.. _api-resource:

Resource
--------

.. autoclass:: RNS.Resource(data, link, advertise=True, auto_compress=True, callback=None, progress_callback=None, timeout=None)
   :members:

.. _api-transport:

Transport
---------

.. autoclass:: RNS.Transport
   :members: