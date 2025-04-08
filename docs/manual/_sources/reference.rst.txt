:tocdepth: 4

.. _api-main:

*************
API Reference
*************
Communication over Reticulum networks is achieved by using a simple set of classes exposed by the RNS API.
This chapter lists and explains all classes exposed by the Reticulum Network Stack API, along with their method signatures and usage. It can be used as a reference while writing applications that utilise Reticulum, or it can be read in entirity to gain an understanding of the complete functionality of RNS from a developers perspective.

.. _api-reticulum:

.. only:: html

   |start-h3| Reticulum |end-h3|

.. only:: latex

   Reticulum
   ---------

.. autoclass:: RNS.Reticulum
   :members:


.. _api-identity:

.. only:: html

   |start-h3| Identity |end-h3|

.. only:: latex

   Identity
   --------

.. autoclass:: RNS.Identity
   :members:

.. _api-destination:

.. only:: html

   |start-h3| Destination |end-h3|

.. only:: latex

   Destination
   -----------

.. autoclass:: RNS.Destination
   :members:

.. _api-packet:

.. only:: html

   |start-h3| Packet |end-h3|

.. only:: latex

   Packet
   ------

.. autoclass:: RNS.Packet(destination, data, create_receipt = True)
   :members:

.. _api-packetreceipt:

.. only:: html

   |start-h3| Packet Receipt |end-h3|

.. only:: latex

   Packet Receipt
   --------------

.. autoclass:: RNS.PacketReceipt()
   :members:

.. _api-link:

.. only:: html

   |start-h3| Link |end-h3|

.. only:: latex

   Link
   ----

.. autoclass:: RNS.Link(destination, established_callback=None, closed_callback = None)
   :members:

.. _api-requestreceipt:

.. only:: html

   |start-h3| Request Receipt |end-h3|

.. only:: latex

   Request Receipt
   ---------------

.. autoclass:: RNS.RequestReceipt()
   :members:

.. _api-resource:

.. only:: html

   |start-h3| Resource |end-h3|

.. only:: latex

   Resource
   --------

.. autoclass:: RNS.Resource(data, link, advertise=True, auto_compress=True, callback=None, progress_callback=None, timeout=None)
   :members:

.. _api-channel:

.. only:: html

   |start-h3| Channel |end-h3|

.. only:: latex

   Channel
   -------

.. autoclass:: RNS.Channel.Channel()
   :members:

.. _api-messsagebase:

.. only:: html

   |start-h3| MessageBase |end-h3|

.. only:: latex

   MessageBase
   -----------

.. autoclass:: RNS.MessageBase()
   :members:

.. _api-buffer:

.. only:: html

   |start-h3| Buffer |end-h3|

.. only:: latex

   Buffer
   ------

.. autoclass:: RNS.Buffer
   :members:

.. _api-rawchannelreader:

.. only:: html

   |start-h3| RawChannelReader |end-h3|

.. only:: latex

   RawChannelReader
   ----------------

.. autoclass:: RNS.RawChannelReader
   :members: __init__, add_ready_callback, remove_ready_callback

.. _api-rawchannelwriter:

.. only:: html

   |start-h3| RawChannelWriter |end-h3|

.. only:: latex

   RawChannelWriter
   ----------------

.. autoclass:: RNS.RawChannelWriter
   :members: __init__

.. _api-transport:

.. only:: html

   |start-h3| Transport |end-h3|

.. only:: latex

   Transport
   ---------

.. autoclass:: RNS.Transport
   :members:

.. |start-h3| raw:: html

     <h3>

.. |end-h3| raw:: html

     </h3>